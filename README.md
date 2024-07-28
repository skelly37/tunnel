# Tunnel
Simple command-line peer-to-peer file transfer using WebRTC.

https://github.com/user-attachments/assets/64ca9bea-b3cf-4de3-bd44-f17d4e99243a

## Features
- Auto-zipping and unzipping when directory or multiple files are selected as input.
- SHA256 checksum validation upon finish.
- Auto-generated receive commands with random words (instead of unpronounceable hashes).
- Live progress prompt for both parties
- Customizable receiver's RAM usage (i.e. intermediate file part dumps size)
- Customizable signaling server's address (can be self-hosted)
- Customizable chunk size (sender sends one chunk per message)

## Requirements
- [Python packages](./requirements.txt)
- Developed and tested on `Python 3.10.12`, might misbehave on different versions

## Generate executable
```shell
pip3 install -r requirements.txt
pyinstaller --onefile --name tunnel --hidden-import=aiortc --hidden-import=websockets ./client/__main__.py
```
