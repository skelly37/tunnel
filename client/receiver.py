import asyncio
import json
from math import (
    ceil,
    floor,
)
import os
from typing import (
    List,
    Optional,
    Union,
)

from aiortc import (
    RTCDataChannel,
    RTCIceCandidate,
    RTCPeerConnection,
    RTCSessionDescription,
)
import websockets

from client.utils.communication import (
    FileMetadata,
    RegisterException,
    SessionConfig,
    rtc_ice_candidate_to_json,
)
from client.utils.file import (
    decompress_files,
    get_file_checksum,
    get_human_readable_file_size,
)


def save_file(file_path: str, chunks: List[bytes]) -> None:
    with open(file_path, "wb") as file:
        for chunk in chunks:
            file.write(chunk)


class Receiver:
    def __init__(self, session_name: str, max_ram_mb: int, session_config: SessionConfig) -> None:
        self.__session_name: str = session_name
        self.__chunks_per_part: int = floor(max_ram_mb / session_config.chunk_size_megabytes())
        self.__session_config: SessionConfig = session_config

    async def __call__(self) -> None:
        async with websockets.connect(self.__session_config.SERVER_ADDRESS) as self.__websocket:
            await self.__register()
            await self.__get_file_metadata()

            if self.__does_user_want_to_receive_transfer():
                await self.__prepare_rtc_connection()
                await self.__handle_incoming_messages()
            else:
                await self.__websocket.send(json.dumps({"action": "cancel", "session": self.__session_name}))
                await self.__websocket.close()
                print("User declined the file transfer.")

    async def __register(self) -> None:
        print("Registering receiver in the coordinating server...", end="")
        await self.__websocket.send(json.dumps({"action": "register", "role": "receiver", "session": self.__session_name}))
        response = await self.__websocket.recv()
        response_data = json.loads(response)

        if response_data.get("status") == "error":
            await self.__websocket.close()
            raise RegisterException(response_data)

        print("\rReceiver registered successfully, connecting to the sender...")

    async def __get_file_metadata(self) -> None:
        metadata_response = await self.__websocket.recv()
        metadata = json.loads(metadata_response)
        self.__file_metadata = FileMetadata(
            filename=metadata["metadata"]["filename"],
            filesize=metadata["metadata"]["filesize"],
            checksum=metadata["metadata"]["checksum"],
            should_unzip=metadata["metadata"]["should_unzip"],
        )

    def __does_user_want_to_receive_transfer(self) -> bool:
        maybe_zipped_message = f", archive will be unpacked into directory: {self.__session_name}" if self.__file_metadata.should_unzip else ""
        maybe_exists_message = " (will overwrite an existing file in the current working directory) " if os.path.exists(self.__file_metadata.filename) else ""
        incoming_message = f"Incoming file: {self.__file_metadata.filename} ({get_human_readable_file_size(self.__file_metadata.filesize)}{maybe_zipped_message}). Accept transfer{maybe_exists_message}? [Y/n]"  # pylint: disable=line-too-long
        print(incoming_message, end=" ")
        return input().lower().strip() in {"y", ""}  # pylint: disable=bad-builtin

    async def __prepare_rtc_connection(self) -> None:
        self.__rtc_connection: RTCPeerConnection = RTCPeerConnection()

        @self.__rtc_connection.on("icecandidate")
        async def on_icecandidate(candidate: Optional[RTCIceCandidate]) -> None:
            if candidate:
                await self.__websocket.send(
                    json.dumps({
                        "action": "candidate",
                        "target": "sender",
                        "candidate": rtc_ice_candidate_to_json(candidate),
                        "session": self.__session_name,
                    }),
                )

        @self.__rtc_connection.on("datachannel")
        def on_datachannel(channel: RTCDataChannel) -> None:
            chunks = []
            parts = []
            self.__received_count = 0
            self.__chunks_count = ceil(self.__file_metadata.filesize / self.__session_config.CHUNK_SIZE_BYTES)

            @channel.on("message")
            def on_message(message: Union[str, bytes]) -> None:
                self.__received_count += 1
                progress = (self.__received_count * 100) / self.__chunks_count
                chunks.append(message)
                print(f"\rProgress: {progress:.3f}% ({get_human_readable_file_size(len(chunks) * self.__session_config.CHUNK_SIZE_BYTES)})          ", end="")

                if len(chunks) == self.__chunks_per_part or self.__received_count == self.__chunks_count:
                    part_filename = f"{self.__file_metadata.filename}.part{len(parts)}"
                    save_file(part_filename, chunks)
                    parts.append(part_filename)
                    chunks.clear()

                channel.send("ack")
                if self.__received_count == self.__chunks_count:
                    self.__merge_file_parts(parts)
                    self.__finalize_transfer(channel)
                    asyncio.ensure_future(self.__websocket.close())
                    if self.__file_metadata.should_unzip:
                        decompress_files(self.__file_metadata.filename, self.__session_name, delete_input=True)

    def __finalize_transfer(self, channel: RTCDataChannel) -> None:
        checksum = get_file_checksum(self.__file_metadata.filename)
        if checksum != self.__file_metadata.checksum:
            print("File transfer failed: checksum mismatch")
            channel.send("Error: checksum mismatch")
        else:
            print("File transfer finished.")
            channel.send("Finished")

    async def __handle_incoming_messages(self) -> None:
        async for message in self.__websocket:
            data = json.loads(message)
            action = data.get("action")

            if action == "offer":
                await self.__handle_offer(data)
            elif action == "candidate":
                await self.__handle_candidate(data)

    async def __handle_offer(self, data: json) -> None:
        offer = RTCSessionDescription(sdp=data["sdp"], type="offer")
        await self.__rtc_connection.setRemoteDescription(offer)

        answer = await self.__rtc_connection.createAnswer()
        await self.__rtc_connection.setLocalDescription(answer)

        await self.__websocket.send(json.dumps({"action": "answer", "sdp": self.__rtc_connection.localDescription.sdp, "session": self.__session_name}))

    async def __handle_candidate(self, data: json) -> None:
        candidate = RTCIceCandidate(**data["candidate"])
        await self.__rtc_connection.addIceCandidate(candidate)

    def __merge_file_parts(self, parts: List[str]) -> None:
        print("\nAll data received, finalizing...")

        if len(parts) == 1:
            if os.path.exists(self.__file_metadata.filename):
                os.remove(self.__file_metadata.filename)
            os.rename(parts[0], self.__file_metadata.filename)
            return

        with open(self.__file_metadata.filename, "wb") as output_file:
            for part in parts:
                with open(part, "rb") as input_file:
                    output_file.write(input_file.read())

                os.remove(part)
