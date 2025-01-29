import tempfile
import shutil
import random
import string
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
    def create(cls, content: bytes = b""):
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
        """Test a byte sequence where both an addition and a deletion occur in the exact same cycle once."""
        with TempFileHelper() as helper:
            old_file_path = helper.create(b"this is an example of very short a file")
            new_file_path = helper.create(b"this is an example from a file")

            changes = get_changes(old_file_path, new_file_path)
            apply_changes(changes, old_file_path)

            with open(old_file_path, "rb") as old_file:
                with open(new_file_path, "rb") as new_file:
                    assert old_file.read() == new_file.read()

    def test_get_changes_with_break_condition_and_empty_file_on_same_cycle(self):
        """Test a byte sequence where one of the break conditions is met on the exact same cycle as a file ends.

        This should prioritize the break contition, as that is what will result on the actual change being saved.
        If this is not the case, an empty change will be saved instead of the real change.
        """
        with TempFileHelper() as helper:
            old_file_path = helper.create(b"new file with some extra content and this")
            new_file_path = helper.create(b"old content with a whole whole lot of removed contentaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

            changes = get_changes(old_file_path, new_file_path)
            apply_changes(changes, old_file_path)

            with open(old_file_path, "rb") as old_file:
                with open(new_file_path, "rb") as new_file:
                    assert old_file.read() == new_file.read()

    def test_random_chars(self):
        """Test the program with two randomly generated sequences of characters."""
        with TempFileHelper() as helper:
            # assign a random size for each file
            old_file_size = random.randint(15, 30)
            new_file_size = random.randint(15, 30)

            # fill both files with random characters
            old_file_content = "".join(random.choices(string.ascii_letters + string.digits, k=old_file_size))
            new_file_content = "".join(random.choices(string.ascii_letters + string.digits, k=new_file_size))
            old_file_path = helper.create(old_file_content.encode())
            new_file_path = helper.create(new_file_content.encode())

            # create a backup of the old file before it's altered
            with open(old_file_path, "rb") as old_file:
                old_file_backup_path = helper.create(old_file.read())

            # get and apply changes
            changes = get_changes(old_file_path, new_file_path)
            apply_changes(changes, old_file_path)

            # assert that both files are the same after applying the changes
            with open(old_file_path, "rb") as old_file:
                with open(new_file_path, "rb") as new_file:
                    try:
                        assert old_file.read() == new_file.read()
                    except AssertionError as e:
                        # save the files for analysis if the assertion fails
                        shutil.copy(old_file_backup_path, "./error_old_file.txt")
                        shutil.copy(new_file_path, "./error_new_file.txt")

                        raise e
