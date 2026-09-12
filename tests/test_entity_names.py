"""Entity display names must be distinct per entity type on a shared device.

Regression: ``entity_display_name`` used to return the device name for every
entity whose control had no explicit name, so ``device_sensor_4`` and
``device_problem_sensor_4`` (and the signal sensor) all came out as
"Door opening detector (device 4)". Home Assistant prefixes the (sub-)device
name itself, so identical entity names collapse/duplicate entities.
"""
from __future__ import annotations

from types import SimpleNamespace

from jablo2esphome.const import EntityType
from jablo2esphome.mapping import entity_display_name


def _device():
	return SimpleNamespace(
		id="device_4",
		name="Door opening detector (device {deviceNo})",
		translation_placeholders={"deviceNo": "4"},
	)


def _control(name=None, hass_device=None):
	return SimpleNamespace(name=name, hass_device=hass_device)


def test_entity_names_are_distinct_per_type_on_one_device():
	control = _control(hass_device=_device())

	names = {
		entity_display_name(control, EntityType.DEVICE_STATE_DOOR),
		entity_display_name(control, EntityType.PROBLEM),
		entity_display_name(control, EntityType.SIGNAL_STRENGTH),
		entity_display_name(control, EntityType.BATTERY_LEVEL),
	}
	assert names == {"Door", "Problem", "Signal strength", "Battery level"}
	assert len(names) == 4


def test_explicit_control_name_wins():
	control = _control(name="Custom name", hass_device=_device())
	assert entity_display_name(control, EntityType.SIGNAL_STRENGTH) == "Custom name"


def test_root_entity_uses_type_name():
	control = _control(hass_device=None)
	assert entity_display_name(control, EntityType.EVENT_LOGIN) == "Login"


def test_alarm_panel_uses_device_name():
	control = _control(hass_device=_device())
	assert entity_display_name(control, EntityType.ALARM_CONTROL_PANEL) == "Door opening detector (device 4)"
