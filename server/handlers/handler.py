from abc import (
    ABC,
    abstractmethod,
)

from websockets import WebSocketServerProtocol

from server.request_data import RequestData


class Handler(ABC):
    def __init__(self, action: str) -> None:
        self._action = action

    def should_handle(self, request_data: RequestData) -> bool:
        return request_data.action == self._action

    @abstractmethod
    async def handle(self, request_data: RequestData, websocket: WebSocketServerProtocol) -> None:
        pass
