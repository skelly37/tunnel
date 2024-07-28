import json
import logging

from websockets import WebSocketServerProtocol

from server.handlers.handler import Handler
from server.request_data import RequestData
from server.sessions import sessions


class CancelHandler(Handler):
    async def handle(self, request_data: RequestData, _: WebSocketServerProtocol) -> None:
        if "sender" in sessions[request_data.session_name] and sessions[request_data.session_name]["sender"]:
            await sessions[request_data.session_name]["sender"].send(json.dumps({"action": "cancel"}))
            logging.debug(f"Notified sender to cancel session {request_data.session_name}")
