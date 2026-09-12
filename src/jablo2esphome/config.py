"""Bridge configuration: YAML file -> core ``config`` / ``options``.

The two dicts handed to ``Jablotron`` use exactly the CONF_* keys from
const.py so the de-HA'd core keeps working untouched. Everything else the
bridge itself needs (device name, native API port, store directory)
lives in ``Settings``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .const import (
	AUTODETECT_SERIAL_PORT,
	LOGGER,
	MAX_DEVICES,
	MAX_PG_OUTPUTS,
	DeviceType,
	PartiallyArmingMode,
)

DEFAULT_SERIAL_PORT: str = AUTODETECT_SERIAL_PORT
DEFAULT_NUMBER_OF_DEVICES: int = 70
DEFAULT_NUMBER_OF_PG_OUTPUTS: int = 0
DEFAULT_PARTIALLY_ARMING_MODE = PartiallyArmingMode.NIGHT_MODE.value

DEFAULT_NAME: str = "Jablotron"
DEFAULT_API_PORT: int = 6053
DEFAULT_STORE_DIR: str = "./data"


class ConfigValidationError(Exception):
	pass


def _as_int(value, key: str, minimum: int, maximum: int) -> int:
	if not isinstance(value, int) or isinstance(value, bool):
		raise ConfigValidationError(f"{key} must be an integer, got {value!r}")
	if value < minimum or value > maximum:
		raise ConfigValidationError(f"{key} must be between {minimum} and {maximum}, got {value}")
	return value


def _as_bool(value, key: str) -> bool:
	if not isinstance(value, bool):
		raise ConfigValidationError(f"{key} must be a boolean, got {value!r}")
	return value


def _as_device_types(value, key: str, count: int) -> list:
	if value is None:
		value = [DeviceType.EMPTY.value] * count
	if not isinstance(value, list):
		raise ConfigValidationError(f"{key} must be a list of device types")

	device_types = []
	for index, entry in enumerate(value, start=1):
		if isinstance(entry, DeviceType):
			device_types.append(entry)
		elif isinstance(entry, str):
			try:
				device_types.append(DeviceType(entry))
			except ValueError as error:
				raise ConfigValidationError(
					f"{key}[{index}] is not a valid device type: {entry!r}"
				) from error
		else:
			raise ConfigValidationError(f"{key}[{index}] must be a device type name")

	if len(device_types) < count:
		device_types.extend([DeviceType.EMPTY] * (count - len(device_types)))
	return device_types


def _parse_devices(section: dict) -> list:
	value = section.get("devices")
	number_of_devices = _as_int(
		section.get("number_of_devices", DEFAULT_NUMBER_OF_DEVICES),
		"number_of_devices",
		1,
		MAX_DEVICES,
	)
	return _as_device_types(value, "devices", number_of_devices)


@dataclass
class BridgeConfig:
	config: dict
	options: dict
	name: str = DEFAULT_NAME
	api_port: int = DEFAULT_API_PORT
	store_dir: Path = field(default_factory=lambda: Path(DEFAULT_STORE_DIR))


def load_config(path: Path) -> BridgeConfig:
	LOGGER.debug("Loading configuration from %s", path)

	try:
		with open(path, encoding="utf-8") as handle:
			raw = yaml.safe_load(handle)
	except FileNotFoundError as error:
		raise ConfigValidationError(f"Configuration file not found: {path}") from error
	except yaml.YAMLError as error:
		raise ConfigValidationError(f"Could not parse {path}: {error}") from error

	if raw is None:
		raw = {}
	if not isinstance(raw, dict):
		raise ConfigValidationError(f"Configuration file {path} must contain a YAML mapping")

	serial_port = raw.get("serial_port", DEFAULT_SERIAL_PORT)
	if not isinstance(serial_port, str) or not serial_port:
		raise ConfigValidationError("serial_port must be a non-empty string or 'auto'")

	alarm_password = raw.get("alarm_password")
	if not isinstance(alarm_password, str) or not alarm_password:
		raise ConfigValidationError(
			"alarm_password (the Jablotron master/installer code) must be set"
		)

	unique_id = raw.get("unique_id")
	if unique_id is not None and (not isinstance(unique_id, str) or not unique_id):
		raise ConfigValidationError("unique_id must be a non-empty string when set")

	number_of_pg_outputs = _as_int(
		raw.get("number_of_pg_outputs", DEFAULT_NUMBER_OF_PG_OUTPUTS),
		"number_of_pg_outputs",
		0,
		MAX_PG_OUTPUTS,
	)

	devices = _parse_devices(raw)
	device_types = [device.value for device in devices]

	config = {
		"serial_port": serial_port,
		"password": alarm_password,
		"number_of_devices": len(device_types),
		"devices": device_types,
		"number_of_pg_outputs": number_of_pg_outputs,
	}
	if unique_id is not None:
		config["unique_id"] = unique_id

	partially_arming_mode = raw.get("partially_arming_mode", DEFAULT_PARTIALLY_ARMING_MODE)
	if not isinstance(partially_arming_mode, str):
		raise ConfigValidationError("partially_arming_mode must be a string")
	try:
		PartiallyArmingMode(partially_arming_mode)
	except ValueError as error:
		raise ConfigValidationError(
			f"partially_arming_mode must be one of {', '.join(member.value for member in PartiallyArmingMode)}"
		) from error

	options = {
		"require_code_to_arm": _as_bool(raw.get("require_code_to_arm", False), "require_code_to_arm"),
		"require_code_to_disarm": _as_bool(raw.get("require_code_to_disarm", True), "require_code_to_disarm"),
		"partially_arming_mode": partially_arming_mode,
		"enable_debugging": _as_bool(raw.get("enable_debugging", False), "enable_debugging"),
		"log_all_incoming_packets": _as_bool(raw.get("log_all_incoming_packets", False), "log_all_incoming_packets"),
		"log_all_outcoming_packets": _as_bool(raw.get("log_all_outcoming_packets", False), "log_all_outcoming_packets"),
		"log_sections_packets": _as_bool(raw.get("log_sections_packets", False), "log_sections_packets"),
		"log_pg_outputs_packets": _as_bool(raw.get("log_pg_outputs_packets", False), "log_pg_outputs_packets"),
		"log_devices_packets": _as_bool(raw.get("log_devices_packets", False), "log_devices_packets"),
	}

	name = raw.get("name", DEFAULT_NAME)
	if not isinstance(name, str) or not name:
		raise ConfigValidationError("name must be a non-empty string")

	api_port = _as_int(raw.get("api_port", DEFAULT_API_PORT), "api_port", 1, 65535)

	store_dir = Path(raw.get("store_dir", DEFAULT_STORE_DIR))

	return BridgeConfig(
		config=config,
		options=options,
		name=name,
		api_port=api_port,
		store_dir=store_dir,
	)