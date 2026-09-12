"""JablotronStore must match Home Assistant's Store surface.

``async_delay_save`` is a *synchronous* scheduling method (HA's is too): the
core calls it fire-and-forget from the event loop. Making it a coroutine left
the returned object unawaited ("coroutine ... was never awaited").
"""
from __future__ import annotations

import asyncio
import json

import pytest

from jablo2esphome.storage import JablotronStore


@pytest.mark.asyncio
async def test_async_delay_save_returns_none(tmp_path) -> None:
	store = JablotronStore(tmp_path / "store.json", 1)

	result = store.async_delay_save(lambda: {"value": 1}, delay=0.01)

	assert result is None
	assert not asyncio.iscoroutine(result)


@pytest.mark.asyncio
async def test_async_delay_save_persists_last_value(tmp_path) -> None:
	path = tmp_path / "store.json"
	store = JablotronStore(path, 1)

	# Two rapid fire-and-forget saves coalesce into one write of the last data.
	store.async_delay_save(lambda: {"value": 1}, delay=0.01)
	store.async_delay_save(lambda: {"value": 2}, delay=0.01)

	await asyncio.sleep(0.1)

	payload = json.loads(path.read_text(encoding="utf-8"))
	assert payload == {"version": 1, "data": {"value": 2}}


@pytest.mark.asyncio
async def test_async_save_round_trip(tmp_path) -> None:
	path = tmp_path / "store.json"
	store = JablotronStore(path, 1)

	await store.async_save({"hello": "world"})

	fresh = JablotronStore(path, 1)
	assert await fresh.async_load() == {"hello": "world"}
