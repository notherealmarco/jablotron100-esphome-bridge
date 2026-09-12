"""Pytest configuration for the bridge.

Unlike the upstream Home Assistant integration, the de-HA'd core has no
``homeassistant`` import, so no module stubbing is needed: the packet tests
below run headless against plain ``jablo2esphome``.
"""
from __future__ import annotations