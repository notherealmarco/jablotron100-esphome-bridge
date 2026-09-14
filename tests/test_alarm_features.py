"""The alarm panel must advertise only the arming modes the panel supports.

``partially_arming_mode`` decides how the section's "partially armed" state is
reported (home vs night), so exposing both modes would offer a button that
behaves identically to the other one.
"""
from __future__ import annotations

import pytest

from jablo2esphome.const import PartiallyArmingMode
from jablo2esphome.entities import alarm_supported_features


@pytest.mark.parametrize(
	("mode", "expected_features"),
	[
		pytest.param(PartiallyArmingMode.NIGHT_MODE, 2 | 4, id="night-mode"),
		pytest.param(PartiallyArmingMode.HOME_MODE, 2 | 1, id="home-mode"),
		pytest.param(PartiallyArmingMode.NOT_SUPPORTED, 2, id="not-supported"),
	],
)
def test_alarm_supported_features_follow_partially_arming_mode(
	mode: PartiallyArmingMode,
	expected_features: int,
) -> None:
	assert alarm_supported_features(mode) == expected_features


def test_away_is_always_advertised() -> None:
	for mode in PartiallyArmingMode:
		assert alarm_supported_features(mode) & 2
