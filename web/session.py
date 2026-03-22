from typing import Optional, Callable, Any, Awaitable

class GameSession:
    def __init__(self):
        self.env = None
        self.mode = None
        self.send_json_cb: Optional[Callable[[dict], Awaitable[None]]] = None
        self.send_state_update_cb: Optional[Callable[[], Awaitable[None]]] = None

    async def broadcast(self, data: dict):
        if self.send_json_cb:
            await self.send_json_cb(data)

    async def state_update(self):
        if self.send_state_update_cb:
            await self.send_state_update_cb()

game_session = GameSession()
