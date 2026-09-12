from __future__ import annotations

from aioesphomeapi.api_pb2 import (  # type: ignore
    ListEntitiesSwitchResponse,
    SwitchCommandRequest,
    SwitchStateResponse,
)

from .basic_entity import BasicEntity

class SwitchEntity(BasicEntity):
    DOMAIN = "switch"

    def __init__(
            self,
            *args,
            assumed_state=None,
            **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.assumed_state = assumed_state
        self._state = False
    
    async def build_list_entities_response(self):
        return ListEntitiesSwitchResponse(
            object_id = self.object_id,
            key = self.key,
            name = self.name,
            icon = self.icon,
            entity_category = self.entity_category,
            device_class = self.device_class,
            assumed_state = self.assumed_state,
            device_id = self.device_id,
        )

    async def build_state_response(self):
        return SwitchStateResponse(
            key = self.key,
            state = await self.get_state(),
            device_id = self.device_id,
        )

    async def get_state(self):
        return self._state

    async def set_state(self, val):
        await self.device.log(3, self.DOMAIN, f"[{self.object_id}] Setting state to {val}")
        old_state = self._state
        self._state = val
        if val != old_state:
            await self.notify_state_change()

    async def handle(self, key, message):
        if type(message) == SwitchCommandRequest:
            if message.key == self.key:
                await self.set_state(message.state)