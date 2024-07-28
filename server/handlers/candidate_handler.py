import json
import logging

from websockets import WebSocketServerProtocol

from server.handlers.handler import Handler
from server.request_data import RequestData
from server.sessions import sessions


class CandidateHandler(Handler):
    async def handle(self, request_data: RequestData, _: WebSocketServerProtocol) -> None:
        sessions[request_data.session_name]["messages"]["candidates"].append({"target": request_data.target, "candidate": request_data.candidate})
        if sessions[request_data.session_name][request_data.target]:
            await sessions[request_data.session_name][request_data.target].send(json.dumps({"action": "candidate", "candidate": request_data.candidate}))
            logging.debug(f"Sent candidate to {request_data.target}")
