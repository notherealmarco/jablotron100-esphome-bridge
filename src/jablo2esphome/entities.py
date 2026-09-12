"""ESPHome native API entity wrappers for Jablotron controls.

Each class bridges one ``EntityType`` from the de-HA'd core onto the native
API messages the vendored ``aioesphomeserver`` knows how to serve. State
changes flow from ``state_sync`` through the entity's ``set_state`` and are
broadcast by the server's ``notify_state_change``; client commands arrive via
``handle(..., 'client_request', <CommandRequest>)``.
"""
from __future__ import annotations

from aioesphomeapi.api_pb2 import (  # type: ignore
	AlarmControlPanelCommandRequest,
	AlarmControlPanelStateResponse,
	EventResponse,
	ListEntitiesAlarmControlPanelResponse,
	ListEntitiesEventResponse,
	ListEntitiesTextSensorResponse,
	SwitchCommandRequest,
	TextSensorStateResponse,
)
from aioesphomeserver import (
	BasicEntity,
	BinarySensorEntity,
	SensorEntity,
	SwitchEntity,
)

from .const import (
	AlarmControlPanelState,
	EntityType,
	EventLoginType,
	STATE_OFF,
	STATE_ON,
)
from .mapping import (
	BINARY_SENSOR_DESCRIPTORS,
	SENSOR_DESCRIPTORS,
	TEXT_SENSOR_ENTITY_TYPES,
	entity_display_name,
	stable_sub_device_id,
)

# ESPHome protobuf values (see aioesphomeapi.api_pb2, api_version 46.x).
# 1 | 2 | 4 == ARM_AWAY | ARM_HOME | ARM_NIGHT; partial arming is negotiated
# by the user via config, the rest is timeless.
ACP_SUPPORTED_FEATURES = 1 | 2 | 4

ALARM_STATE_TO_PROTO = {
	AlarmControlPanelState.DISARMED.value: 0,
	AlarmControlPanelState.ARMED_HOME.value: 1,
	AlarmControlPanelState.ARMED_AWAY.value: 2,
	AlarmControlPanelState.ARMED_NIGHT.value: 3,
	AlarmControlPanelState.PENDING.value: 6,
	AlarmControlPanelState.ARMING.value: 7,
	AlarmControlPanelState.DISARMING.value: 8,
	AlarmControlPanelState.TRIGGERED.value: 9,
}

ALARM_COMMAND_TO_STATE = {
	0: AlarmControlPanelState.DISARMED,
	1: AlarmControlPanelState.ARMED_AWAY,
	2: AlarmControlPanelState.ARMED_HOME,
	3: AlarmControlPanelState.ARMED_NIGHT,
}


class JablotronSensor(SensorEntity):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

	async def set_state(self, val):
		if val is None:
			return
		await super().set_state(float(val))


class JablotronBinarySensor(BinarySensorEntity):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

	async def set_state(self, val):
		await super().set_state(val == STATE_ON)


class TextSensorEntity(BasicEntity):
	"""A string-valued sensor (used for the central unit LAN IP address)."""

	DOMAIN = "text_sensor"

	async def build_list_entities_response(self):
		return ListEntitiesTextSensorResponse(
			object_id=self.object_id,
			name=self.name,
			key=self.key,
			icon=self.icon,
			entity_category=self.entity_category,
			device_class=self.device_class,
			device_id=self.device_id,
		)

	async def build_state_response(self):
		return TextSensorStateResponse(
			key=self.key,
			state=self._state or "",
			device_id=self.device_id,
		)

	async def get_state(self):
		return self._state

	async def set_state(self, val):
		if val is None:
			return
		text = str(val)
		if text == self._state:
			return
		self._state = text
		await self.notify_state_change()


