import asyncio
import json
import logging
import os
from typing import (
    List,
    Optional,
    Tuple,
)

import websockets

from server.handlers import *  # pylint: disable=wildcard-import
from server.request_data import RequestData
from server.sessions import sessions

handlers: List[Handler] = [
    AnswerHandler("answer"),
    CancelHandler("cancel"),
    CandidateHandler("candidate"),
    OfferHandler("offer"),
    RegisterHandler("register"),
]


def get_role_and_session_name(websocket: websockets.WebSocketServerProtocol) -> Tuple[Optional[str], Optional[str]]:
    for name, session in sessions.items():
        for role, socket in session.items():
            if socket == websocket:
                return role, name

    return None, None


def cleanup(websocket: websockets.WebSocketServerProtocol) -> None:
    role, session_name = get_role_and_session_name(websocket)
    if role and session_name:
        sessions[session_name][role] = None
        logging.debug(f"Unregistered {role} from session {session_name}")

        if sessions[session_name]["sender"] is None and sessions[session_name]["receiver"] is None:
            del sessions[session_name]
            logging.debug(f"Cleared session {session_name}")


async def server_loop(websocket: websockets.WebSocketServerProtocol) -> None:
    try:
        async for message in websocket:
            request_data = RequestData(json.loads(message))

            logging.info(f"[{request_data.session_name}] Received action: {request_data.action}")

            handled = False

            for h in handlers:
                if h.should_handle(request_data):
                    await h.handle(request_data, websocket)
                    handled = True
                    break

            if not handled:
                await websocket.send("Invalid message")

    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.error(f"Error: {e}")
    finally:
        cleanup(websocket)


if __name__ == "__main__":
    start_server = websockets.serve(server_loop, "0.0.0.0", int(os.environ.get("SERVER_PORT", 25565)))

    logging.basicConfig(level=logging.INFO)
    logging.info("Signaling server started")
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
