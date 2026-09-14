"""End-to-end test: bridge native API server vs the real aioesphomeapi client.

Spawns the vendored aioesphomeserver with a stubbed Jablotron hub and connects
using the installed aioesphomeapi client, exercising list-entities,
subscribe-states, alarm commands and switch commands over the actual wire.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from aioesphomeapi.api_pb2 import (
	AlarmControlPanelCommandRequest,
	AlarmControlPanelStateResponse,
	BinarySensorStateResponse,
	EventResponse,
	ListEntitiesAlarmControlPanelResponse,
	ListEntitiesBinarySensorResponse,
	ListEntitiesDoneResponse,
	ListEntitiesEventResponse,
	ListEntitiesRequest,
	ListEntitiesSensorResponse,
	ListEntitiesSwitchResponse,
	ListEntitiesTextSensorResponse,
	SensorStateResponse,
	SubscribeStatesRequest,
	SwitchCommandRequest,
	SwitchStateResponse,
	TextSensorStateResponse,
)
from aioesphomeapi.connection import APIConnection, ConnectionParams

from jablo2esphome.const import (
	AlarmControlPanelState,
	EntityType,
	EVENT_WRONG_CODE,
	PartiallyArmingMode,
	STATE_OFF,
	STATE_ON,
)
from jablo2esphome.runtime import BridgeRuntime
from jablo2esphome.state_sync import EspDeviceTree, StateSync


class FakeHassDevice:

	def __init__(self, device_id: str, name: str, placeholders=None):
		self.id = device_id
		self.name = name
		self.translation_placeholders = placeholders or {}


class FakeControl:

	def __init__(self, control_id, name=None, hass_device=None, section=None, pg_output_number=None):
		self.id = control_id
		self.name = name
		self.hass_device = hass_device
		self.section = section
		self.pg_output_number = pg_output_number


class FakeJablotron:

	def __init__(self):
		device5 = FakeHassDevice("device_5", "Motion detector (device {deviceNo})", {"deviceNo": "5"})
		section1 = FakeHassDevice("section_1", "Section {sectionNo}", {"sectionNo": "1"})

		self.entities = {
			EntityType.ALARM_CONTROL_PANEL: {
				"section_1": FakeControl("section_1", hass_device=section1, section=1),
			},
			EntityType.PROGRAMMABLE_OUTPUT: {
				"pg_output_1": FakeControl("pg_output_1", name="PG output 1", pg_output_number=1),
			},
			EntityType.EVENT_LOGIN: {
				"login": FakeControl("login"),
			},
			EntityType.DEVICE_STATE_MOTION: {
				"device_sensor_5": FakeControl("device_sensor_5", hass_device=device5),
			},
			EntityType.BATTERY_LEVEL: {
				"device_battery_level_sensor_5": FakeControl("device_battery_level_sensor_5", hass_device=device5),
			},
			EntityType.LAN_IP: {
				"lan_ip": FakeControl("lan_ip"),
			},
		}

		self.states = {
			"section_1": AlarmControlPanelState.DISARMED,
			"pg_output_1": STATE_OFF,
			"device_sensor_5": STATE_OFF,
			"device_battery_level_sensor_5": 85,
			"lan_ip": "192.168.1.7",
		}

	def signal_entities_added(self) -> str:
		return "jablotron100_bridge_entities_added"


class FakeHub:

	def __init__(self, runtime):
		self.runtime = runtime
		self.settings = SimpleNamespace(
			name="Jablotron",
			store_dir=Path("/tmp/jablo2esphome-e2e"),
		)
		self.fixed_mac = "02:00:00:01:02:03"
		self.jablotron = FakeJablotron()
		self.modify_calls = []
		self.toggle_calls = []

	def signal_entities_added(self) -> str:
		return self.jablotron.signal_entities_added()

	def central_unit_model(self):
		return "JA-103K"

	def is_code_required_for_arm(self) -> bool:
		return False

	def is_code_required_for_disarm(self) -> bool:
		return True

	def partially_arming_mode(self) -> PartiallyArmingMode:
		return PartiallyArmingMode.NIGHT_MODE

	def snapshot(self):
		return dict(self.jablotron.states), True, False

	def modify_section_state(self, section, state, code):
		self.modify_calls.append((section, state, code))

	def toggle_pg_output(self, number, state):
		self.toggle_calls.append((number, state))


async def _connect(port: int, password: str) -> APIConnection:
	conn = APIConnection(
		ConnectionParams(
			addresses=["127.0.0.1"],
			port=port,
			password=password,
			client_info="jablo2esphome e2e",
			keepalive=5.0,
			zeroconf_manager=None,
			noise_psk=None,
			expected_name=None,
			expected_mac=None,
			provide_time=False,
		),
		None,
		False,
		"jablo2esphome e2e",
	)
	await conn.start_resolve_host()
	await conn.start_connection()
	await conn.finish_connection(login=True)
	return conn


async def _list_entities(conn: APIConnection) -> dict:
	responses = await conn.send_messages_await_response_complex(
		(ListEntitiesRequest(),),
		lambda resp: True,
		lambda resp: type(resp) is ListEntitiesDoneResponse,
		(
			ListEntitiesAlarmControlPanelResponse,
			ListEntitiesBinarySensorResponse,
			ListEntitiesEventResponse,
			ListEntitiesSensorResponse,
			ListEntitiesSwitchResponse,
			ListEntitiesTextSensorResponse,
			ListEntitiesDoneResponse,
		),
		5.0,
	)

	entities = {}
	for resp in responses:
		if type(resp) is ListEntitiesDoneResponse:
			continue
		entities[resp.object_id] = resp
	return entities


@pytest.mark.asyncio
async def _spin_server(tmp_path):
	from aioesphomeserver import NativeApiServer

	loop = asyncio.get_running_loop()
	runtime = BridgeRuntime(loop, tmp_path)
	hub = FakeHub(runtime)

	tree = EspDeviceTree(hub)
	tree.build()
	server = NativeApiServer(name="_server", port=0, api_version_minor=18)
	tree.add_server(server)
	server_task = asyncio.create_task(server.run())
	await asyncio.sleep(0.1)
	port = server.server.sockets[0].getsockname()[1]
	return server, server_task, tree, loop, port


@pytest.mark.asyncio
async def test_abrupt_client_disconnect_does_not_wedge_loop(tmp_path):
	"""An abrupt disconnect must not wedge the event loop for other clients.

	Regression: read_next_message() returned None on peer EOF and the
	connection loop re-entered it, which at EOF returned synchronously with no
	yielding await point, starving the event loop for every other client.
	"""
	server, server_task, _tree, _loop, port = await _spin_server(tmp_path)

	conn_a = None
	conn_b = None
	try:
		# Client A connects and completes the hello/login handshake, then
		# slams the transport shut without a DisconnectRequest — the same
		# abnormal disconnect HA (or a crashed probe) produces.
		conn_a = await _connect(port, "")
		assert conn_a.is_connected
		conn_a._frame_helper.close()
		await asyncio.sleep(0.2)
		conn_a = None

		# Client B must still get its hello + full entity list promptly.
		conn_b = await asyncio.wait_for(_connect(port, ""), 5.0)
		assert conn_b.is_connected
		entities = await asyncio.wait_for(_list_entities(conn_b), 5.0)
		assert "section_1" in entities
	finally:
		if conn_a is not None:
			try:
				await conn_a.disconnect()
			except Exception:
				pass
		if conn_b is not None:
			await conn_b.disconnect()
		await server.stop()
		server_task.cancel()
		try:
			await server_task
		except asyncio.CancelledError:
			pass
		await _tree.device.unregister_zeroconf()


@pytest.mark.asyncio
async def test_end_to_end_native_api(tmp_path):
	from aioesphomeserver import NativeApiServer

	loop = asyncio.get_running_loop()
	runtime = BridgeRuntime(loop, tmp_path)
	hub = FakeHub(runtime)

	tree = EspDeviceTree(hub)
	tree.build()

	server = NativeApiServer(name="_server", port=0, api_version_minor=18)
	tree.add_server(server)

	server_task = asyncio.create_task(server.run())
	await asyncio.sleep(0.1)
	port = server.server.sockets[0].getsockname()[1]

	received = []
	conn = None
	try:
		conn = await _connect(port, "")
		assert conn.is_connected

		conn.add_message_callback(
			lambda msg: received.append(msg),
			(
				AlarmControlPanelStateResponse,
				BinarySensorStateResponse,
				EventResponse,
				SensorStateResponse,
				SwitchStateResponse,
				TextSensorStateResponse,
			),
		)

		entities = await _list_entities(conn)
		assert "section_1" in entities
		assert "pg_output_1" in entities
		assert "login" in entities
		assert "device_sensor_5" in entities
		assert "lan_ip" in entities

		acp = entities["section_1"]
		assert acp.device_id != 0
		# FakeHub defaults to night_mode: ARM_AWAY | ARM_NIGHT only.
		assert acp.supported_features == (2 | 4)
		sensor = entities["device_battery_level_sensor_5"]
		assert sensor.device_id != 0
		assert sensor.unit_of_measurement == "%"

		conn.send_message(SubscribeStatesRequest())
		await asyncio.sleep(0.3)

		by_type = {type(msg): msg for msg in received}
		assert SwitchStateResponse in by_type
		assert by_type[SwitchStateResponse].state is False

		# state changes heard on the wire
		await tree.get("section_1").set_state(AlarmControlPanelState.ARMED_AWAY)
		await tree.get("device_sensor_5").set_state(STATE_ON)
		await tree.get("lan_ip").set_state("192.168.1.8")
		await asyncio.sleep(0.3)

		by_type = {type(msg): msg for msg in received}
		assert by_type[AlarmControlPanelStateResponse].state == 2
		assert by_type[BinarySensorStateResponse].state is True
		assert by_type[TextSensorStateResponse].state == "192.168.1.8"

		# commands round-trip
		key_acp = acp.key
		conn.send_message(AlarmControlPanelCommandRequest(key=key_acp, command=1))
		key_switch = entities["pg_output_1"].key
		conn.send_message(SwitchCommandRequest(key=key_switch, state=True))
		await asyncio.sleep(0.2)

		(section, state, code) = hub.modify_calls[-1]
		assert (section, state) == (1, AlarmControlPanelState.ARMED_AWAY)
		assert hub.toggle_calls[-1] == (1, STATE_ON)
	finally:
		if conn is not None:
			await conn.disconnect()
		await server.stop()
		server_task.cancel()
		try:
			await server_task
		except asyncio.CancelledError:
			pass
		await tree.device.unregister_zeroconf()


@pytest.mark.asyncio
async def test_wrong_code_event(tmp_path):
	from aioesphomeserver import NativeApiServer

	loop = asyncio.get_running_loop()
	runtime = BridgeRuntime(loop, tmp_path)
	hub = FakeHub(runtime)

	tree = EspDeviceTree(hub)
	tree.build()
	server = NativeApiServer(name="_server", port=0, api_version_minor=18)
	tree.add_server(server)
	server_task = asyncio.create_task(server.run())
	await asyncio.sleep(0.1)
	port = server.server.sockets[0].getsockname()[1]

	state_sync = StateSync(tree)
	await state_sync.start()

	received = []
	conn = None
	try:
		conn = await _connect(port, "")
		conn.add_message_callback(lambda msg: received.append(msg), (EventResponse,))
		conn.send_message(SubscribeStatesRequest())
		await asyncio.sleep(0.3)

		runtime.bus.fire(EVENT_WRONG_CODE)
		await asyncio.sleep(0.3)

		assert any(type(msg) is EventResponse and msg.event_type == "wrong_code" for msg in received)
	finally:
		await state_sync.stop()
		if conn is not None:
			await conn.disconnect()
		await server.stop()
		server_task.cancel()
		try:
			await server_task
		except asyncio.CancelledError:
			pass
		await tree.device.unregister_zeroconf()


@pytest.mark.asyncio
async def test_plaintext_login_accepts_any_password(tmp_path):
	from aioesphomeserver import NativeApiServer

	loop = asyncio.get_running_loop()
	runtime = BridgeRuntime(loop, tmp_path)
	hub = FakeHub(runtime)

	tree = EspDeviceTree(hub)
	tree.build()

	server = NativeApiServer(name="_server", port=0, api_version_minor=18)
	tree.add_server(server)

	server_task = asyncio.create_task(server.run())
	await asyncio.sleep(0.1)
	port = server.server.sockets[0].getsockname()[1]

	conn = None
	try:
		conn = await _connect(port, "wrong-password")
		assert conn.is_connected
	finally:
		if conn is not None:
			await conn.disconnect()
		await server.stop()
		server_task.cancel()
		try:
			await server_task
		except asyncio.CancelledError:
			pass
		await tree.device.unregister_zeroconf()


@pytest.mark.asyncio
async def test_zeroconf_txt_has_no_api_encryption_key(monkeypatch):
	import aioesphomeserver.device as device_module
	from aioesphomeserver.device import Device

	captured = {}

	class FakeZeroconf:
		def __init__(self, *args, **kwargs):
			pass

		async def async_register_service(self, service_info):
			captured["properties"] = dict(service_info.properties)

		async def async_close(self):
			pass

	class FakeServiceInfo:
		def __init__(self, *args, **kwargs):
			self.properties = kwargs.get("properties", {})

	monkeypatch.setattr(device_module, "AsyncZeroconf", FakeZeroconf)
	monkeypatch.setattr(device_module, "ServiceInfo", FakeServiceInfo)

	device = Device(
		name="Jablotron",
		mac_address="02:00:00:01:02:03",
		project_version="1.0.0",
		manufacturer="Jablotron",
		model="JA-100K",
		friendly_name="Jablotron",
	)

	zeroconf = await device.register_zeroconf(6053)
	assert zeroconf is not None
	assert "api_encryption" not in captured["properties"]
	assert not bool(captured["properties"].get("api_encryption"))

	info = await device.build_device_info_response()
	assert info.uses_password is False