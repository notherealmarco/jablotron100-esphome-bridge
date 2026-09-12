"""Poll the de-HA'd core and publish state changes to the native API clients."""

from __future__ import annotations

import asyncio
from typing import Any

from .const import EVENT_WRONG_CODE, EventLoginType, LOGGER, VERSION
from .entities import build_entity
from .mapping import build_sub_devices

_MISSING = object()

POLL_INTERVAL = 0.5

# control.id of the login event entity (created by _create_central_unit_sensors).
EVENT_LOGIN_CONTROL_ID = "login"


class EspDeviceTree:

	def __init__(self, hub: Any) -> None:
		from aioesphomeserver import Device

		settings = hub.settings
		self.hub = hub
		self.device = Device(
			name=settings.name,
			mac_address=hub.fixed_mac,
			model=hub.central_unit_model() or "Jablotron 100",
			manufacturer="Jablotron",
			friendly_name=settings.name,
			project_name="jablo2esphome",
			project_version=VERSION,
			uses_password=False,
			api_version_minor=18,
			sub_devices=build_sub_devices(hub.jablotron),
		)
		self._entities: dict = {}
		self._by_object_id: dict = {}

	def build(self) -> None:
		for entity_type, entities in self.hub.jablotron.entities.items():
			for control_id, control in entities.items():
				if control_id in self._entities:
					continue
				entity = build_entity(self.hub, control, entity_type)
				if entity is None:
					continue
				LOGGER.debug("Adding native API entity %s (%s)", control_id, entity.DOMAIN)
				self.device.add_entity(entity)
				self._entities[control_id] = entity
				self._by_object_id[entity.object_id] = entity

	def get(self, control_id: str) -> Any:
		return self._entities.get(control_id)

	def add_server(self, server: Any) -> None:
		self.device.add_entity(server)

	@property
	def sub_devices(self) -> list:
		return build_sub_devices(self.hub.jablotron)


class StateSync:

	def __init__(self, tree: EspDeviceTree) -> None:
		self._tree = tree
		self._last_states: dict = {}
		self._poll_task: asyncio.Task | None = None
		self._unsub_wrong_code: Any = None
		self._unsub_entities_added: Any = None

	async def start(self) -> None:
		self._unsub_wrong_code = self._tree.hub.runtime.bus.async_listen(
			EVENT_WRONG_CODE, self._on_wrong_code
		)
		self._unsub_entities_added = self._tree.hub.runtime.async_listen(
			self._tree.hub.signal_entities_added, self._on_entities_added
		)
		await self._sync()
		self._poll_task = asyncio.create_task(self._poll())

	async def stop(self) -> None:
		if self._poll_task is not None:
			self._poll_task.cancel()
			try:
				await self._poll_task
			except asyncio.CancelledError:
				pass
			self._poll_task = None
		if self._unsub_wrong_code is not None:
			self._unsub_wrong_code()
			self._unsub_wrong_code = None
		if self._unsub_entities_added is not None:
			self._unsub_entities_added()
			self._unsub_entities_added = None

	def _on_wrong_code(self, _event: Any) -> None:
		entity = self._tree.get(EVENT_LOGIN_CONTROL_ID)
		if entity is None:
			return
		loop = self._tree.hub.runtime.loop
		loop.call_soon_threadsafe(
			asyncio.ensure_future,
			entity.publish_event(EventLoginType.WRONG_CODE.value),
		)

	def _on_entities_added(self) -> None:
		# May be signalled from the core worker thread; hop onto the loop.
		loop = self._tree.hub.runtime.loop
		loop.call_soon_threadsafe(asyncio.ensure_future, self._sync())

	async def _poll(self) -> None:
		while True:
			await asyncio.sleep(POLL_INTERVAL)
			await self._sync()

	async def _sync(self) -> None:
		self._tree.build()

		states, _available, _in_service_mode = self._tree.hub.snapshot()

		for control_id, state in states.items():
			entity = self._tree.get(control_id)
			if entity is None:
				continue
			set_state = getattr(entity, "set_state", None)
			if set_state is None:
				continue
			if self._last_states.get(control_id, _MISSING) == state:
				continue
			self._last_states[control_id] = state
			try:
				await set_state(state)
			except Exception:  # noqa: BLE001
				LOGGER.exception("Failed to publish state for %s", control_id)