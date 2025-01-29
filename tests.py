import tempfile
import os

from backup import get_changes, apply_changes


class TempFileHelper:
    temp_files = []

    def __enter__(self):
        return TempFileHelper

    @classmethod
    def purge(cls):
        for file in cls.temp_files:
            try:
                os.remove(file)
            except FileNotFoundError:
                continue

    @classmethod
    def create(cls, content: bytes):
        temp_file = tempfile.NamedTemporaryFile("wb", delete=False)
        temp_file.write(content)
        temp_file.close()

        cls.temp_files.append(temp_file.name)
        return temp_file.name

    def __exit__(self, exc_type, exc_value, traceback):
        TempFileHelper.purge()
        return False


class TestCore:
    def test_get_changes_with_label_bth_once(self):
        """Test a byte sequence where both an addition and a deletion occur in the exact same cycle once"""
        with TempFileHelper() as helper:
            old_file_path = helper.create(b"this is an example of very short a file")
            new_file_path = helper.create(b"this is an example from a file")

            changes = get_changes(old_file_path, new_file_path)
            apply_changes(changes, old_file_path)

            with open(old_file_path, "rb") as old_file:
                with open(new_file_path, "rb") as new_file:
                    assert old_file.read() == new_file.read()
