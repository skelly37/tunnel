import logging
from pathlib import Path
from shutil import rmtree
import unittest

from client.utils.communication import SessionConfig
from client.utils.file import (
    compress_files,
    decompress_files,
    get_file_checksum,
    get_human_readable_file_size,
)
from tests.helpers import (
    FileStructure,
    create_file_structure,
    get_directory_structure,
)


class UtilsTests(unittest.TestCase):
    def setUp(self) -> None:
        logging.basicConfig(level=logging.DEBUG)
        self.__SMALL_FILENAME_FOR_CHECKSUM: Path = Path("./small_file.txt")
        self.__COMPRESSION_TEST_OUTPUT_ZIPNAME: Path = Path("./compression_test.zip")
        self.__COMPRESSION_TEST_INPUT_DIRNAME: Path = Path("./compression_input")
        self.__COMPRESSION_TEST_OUTPUT_DIRNAME: Path = Path("./compression_result")

    def tearDown(self) -> None:
        Path.unlink(self.__SMALL_FILENAME_FOR_CHECKSUM, missing_ok=True)
        Path.unlink(self.__COMPRESSION_TEST_OUTPUT_ZIPNAME, missing_ok=True)
        rmtree(self.__COMPRESSION_TEST_INPUT_DIRNAME, ignore_errors=True)
        rmtree(self.__COMPRESSION_TEST_OUTPUT_DIRNAME, ignore_errors=True)

    def test_session_config_get_chunk_size_megabytes(self) -> None:
        self.assertEqual(1, SessionConfig(server_address="", chunk_size_bytes=1024 ** 2).chunk_size_megabytes())
        self.assertEqual(2.5, SessionConfig(server_address="", chunk_size_bytes=((2 * (1024 ** 2)) + (1024 ** 2) / 2)).chunk_size_megabytes())

    def test_human_readable_file_size_standard_powers(self) -> None:
        suffix_as_power = {
            "B": 0,
            "KB": 1,
            "MB": 2,
            "GB": 3,
            "TB": 4,
            "PB": 5,
        }

        for suffix, power in suffix_as_power.items():
            self.assertEqual(f"1.000 {suffix}", get_human_readable_file_size(1024 ** power), f"suffix: {suffix}, power: {power}")

    def test_human_readable_file_size_roundings(self) -> None:
        self.assertEqual("1.500 KB", get_human_readable_file_size(int(1024 * 1.5)))
        self.assertEqual("1.001 KB", get_human_readable_file_size(1025))
        self.assertEqual("1.000 MB", get_human_readable_file_size((1024 ** 2) + 1))

    def test_small_file_checksum(self) -> None:
        text = "abcdef"
        checksum = "bef57ec7f53a6d40beb640a780a639c83bc29ac8a9816f1fc6c5c6dcd93c4721"
        with open(self.__SMALL_FILENAME_FOR_CHECKSUM, "w", encoding="utf8") as f:
            f.write(text)

        self.assertEqual(checksum, get_file_checksum(self.__SMALL_FILENAME_FOR_CHECKSUM))

    def test_large_file_checksum(self) -> None:
        self.assertEqual("ab0ab0ef726148f063b60a61ccc71dd0bab277ef39805b625fafd30611d3966a", get_file_checksum("../docs/preview.mp4"))

    def test_compression_flow(self) -> None:
        file_structure: FileStructure = {
            "a": {
                "b": "bb",
                "c": "uasfhasyfg",
            },
            "d": "test",
            "e": {},
        }

        create_file_structure(self.__COMPRESSION_TEST_INPUT_DIRNAME, file_structure)

        # sanity check
        self.assertEqual(file_structure, get_directory_structure(self.__COMPRESSION_TEST_INPUT_DIRNAME))

        compress_files([f"{self.__COMPRESSION_TEST_INPUT_DIRNAME / key}" for key in file_structure], self.__COMPRESSION_TEST_OUTPUT_ZIPNAME)
        decompress_files(self.__COMPRESSION_TEST_OUTPUT_ZIPNAME, self.__COMPRESSION_TEST_OUTPUT_DIRNAME)

        self.assertEqual(file_structure, get_directory_structure(self.__COMPRESSION_TEST_OUTPUT_DIRNAME))


if __name__ == "__main__":
    unittest.main()
