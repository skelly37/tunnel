import json
import logging

from websockets import WebSocketServerProtocol

from server.handlers.handler import Handler
from server.request_data import RequestData
from server.sessions import sessions


class OfferHandler(Handler):
    async def handle(self, request_data: RequestData, _: WebSocketServerProtocol) -> None:
        sessions[request_data.session_name]["messages"]["offer"] = request_data.sdp
        if sessions[request_data.session_name]["receiver"]:
            await sessions[request_data.session_name]["receiver"].send(json.dumps({"action": "offer", "sdp": request_data.sdp}))
            logging.debug("Sent offer to receiver")
