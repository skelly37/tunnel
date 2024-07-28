import json
import logging

from websockets import WebSocketServerProtocol

from server.handlers.handler import Handler
from server.request_data import RequestData
from server.sessions import sessions


class RegisterHandler(Handler):
    async def handle(self, request_data: RequestData, websocket: WebSocketServerProtocol) -> None:
        if request_data.session_name in sessions and sessions[request_data.session_name][request_data.role] is not None:
            await websocket.send(json.dumps({"status": "error", "message": f"{request_data.role} already registered in session {request_data.session_name}"}))
            logging.info(f"Failed to register {request_data.role} in session {request_data.session_name}: already registered")
            return

        try:
            await {"sender": self.__register_sender, "receiver": self.__register_receiver}[request_data.role](request_data, websocket)
        except KeyError as e:
            raise KeyError("Unknown sender role") from e

    @staticmethod
    async def __register_receiver(request_data: RequestData, websocket: WebSocketServerProtocol) -> None:
        if request_data.session_name not in sessions:
            await websocket.send(json.dumps({"status": "error", "message": f"Session {request_data.session_name} does not exist"}))
            await websocket.close()
            logging.info(f"Failed to register receiver: session {request_data.session_name} does not exist")
            return

        sessions[request_data.session_name][request_data.role] = websocket

        await websocket.send(json.dumps({"status": "registered"}))
        logging.info(f"Registered {request_data.role} in session {request_data.session_name}")

        await websocket.send(json.dumps({"action": "metadata", "metadata": sessions[request_data.session_name]["metadata"]}))
        logging.debug("Sent metadata to receiver")

        if sessions[request_data.session_name]["messages"]["offer"]:
            await websocket.send(json.dumps({"action": "offer", "sdp": sessions[request_data.session_name]["messages"]["offer"]}))
            logging.debug("Sent stored offer to receiver")

    @staticmethod
    async def __register_sender(request_data: RequestData, websocket: WebSocketServerProtocol) -> None:
        sessions[request_data.session_name] = {
            "sender": None,
            "receiver": None,
            "messages": {"offer": None, "answer": None, "candidates": []},
            "metadata": request_data.metadata,
        }

        sessions[request_data.session_name][request_data.role] = websocket

        await websocket.send(json.dumps({"status": "registered"}))
        logging.info(f"Registered {request_data.role} in session {request_data.session_name}")
