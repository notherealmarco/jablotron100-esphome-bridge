"""Entity-type descriptor tables and sub-device helpers.

Describes how each de-HA'd core ``EntityType`` maps onto a native API entity,
mirroring the Home Assistant platform files (sensor.py, binary_sensor.py,
switch.py, alarm_control_panel.py, event.py). Values use the prose-level
strings the ESPHome native API expects (device classes, state classes, units)
rather than the Home Assistant enums those platform files import.
"""
from __future__ import annotations

import zlib
from typing import Any

from aioesphomeapi.api_pb2 import DeviceInfo  # type: ignore

from .const import EntityType

ENTITY_CATEGORY_CONFIG = 1
ENTITY_CATEGORY_DIAGNOSTIC = 2

# Home Assistant exposes one binary sensor per device state; ESPHome does too.
# device_class / icon / entity_category mirror binary_sensor.py.
BINARY_SENSOR_DESCRIPTORS: dict[EntityType, dict[str, Any]] = {
	EntityType.BATTERY_PROBLEM: {"device_class": "problem", "category": ENTITY_CATEGORY_DIAGNOSTIC},
	EntityType.DEVICE_STATE_MOTION: {"device_class": "motion"},
	EntityType.DEVICE_STATE_WINDOW: {"device_class": "window"},
	EntityType.DEVICE_STATE_DOOR: {"device_class": "door"},
	EntityType.DEVICE_STATE_GARAGE_DOOR: {"device_class": "garage_door"},
	EntityType.DEVICE_STATE_GLASS: {},
	EntityType.DEVICE_STATE_MOISTURE: {"device_class": "moisture"},
	EntityType.DEVICE_STATE_GAS: {"device_class": "gas"},
	EntityType.DEVICE_STATE_SMOKE: {"device_class": "smoke"},
	EntityType.DEVICE_STATE_LOCK: {"device_class": "lock"},
	EntityType.DEVICE_STATE_TAMPER: {"device_class": "tamper"},
	EntityType.DEVICE_STATE_THERMOSTAT: {},
	EntityType.DEVICE_STATE_THERMOMETER: {},
	EntityType.DEVICE_STATE_INDOOR_SIREN_BUTTON: {},
	EntityType.DEVICE_STATE_BUTTON: {},
	EntityType.DEVICE_STATE_VALVE: {},
	EntityType.DEVICE_STATE_CUSTOM: {},
	EntityType.FIRE: {},
	EntityType.GSM_SIGNAL: {"device_class": "connectivity", "category": ENTITY_CATEGORY_DIAGNOSTIC},
	EntityType.LAN_CONNECTION: {"device_class": "connectivity", "category": ENTITY_CATEGORY_DIAGNOSTIC},
	EntityType.POWER_SUPPLY: {"device_class": "problem", "category": ENTITY_CATEGORY_DIAGNOSTIC},
	EntityType.PROBLEM: {"device_class": "problem", "category": ENTITY_CATEGORY_DIAGNOSTIC},
}

# device_class / unit / accuracy_decimals / state_class / icon / category
# mirror sensor.py.
SENSOR_DESCRIPTORS: dict[EntityType, dict[str, Any]] = {
	EntityType.SIGNAL_STRENGTH: {
		"unit": "%",
		"accuracy_decimals": 0,
		"state_class": "measurement",
		"icon": "mdi:wifi",
		"category": ENTITY_CATEGORY_DIAGNOSTIC,
	},
	EntityType.GSM_SIGNAL_STRENGTH: {
		"unit": "%",
		"accuracy_decimals": 0,
		"state_class": "measurement",
		"icon": "mdi:wifi",
		"category": ENTITY_CATEGORY_DIAGNOSTIC,
	},
	EntityType.BATTERY_LEVEL: {
		"unit": "%",
		"accuracy_decimals": 0,
		"state_class": "measurement",
		"device_class": "battery",
		"category": ENTITY_CATEGORY_DIAGNOSTIC,
	},
	EntityType.BATTERY_STANDBY_VOLTAGE: {
		"unit": "V",
		"accuracy_decimals": 1,
		"state_class": "measurement",
		"device_class": "voltage",
		"category": ENTITY_CATEGORY_DIAGNOSTIC,
	},
	EntityType.BATTERY_LOAD_VOLTAGE: {
		"unit": "V",
		"accuracy_decimals": 1,
		"state_class": "measurement",
		"device_class": "voltage",
		"category": ENTITY_CATEGORY_DIAGNOSTIC,
	},
	EntityType.TEMPERATURE: {
		"unit": "\u00b0C",
		"accuracy_decimals": 1,
		"state_class": "measurement",
		"device_class": "temperature",
	},
	EntityType.BUS_DEVICES_CURRENT: {
		"unit": "mA",
		"accuracy_decimals": 0,
		"state_class": "measurement",
		"device_class": "current",
		"category": ENTITY_CATEGORY_DIAGNOSTIC,
	},
	EntityType.BUS_VOLTAGE: {
		"unit": "V",
		"accuracy_decimals": 1,
		"state_class": "measurement",
		"device_class": "voltage",
		"category": ENTITY_CATEGORY_DIAGNOSTIC,
	},
	EntityType.PULSES: {
		"accuracy_decimals": 0,
		"state_class": "total_increasing",
	},
}

