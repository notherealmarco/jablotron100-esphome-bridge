"""jablo2esphome command line entry point."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

from .const import LOGGER, VERSION
from .bridge import JablotronBridge
from .config import ConfigValidationError, load_config
from .core import SerialPortNotDetected


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		prog="jablo2esphome",
		description="Expose a Jablotron 100 alarm system to Home Assistant as an ESPHome-native device.",
	)
	parser.add_argument("config", nargs="?", default="config.yaml", help="Path to the YAML configuration file (default: config.yaml)")
	parser.add_argument("--check", action="store_true", help="Validate the configuration and exit")
	parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Logging level (default: INFO)")
	parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
	return parser.parse_args(argv)


def _validate_serial_port(config: dict) -> None:
	serial_port = config["serial_port"]
	if serial_port == "auto":
		return

	import os

	if not os.path.exists(serial_port):
		raise ConfigValidationError(
			f"Configured serial_port '{serial_port}' does not exist. "
			"Use 'auto' for autodetection or fix the device path."
		)


def _print_summary(settings) -> None:
	print("Configuration OK:")
	print("  name:                  {}".format(settings.name))
	print("  serial_port:           {}".format(settings.config["serial_port"]))
	print("  number_of_devices:     {}".format(settings.config["number_of_devices"]))
	print("  number_of_pg_outputs:  {}".format(settings.config["number_of_pg_outputs"]))
	print("  unique_id:             {}".format(settings.config.get("unique_id", "<derived> <serial_port>")))
	print("  api_port:              {}".format(settings.api_port))
	print("  store_dir:             {}".format(settings.store_dir))


def _check(config_path: Path) -> int:
	try:
		settings = load_config(config_path)
		_validate_serial_port(settings.config)
		settings.store_dir.mkdir(parents=True, exist_ok=True)
	except ConfigValidationError as error:
		print(f"ERROR: {error}", file=sys.stderr)
		return 1

	_print_summary(settings)
	return 0


async def _async_run(settings) -> None:
	loop = asyncio.get_running_loop()

	if settings.config["serial_port"] != "auto":
		_validate_serial_port(settings.config)

	stop_event = asyncio.Event()

	def _request_stop() -> None:
		stop_event.set()

	for sig in (signal.SIGTERM, signal.SIGINT):
		loop.add_signal_handler(sig, _request_stop)

	bridge = JablotronBridge(settings)
	try:
		await bridge.start()
	except SerialPortNotDetected as error:
		LOGGER.error("%s", error)
		return
	except Exception:  # noqa: BLE001
		LOGGER.exception("Bridge failed to start")
		return

	await stop_event.wait()

	for sig in (signal.SIGTERM, signal.SIGINT):
		loop.remove_signal_handler(sig)

	await bridge.stop()


def main(argv: list[str] | None = None) -> int:
	args = _parse_args(argv)

	logging.basicConfig(
		level=getattr(logging, args.log_level),
		format="%(asctime)s %(levelname)s %(name)s: %(message)s",
	)

	config_path = Path(args.config)

	if args.check:
		return _check(config_path)

	try:
		settings = load_config(config_path)
	except ConfigValidationError as error:
		LOGGER.error("%s", error)
		return 1

	try:
		asyncio.run(_async_run(settings))
	except KeyboardInterrupt:
		pass

	return 0


if __name__ == "__main__":
	sys.exit(main())