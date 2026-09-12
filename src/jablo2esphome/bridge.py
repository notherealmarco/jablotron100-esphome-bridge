"""Top-level bridge: wires the core + native API server together."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aioesphomeserver import NativeApiServer

from .runtime import BridgeRuntime
from .hub import Hub
from .state_sync import EspDeviceTree, StateSync
from .const import LOGGER

logger = logging.getLogger(__name__)


class JablotronBridge:

	def __init__(self, settings: Any) -> None:
		self.settings = settings
		self.runtime: BridgeRuntime | None = None
		self.hub: Hub | None = None
		self.tree: EspDeviceTree | None = None
		self.state_sync: StateSync | None = None
		self.server: NativeApiServer | None = None

	async def start(self) -> None:
		loop = asyncio.get_running_loop()

		self.runtime = BridgeRuntime(loop, self.settings.store_dir)

		self.hub = Hub(
			self.runtime,
			self.settings.config,
			self.settings.options,
			settings=self.settings,
		)
		await self.hub.initialize()

		self.tree = EspDeviceTree(self.hub)

		self.server = NativeApiServer(
			name="_server",
			port=self.settings.api_port,
			api_version_minor=18,
		)
		self.tree.add_server(self.server)

		self.state_sync = StateSync(self.tree)
		await self.state_sync.start()

		self.tree.device.zeroconf = await self.tree.device.register_zeroconf(self.settings.api_port)
		asyncio.create_task(self.server.run())

		LOGGER.info(
			"Bridge '%s' listening on port %d (%d sub-devices)",
			self.settings.name,
			self.settings.api_port,
			len(self.tree.device.sub_devices),
		)

	async def stop(self) -> None:
		if self.state_sync is not None:
			await self.state_sync.stop()
		if self.tree is not None:
			await self.tree.device.unregister_zeroconf()
		if self.server is not None:
			await self.server.stop()
		if self.hub is not None:
			self.hub.shutdown()
		LOGGER.info("Bridge stopped")