# LAN_IP holds a text value (the IP address), so it must be a text sensor,
# not a numeric sensor.
TEXT_SENSOR_ENTITY_TYPES: frozenset = frozenset({EntityType.LAN_IP})

# Display names for each entity type (mirrors the integration's
# translations/en.json under entity/<domain>/<key>/name). The (sub-)device name
# is deliberately NOT included: Home Assistant composes "<device> <entity>" for
# the native API entities itself, so every entity that is not on the root
# device gets its device name prefixed automatically (has_entity_name).
DEFAULT_ENTITY_NAMES: dict[EntityType, str] = {
	EntityType.EVENT_LOGIN: "Login",
	EntityType.POWER_SUPPLY: "Power supply",
	EntityType.BATTERY_PROBLEM: "Battery problem",
	EntityType.BATTERY_LEVEL: "Battery level",
	EntityType.BATTERY_STANDBY_VOLTAGE: "Battery standby voltage",
	EntityType.BATTERY_LOAD_VOLTAGE: "Battery load voltage",
	EntityType.BUS_DEVICES_CURRENT: "BUS devices current",
	EntityType.BUS_VOLTAGE: "BUS voltage",
	EntityType.LAN_CONNECTION: "LAN connection",
	EntityType.LAN_IP: "LAN IP",
	EntityType.GSM_SIGNAL: "GSM signal",
	EntityType.GSM_SIGNAL_STRENGTH: "GSM signal strength",
	EntityType.SIGNAL_STRENGTH: "Signal strength",
	EntityType.PULSES: "Pulses",
	EntityType.FIRE: "Fire",
	EntityType.PROBLEM: "Problem",
	EntityType.DEVICE_STATE_MOTION: "Motion",
	EntityType.DEVICE_STATE_WINDOW: "Window",
	EntityType.DEVICE_STATE_DOOR: "Door",
	EntityType.DEVICE_STATE_GARAGE_DOOR: "Garage door",
	EntityType.DEVICE_STATE_GLASS: "Glass break",
	EntityType.DEVICE_STATE_MOISTURE: "Moisture",
	EntityType.DEVICE_STATE_GAS: "Gas",
	EntityType.DEVICE_STATE_SMOKE: "Smoke",
	EntityType.DEVICE_STATE_LOCK: "Lock",
	EntityType.DEVICE_STATE_TAMPER: "Tamper",
	EntityType.DEVICE_STATE_THERMOSTAT: "Thermostat",
	EntityType.DEVICE_STATE_THERMOMETER: "Thermometer",
	EntityType.DEVICE_STATE_INDOOR_SIREN_BUTTON: "Button",
	EntityType.DEVICE_STATE_BUTTON: "Button",
	EntityType.DEVICE_STATE_VALVE: "Valve",
	EntityType.DEVICE_STATE_CUSTOM: "Custom",
}


def entity_display_name(control: Any, entity_type: EntityType) -> str:
	# An explicit control name (user-named control, PG output) wins. Otherwise
	# use the entity-type name; never the device name, or every entity on the
	# same device would share it and collide in Home Assistant.
	if control.name:
		return control.name
	if entity_type == EntityType.ALARM_CONTROL_PANEL:
		# The panel represents its whole section device, so HA shows the
		# device name (the integration sets _attr_name = None for this).
		return _rendered_device_name(control) or DEFAULT_ENTITY_NAMES.get(entity_type, _humanize(entity_type))
	return DEFAULT_ENTITY_NAMES.get(entity_type, _humanize(entity_type))


def _humanize(entity_type: EntityType) -> str:
	return entity_type.value.replace("_", " ").title()


def _rendered_device_name(control: Any) -> str | None:
	hass_device = getattr(control, "hass_device", None)
	if hass_device is None or not hass_device.name:
		return None
	return hass_device.name.format(**hass_device.translation_placeholders)


def stable_sub_device_id(hass_device: Any) -> int:
	# crc32 is stable across processes/restarts, unlike Python's salted hash().
	return zlib.crc32(hass_device.id.encode("utf-8")) & 0xFFFFFFFF


def build_sub_devices(jablotron: Any) -> list:
	devices: dict = {}
	for entity_type, entities in jablotron.entities.items():
		for control in entities.values():
			hass_device = control.hass_device
			if hass_device is None:
				continue
			if hass_device.id in devices:
				continue
			devices[hass_device.id] = DeviceInfo(
				device_id=stable_sub_device_id(hass_device),
				name=_rendered_device_name(control) or hass_device.name,
			)
	return list(devices.values())