import asyncio
import json
from math import ceil
import os
import random
import tempfile
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
    compress_files,
    get_file_checksum,
    get_human_readable_file_size,
)


class Sender:
    def __init__(self, file_paths: List[str], session_config: SessionConfig) -> None:
        self.__session_config: SessionConfig = session_config

        if len(file_paths) == 1 and os.path.isfile(file_paths[0]):
            self.__is_file_temporary: bool = False
            self.__FILE_PATH: str = file_paths[0]
            self.__FILE_METADATA: FileMetadata = FileMetadata(
                filename=os.path.basename(file_paths[0]),
                filesize=os.path.getsize(file_paths[0]),
                checksum=get_file_checksum(file_paths[0]),
                should_unzip=False,
            )
        else:
            print("Multiple files or directory detected: compressing...")
            self.__is_file_temporary: bool = True
            self.__FILE_PATH: str = f"{tempfile.NamedTemporaryFile(delete=False).name}.zip"  # pylint: disable=consider-using-with
            compress_files(file_paths, self.__FILE_PATH)
            print("Compression finished")
            self.__FILE_METADATA: FileMetadata = FileMetadata(
                filename=os.path.basename(self.__FILE_PATH),
                filesize=os.path.getsize(self.__FILE_PATH),
                checksum=get_file_checksum(self.__FILE_PATH),
                should_unzip=True,
            )

        print(f"Sending {self.__FILE_METADATA.filename} ({get_human_readable_file_size(self.__FILE_METADATA.filesize)})")
        self.__did_receiver_finish: asyncio.Event = asyncio.Event()
        self.__ack_received: asyncio.Event = asyncio.Event()
        self.__ack_received.set()

    def __del__(self):
        self.__cleanup()

    def __cleanup(self) -> None:
        self.__did_receiver_finish.set()
        self.__ack_received.set()
        if self.__is_file_temporary and os.path.exists(self.__FILE_PATH):
            os.remove(self.__FILE_PATH)

    async def __call__(self) -> None:
        try:
            async with websockets.connect(self.__session_config.SERVER_ADDRESS) as self.__websocket:
                await self.__register()
                await self.__prepare_rtc_connection()
                await self.__prepare_data_channel()
                await self.__send_offer()
                await self.__handle_incoming_messages()
        finally:
            self.__cleanup()

    async def __register(self) -> None:
        print("Registering session in the coordinating server...", end="")
        valid_id_generated = False

        while not valid_id_generated:
            self.__session_name = self.__generate_random_session_name()
            already_taken_message = f"sender already registered in session {self.__session_name}"

            await self.__websocket.send(
                json.dumps({
                    "action": "register",
                    "role": "sender",
                    "session": self.__session_name,
                    "metadata": {
                        "filename": self.__FILE_METADATA.filename,
                        "filesize": self.__FILE_METADATA.filesize,
                        "checksum": self.__FILE_METADATA.checksum,
                        "should_unzip": self.__FILE_METADATA.should_unzip,
                    },
                }),
            )
            response = await self.__websocket.recv()
            response_data = json.loads(response)

            if response_data.get("status") == "error":
                if response_data.get("message") != already_taken_message:
                    raise RegisterException(response_data)
            else:
                valid_id_generated = True

        print("\rRegistered successfully, waiting for receiver")
        print("Use the following command to receive data:", end="\n\n")
        print(f"tunnel receive {self.__session_name}", end="\n\n")
        print("On Windows you may need to use:", end="\n\n")
        print(f"tunnel.exe receive {self.__session_name}", end="\n\n")

    async def __prepare_rtc_connection(self) -> None:
        self.__rtc_connection: RTCPeerConnection = RTCPeerConnection()

        @self.__rtc_connection.on("icecandidate")
        async def on_icecandidate(candidate: Optional[RTCIceCandidate]) -> None:
            if candidate:
                await self.__websocket.send(
                    json.dumps({
                        "action": "candidate",
                        "target": "receiver",
                        "candidate": rtc_ice_candidate_to_json(candidate),
                        "session": self.__session_name,
                    }),
                )

        @self.__rtc_connection.on("datachannel")
        def on_datachannel(channel: RTCDataChannel):
            @channel.on("close")
            def on_close():
                print("Data channel closed by receiver, closing connection")
                self.__did_receiver_finish.set()
                self.__ack_received.set()
                asyncio.ensure_future(self.__close_connection())

    async def __prepare_data_channel(self) -> None:
        self.__data_channel: RTCDataChannel = self.__rtc_connection.createDataChannel("filetransfer")

        @self.__data_channel.on("open")
        def on_open():
            print("Receiver connected, sending file...")
            asyncio.ensure_future(self.__send_file(self.__data_channel))
            asyncio.ensure_future(self.__close_connection())

        @self.__data_channel.on("message")
        def on_message(message: Union[str, bytes]) -> None:
            if message == "Finished":
                print("\nFile transfer successful")
                self.__did_receiver_finish.set()
                self.__ack_received.set()
            elif message == "ack":
                self.__ack_received.set()
            elif "Error" in message:
                print(f"\nFile transfer failed: '{message}'")
                self.__did_receiver_finish.set()
                self.__ack_received.set()

    async def __send_offer(self) -> None:
        offer = await self.__rtc_connection.createOffer()
        await self.__rtc_connection.setLocalDescription(offer)
        await self.__websocket.send(json.dumps({"action": "offer", "sdp": self.__rtc_connection.localDescription.sdp, "session": self.__session_name}))

    async def __send_file(self, channel: RTCDataChannel) -> None:
        with open(self.__FILE_PATH, "rb") as file:
            count = 0
            total_sent = 0
            chunks_in_file = ceil(self.__FILE_METADATA.filesize / self.__session_config.CHUNK_SIZE_BYTES)
            while True:
                chunk = file.read(self.__session_config.CHUNK_SIZE_BYTES)
                progress = (count * 100) / chunks_in_file
                print(f"\rProgress: {progress:.3f}% ({get_human_readable_file_size(total_sent)})        ", end="")
                if not chunk:
                    break

                await self.__ack_received.wait()
                self.__ack_received.clear()
                channel.send(chunk)
                total_sent += len(chunk)
                count += 1

    async def __handle_incoming_messages(self) -> None:
        async for message in self.__websocket:
            data = json.loads(message)
            action = data.get("action")

            if action == "answer":
                await self.__handle_answer(data)
            elif action == "candidate":
                await self.__handle_candidate(data)
            elif action == "cancel":
                await self.__handle_cancel()

    async def __handle_answer(self, data: json) -> None:
        answer = RTCSessionDescription(sdp=data["sdp"], type="answer")
        await self.__rtc_connection.setRemoteDescription(answer)

    async def __handle_candidate(self, data: json) -> None:
        candidate = RTCIceCandidate(**data["candidate"])
        await self.__rtc_connection.addIceCandidate(candidate)

    async def __handle_cancel(self) -> None:
        print("Transfer canceled by receiver, closing connection")
        self.__did_receiver_finish.set()
        await self.__close_connection()

    async def __close_connection(self) -> None:
        await self.__did_receiver_finish.wait()
        for transceiver in self.__rtc_connection.getTransceivers():
            if transceiver.receiver:
                await transceiver.receiver.stop()
            if transceiver.sender:
                await transceiver.sender.stop()
        await self.__websocket.close()

    @staticmethod
    def __generate_random_session_name(words_count: int = 3) -> str:
        animals = [
            "aardvark", "aardwolf", "anteater", "antelope", "ape", "armadillo", "badger", "bat", "bear", "beaver", "bison",
            "bluejay", "bobcat", "buffalo", "cardinal", "caribou", "cat", "cheetah", "chicken", "chimpanzee", "chipmunk",
            "cougar", "cow", "crow", "deer", "dingo", "dog", "duck", "eagle", "elephant", "falcon",
            "ferret", "fox", "gazelle", "giraffe", "goat", "goose", "gorilla", "hawk", "hedgehog", "horse",
            "hummingbird", "hyena", "ibex", "jaguar", "jay", "kangaroo", "koala", "lemur", "leopard", "lion",
            "lynx", "magpie", "meerkat", "mink", "mongoose", "monkey", "moose", "muskox", "opossum", "orangutan",
            "ostrich", "otter", "owl", "panda", "pangolin", "panther", "parrot", "peacock", "penguin", "pig",
            "platypus", "porcupine", "rabbit", "raccoon", "raven", "reindeer", "robin", "sheep", "skunk", "sloth",
            "sparrow", "squirrel", "stoat", "swan", "tiger", "turkey", "wallaby", "weasel", "wolf", "wolverine",
            "wombat", "woodpecker", "yak", "zebra",
        ]

        random_words = random.sample(animals, words_count)
        return "-".join(random_words)
