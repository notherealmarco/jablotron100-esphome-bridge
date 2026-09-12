from __future__ import annotations

from aioesphomeapi.api_pb2 import (  # type: ignore
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_NONE,
    STATE_CLASS_TOTAL_INCREASING,
    SensorStateResponse,
    ListEntitiesSensorResponse,
)

from . import BasicEntity

_STATE_CLASS_VALUES = {
    "measurement": STATE_CLASS_MEASUREMENT,
    "total_increasing": STATE_CLASS_TOTAL_INCREASING,
}

class SensorEntity(BasicEntity):
    DOMAIN = "sensor"

    def __init__(
            self,
            *args,
            unit_of_measurement=None,
            accuracy_decimals=None,
            state_class=None,
            **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.unit_of_measurement = unit_of_measurement
        self.accuracy_decimals = accuracy_decimals
        self.state_class = state_class
        self._state = 0.0

    async def build_list_entities_response(self):
        return ListEntitiesSensorResponse(
            object_id = self.object_id,
            name = self.name,
            key = self.key,
            icon = self.icon,
            unit_of_measurement = self.unit_of_measurement,
            accuracy_decimals = self.accuracy_decimals,
            device_class = self.device_class,
            state_class = _STATE_CLASS_VALUES.get(self.state_class, STATE_CLASS_NONE),
            entity_category = self.entity_category,
            device_id = self.device_id,
        )

    async def build_state_response(self):
        return SensorStateResponse(
            key = self.key,
            state = await self.get_state(),
            device_id = self.device_id,
        )

    async def get_state(self):
        return self._state

    async def set_state(self, val):
        await self.device.log(3, self.DOMAIN, f"[{self.object_id}] Setting value to {val}")
        old_state = self._state
        self._state = val
        if val != old_state:
            await self.notify_state_change()