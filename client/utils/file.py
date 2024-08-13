import hashlib
import os
from typing import List
from zipfile import (
    ZIP_DEFLATED,
    ZipFile,
)


def compress_files(input_files_or_dirs: List[str], output_file: str) -> None:
    with ZipFile(output_file, 'w', ZIP_DEFLATED) as zipf:
        for item in input_files_or_dirs:
            if os.path.isfile(item):
                zipf.write(item, os.path.basename(item))
            elif os.path.isdir(item):
                for root, dirs, files in os.walk(item):
                    if not files and not dirs:
                        folder_path = os.path.relpath(root, start=os.path.dirname(item))
                        zipf.write(root, folder_path + '/')
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, start=os.path.dirname(item))
                        zipf.write(file_path, arcname)
                    for directory in dirs:
                        dir_path = os.path.join(root, directory)
                        arcname = os.path.relpath(dir_path, start=os.path.dirname(item)) + '/'
                        zipf.write(dir_path, arcname)
            else:
                print(f"Warning: {item} is neither a file nor a directory, skipping.")


def decompress_files(input_file: str, output_directory: str, delete_input: bool = False) -> None:
    with ZipFile(input_file, 'r') as zipf:
        zipf.extractall(path=output_directory)

    if delete_input:
        os.remove(input_file)


def get_file_checksum(file_path: str, algorithm: str = "sha256") -> str:
    hash_algorithm = getattr(hashlib, algorithm)()
    with open(file_path, 'rb') as file:
        while chunk := file.read(8192):
            hash_algorithm.update(chunk)
    return hash_algorithm.hexdigest()


def get_human_readable_file_size(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    unit_index = 0

    while size_bytes >= 1024 and unit_index < len(units) - 1:
        size_bytes /= 1024.0
        unit_index += 1

    return f"{size_bytes:.3f} {units[unit_index]}"