class AlarmPanelEntity(BasicEntity):
	"""Alarm control panel for one Jablotron section."""

	DOMAIN = "alarm_control_panel"

	def __init__(self, hub, control, name, device_id):
		self.hub = hub
		self.control = control
		super().__init__(name=name, object_id=control.id, device_id=device_id)
		self._state = None

	def is_code_required_for_arm(self) -> bool:
		return self.hub.is_code_required_for_arm()

	def is_code_required_for_disarm(self) -> bool:
		return self.hub.is_code_required_for_disarm()

	async def build_list_entities_response(self):
		return ListEntitiesAlarmControlPanelResponse(
			object_id=self.object_id,
			name=self.name,
			key=self.key,
			icon=self.icon,
			entity_category=self.entity_category,
			supported_features=ACP_SUPPORTED_FEATURES,
			requires_code=self.is_code_required_for_arm() or self.is_code_required_for_disarm(),
			requires_code_to_arm=self.is_code_required_for_arm(),
			device_id=self.device_id,
		)

	async def build_state_response(self):
		return AlarmControlPanelStateResponse(
			key=self.key,
			state=self._state if self._state is not None else 0,
			device_id=self.device_id,
		)

	async def set_state(self, val):
		if isinstance(val, AlarmControlPanelState):
			val = val.value
		proto_state = ALARM_STATE_TO_PROTO.get(val)
		if proto_state is None or proto_state == self._state:
			return
		self._state = proto_state
		await self.notify_state_change()

	async def handle(self, key, message):
		if type(message) != AlarmControlPanelCommandRequest:
			return
		if message.key != self.key:
			return
		state = ALARM_COMMAND_TO_STATE.get(message.command)
		if state is None:
			return
		self.hub.modify_section_state(self.control.section, state, message.code or None)


class PgOutputSwitch(SwitchEntity):
	"""Jablotron programmable output, commandable both ways."""

	def __init__(self, hub, control, name, device_id):
		self.hub = hub
		self.control = control
		super().__init__(name=name, object_id=control.id, device_class="switch", device_id=device_id)

	async def set_state(self, val):
		if isinstance(val, str):
			val = val == STATE_ON
		await super().set_state(bool(val))

	async def handle(self, key, message):
		if type(message) != SwitchCommandRequest:
			return
		if message.key != self.key:
			return
		state = message.state
		self.hub.toggle_pg_output(self.control.pg_output_number, STATE_ON if state else STATE_OFF)
		await self.set_state(state)


class LoginEventEntity(BasicEntity):
	"""Login events (only 'wrong_code' is currently known)."""

	DOMAIN = "event"

	def __init__(self, hub, control, name: str, device_id):
		self.hub = hub
		self.control = control
		super().__init__(name=name, object_id=control.id, icon="mdi:login", device_id=device_id)

	async def build_list_entities_response(self):
		return ListEntitiesEventResponse(
			object_id=self.object_id,
			name=self.name,
			key=self.key,
			icon=self.icon,
			entity_category=self.entity_category,
			device_class=self.device_class,
			event_types=[EventLoginType.WRONG_CODE.value],
			device_id=self.device_id,
		)

	async def build_state_response(self):
		return EventResponse(
			key=self.key,
			event_type="",
			device_id=self.device_id,
		)

	async def publish_event(self, event_type: str) -> None:
		message = EventResponse(
			key=self.key,
			event_type=event_type,
			device_id=self.device_id,
		)
		await self.device.publish(self, "state_change", message)


def build_entity(hub, control, entity_type: EntityType) -> BasicEntity | None:
	device_id = stable_sub_device_id(control.hass_device) if control.hass_device is not None else 0
	name = entity_display_name(control, entity_type)

	if entity_type == EntityType.ALARM_CONTROL_PANEL:
		return AlarmPanelEntity(hub, control, name, device_id)

	if entity_type == EntityType.EVENT_LOGIN:
		return LoginEventEntity(hub, control, name, device_id)

	if entity_type == EntityType.PROGRAMMABLE_OUTPUT:
		return PgOutputSwitch(hub, control, name, device_id)

	if entity_type in TEXT_SENSOR_ENTITY_TYPES:
		return TextSensorEntity(
			name=name,
			object_id=control.id,
			device_id=device_id,
		)

	descriptor = SENSOR_DESCRIPTORS.get(entity_type)
	if descriptor is not None:
		return JablotronSensor(
			name=name,
			object_id=control.id,
			icon=descriptor.get("icon"),
			device_class=descriptor.get("device_class"),
			entity_category=descriptor.get("category"),
			unit_of_measurement=descriptor.get("unit"),
			accuracy_decimals=descriptor.get("accuracy_decimals"),
			state_class=descriptor.get("state_class"),
			device_id=device_id,
		)

	descriptor = BINARY_SENSOR_DESCRIPTORS.get(entity_type)
	if descriptor is not None:
		return JablotronBinarySensor(
			name=name,
			object_id=control.id,
			device_class=descriptor.get("device_class"),
			entity_category=descriptor.get("category"),
			device_id=device_id,
		)

	return None