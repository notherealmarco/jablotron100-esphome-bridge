"""Bridge runtime: the object the de-HA'd core receives as its ``hass``.

The core integration only ever calls through ``self._rt`` (see core.py); every
method it needs is implemented here against the bridge event loop and a data
directory for the file-backed store. This keeps the core byte-identical in
behaviour to the Home Assistant version while running standalone.
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, Callable

from .const import LOGGER


class EventBus:

	def __init__(self) -> None:
		self._listeners: dict[str, list[Callable[..., Any]]] = {}

	def async_listen(self, event_name: str, callback: Callable[..., Any]) -> Callable[[], None]:
		listeners = self._listeners.setdefault(event_name, [])
		if callback not in listeners:
			listeners.append(callback)

		def unsubscribe() -> None:
			if callback in listeners:
				listeners.remove(callback)

		return unsubscribe

	def fire(self, event_name: str) -> None:
		# HA callbacks receive the event object; here they receive the event
		# name (single positional argument) so signatures like
		# `def shutdown_event(_)` keep working untouched.
		for callback in list(self._listeners.get(event_name, ())):
			try:
				callback(event_name)
			except Exception:  # noqa: BLE001
				LOGGER.exception("Unhandled error in event listener for %s", event_name)


class Dispatcher:

	def __init__(self) -> None:
		self._listeners: dict[str, list[Callable[[], Any]]] = {}

	def async_listen(self, signal: str, callback: Callable[[], Any]) -> Callable[[], None]:
		listeners = self._listeners.setdefault(signal, [])
		if callback not in listeners:
			listeners.append(callback)

		def unsubscribe() -> None:
			if callback in listeners:
				listeners.remove(callback)

		return unsubscribe

	def _send(self, signal: str) -> None:
		for callback in list(self._listeners.get(signal, ())):
			try:
				callback()
			except Exception:  # noqa: BLE001
				LOGGER.exception("Unhandled error in dispatcher listener for %s", signal)

	def async_dispatcher_send(self, signal: str) -> None:
		self._send(signal)

	def dispatcher_send(self, signal: str) -> None:
		self._send(signal)


class BridgeRuntime:

	def __init__(self, loop: Any, store_dir: Path) -> None:
		self.loop = loop
		self.store_dir = Path(store_dir)
		self.data: dict[str, Any] = {}
		self.bus = EventBus()
		self._dispatcher = Dispatcher()

	def async_add_executor_job(self, func: Callable[..., Any], *args: Any) -> Any:
		return self.loop.run_in_executor(None, func, *args)

	def call_soon_threadsafe(self, callback: Callable[..., Any], *args: Any) -> Any:
		return self.loop.call_soon_threadsafe(callback, *args)

	def async_call_later(self, delay: float, callback: Callable[[datetime.datetime], Any]) -> Any:
		def _run() -> None:
			callback(datetime.datetime.now())

		return self.loop.call_later(delay, _run)

	def device_id_for_identifier(self, identifiers: Any, config_entry_id: str) -> None:
		# No Home Assistant device registry: there is no "main device" reference
		# the bridge needs, so sub-devices are always attached to the root.
		return None

	def async_remove_ignored_device(self, identifiers: Any, config_entry_id: str) -> None:
		# No Home Assistant device registry to clean up.
		return None

	def async_dispatcher_send(self, signal: str) -> None:
		self._dispatcher.async_dispatcher_send(signal)

	def dispatcher_send(self, signal: str) -> None:
		self._dispatcher.dispatcher_send(signal)

	def async_listen(self, signal: str, callback: Callable[[], Any]) -> Callable[[], None]:
		return self._dispatcher.async_listen(signal, callback)