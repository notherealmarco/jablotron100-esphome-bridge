"""File-backed persistence with the same surface as Home Assistant's Store.

The de-HA'd core only touches ``data``, ``async_load()`` and
``async_delay_save(callback)``; this implements those against a JSON file in
the runtime's data directory so entity states and detected device data survive
restarts, exactly like the Home Assistant integration's ``JablotronStore``.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Callable

from .const import DOMAIN, LOGGER


class JablotronStore:

	def __init__(self, path: Path, version: int) -> None:
		self._path = path
		self._version = version
		self.data: dict = {}
		self._loaded = False
		self._load_lock = asyncio.Lock()
		self._delay_save_handle: asyncio.TimerHandle | None = None

	async def async_load(self) -> dict:
		async with self._load_lock:
			if not self._loaded:
				loaded = await asyncio.to_thread(self._read_sync)
				if loaded is not None:
					self.data.update(loaded)
					LOGGER.debug("Loaded %d keys from %s", len(loaded), self._path)
				self._loaded = True
		return self.data

	async def async_save(self, data: dict) -> None:
		payload = {"version": self._version, "data": data}
		await asyncio.to_thread(self._write_sync, payload)

	def async_delay_save(self, data_func: Callable[[], dict], delay: float = 1.0) -> None:
		"""Schedule a save after ``delay`` seconds, coalescing pending saves.

		Synchronous on purpose, matching Home Assistant's
		``Store.async_delay_save``: the core invokes it fire-and-forget from the
		event loop (via ``call_soon_threadsafe``) and never awaits it. Making it
		a coroutine left the returned object unawaited.
		"""
		loop = asyncio.get_running_loop()

		if self._delay_save_handle is not None:
			self._delay_save_handle.cancel()

		self._delay_save_handle = loop.call_later(delay, self._run_delayed_save, data_func)

	def _run_delayed_save(self, data_func: Callable[[], dict]) -> None:
		self._delay_save_handle = None

		async def save() -> None:
			try:
				await self.async_save(data_func())
			except (OSError, ValueError) as error:
				LOGGER.error("Could not save store %s: %s", self._path, error)

		asyncio.get_running_loop().create_task(save())

	def _read_sync(self) -> dict | None:
		try:
			with open(self._path, encoding="utf-8") as handle:
				payload = json.load(handle)
		except FileNotFoundError:
			return None
		except (OSError, ValueError) as error:
			LOGGER.error("Could not read store %s: %s", self._path, error)
			return None

		if not isinstance(payload, dict) or payload.get("version") != self._version:
			return None

		data = payload.get("data")
		return data if isinstance(data, dict) else None

	def _write_sync(self, payload: dict) -> None:
		os.makedirs(self._path.parent, exist_ok=True)
		temp_path = self._path.with_suffix(".json.tmp")
		with open(temp_path, "w", encoding="utf-8") as handle:
			json.dump(payload, handle, indent=2, sort_keys=True)
		os.replace(temp_path, self._path)


def async_get_store(runtime, version: int) -> JablotronStore:
	key = "{}_store_{}".format(DOMAIN, version)
	store = runtime.data.get(key)
	if store is None:
		store = JablotronStore(Path(runtime.store_dir) / "{}_v{}.json".format(DOMAIN, version), version)
		runtime.data[key] = store
	return store