"""Bridge hub: owns the de-HA'd ``Jablotron`` instance and re-exposes it."""

from __future__ import annotations

import hashlib
from typing import Any, Callable

from .const import DOMAIN, LOGGER, PartiallyArmingMode
from .core import AlarmControlPanelState, Jablotron


def fixed_mac_address(seed: str) -> str:
	digest = hashlib.md5(seed.encode("utf-8")).digest()
	return "02:00:00:{:02x}:{:02x}:{:02x}".format(digest[0], digest[1], digest[2])


class Hub:

	def __init__(
		self,
		runtime: Any,
		config: dict,
		options: dict,
		settings: Any = None,
		config_entry_id: str = DOMAIN,
	) -> None:
		self.runtime = runtime
		self.config_entry_id = config_entry_id
		self.config = config
		self.options = options
		self.settings = settings
		self.jablotron = Jablotron(runtime, config_entry_id, config, options)

	@property
	def signal_entities_added(self) -> str:
		return self.jablotron.signal_entities_added()

	@property
	def fixed_mac(self) -> str:
		seed = self.config["unique_id"] if "unique_id" in self.config else self.config["serial_port"]
		return fixed_mac_address(seed)

	def subscribe_to_entities_added(self, callback: Callable[[], None]) -> Callable[[], None]:
		return self.runtime.async_listen(self.signal_entities_added, callback)

	async def initialize(self) -> None:
		await self.jablotron.initialize()
		LOGGER.info(
			"Connected to Jablotron %s (serial port %s)",
			self.jablotron.central_unit().model,
			self.jablotron._serial_port,
		)

	def shutdown(self) -> None:
		self.jablotron.shutdown()

	def snapshot(self) -> tuple:
		with self.jablotron._state_lock:
			return (
				dict(self.jablotron.entities_states),
				self.jablotron.last_update_success,
				self.jablotron.in_service_mode,
			)

	def central_unit_model(self) -> str | None:
		try:
			return self.jablotron.central_unit().model
		except AssertionError:
			return None

	def is_code_required_for_arm(self) -> bool:
		return self.jablotron.is_code_required_for_arm()

	def is_code_required_for_disarm(self) -> bool:
		return self.jablotron.is_code_required_for_disarm()

	def partially_arming_mode(self) -> PartiallyArmingMode:
		return self.jablotron.partially_arming_mode()

	def modify_section_state(self, section: int, state: AlarmControlPanelState, code: str | None) -> None:
		self.jablotron.modify_alarm_control_panel_section_state(section, state, code)

	def toggle_pg_output(self, pg_output_number: int, state: str) -> None:
		self.jablotron.toggle_pg_output(pg_output_number, state)