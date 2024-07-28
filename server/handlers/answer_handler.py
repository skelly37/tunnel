import json
import logging

from websockets import WebSocketServerProtocol

from server.handlers.handler import Handler
from server.request_data import RequestData
from server.sessions import sessions


class AnswerHandler(Handler):
    async def handle(self, request_data: RequestData, _: WebSocketServerProtocol) -> None:
        sessions[request_data.session_name]["messages"]["answer"] = request_data.sdp
        if sessions[request_data.session_name]["sender"]:
            await sessions[request_data.session_name]["sender"].send(json.dumps({"action": "answer", "sdp": request_data.sdp}))
            logging.debug("Sent answer to sender")
