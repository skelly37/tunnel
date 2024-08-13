import os
from pathlib import Path
from typing import (
    Dict,
    Union,
)

# Recursive structure where string represents file content, while Dict represents the subdirectory tree
FileStructure = Dict[str, Union[str, Dict]]


def create_file_structure(base_path: Path, structure: FileStructure) -> None:
    for name, content in structure.items():
        current_path = base_path / name
        if isinstance(content, dict):
            current_path.mkdir(parents=True, exist_ok=True)
            create_file_structure(current_path, content)
        else:
            with open(current_path, "w", encoding="utf8") as f:
                f.write(content)


def get_directory_structure(base_path: Path) -> FileStructure:
    structure = {}
    for root, dirs, files in os.walk(base_path):
        rel_path = os.path.relpath(root, base_path)
        if rel_path == '.':
            rel_path = ''
        subdir = structure
        if rel_path:
            for part in rel_path.split(os.sep):
                subdir = subdir.setdefault(part, {})
        for file in files:
            with open(Path(root) / file, 'r', encoding="utf8") as f:
                subdir[file] = f.read()
        for directory in dirs:
            subdir[directory] = {}
    return structure
