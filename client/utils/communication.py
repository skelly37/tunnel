import json
import sys

from aiortc import RTCIceCandidate


def rtc_ice_candidate_to_json(candidate: RTCIceCandidate) -> json:
    return {
        "component": candidate.component,
        "foundation": candidate.foundation,
        "ip": candidate.ip,
        "port": candidate.port,
        "priority": candidate.priority,
        "protocol": candidate.protocol,
        "type": candidate.type,
        "relatedAddress": candidate.relatedAddress,
        "relatedPort": candidate.relatedPort,
        "sdpMid": candidate.sdpMid,
        "sdpMLineIndex": candidate.sdpMLineIndex,
        "tcpType": candidate.tcpType,
    }


class FileMetadata:
    def __init__(self, filename: str, filesize: int, checksum: str, should_unzip: bool) -> None:
        self.filename = filename
        self.filesize = filesize
        self.checksum = checksum
        self.should_unzip = should_unzip


class RegisterException(Exception):
    def __init__(self, message: json) -> None:
        print(f"\rRegister error: {message.get('message')}")
        sys.exit(1)


class SessionConfig:
    def __init__(self, server_address: str, chunk_size_bytes: int) -> None:
        self.SERVER_ADDRESS: str = server_address
        self.CHUNK_SIZE_BYTES: int = chunk_size_bytes

    def chunk_size_megabytes(self) -> float:
        return self.CHUNK_SIZE_BYTES / 1024.0 / 1024.0
