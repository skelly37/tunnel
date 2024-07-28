import json
from typing import Optional


class RequestData:
    def __init__(self, data: json) -> None:
        self.session_name: str = data.get("session")
        self.action: str = data.get("action")
        self.role: str = data.get("role")
        self.metadata: Optional[json] = data.get("metadata")
        self.target: Optional[str] = data.get("target")
        self.sdp: Optional[str] = data.get("sdp")
        self.candidate: Optional[str] = data.get("candidate")
