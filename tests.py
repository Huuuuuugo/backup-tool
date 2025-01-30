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


def validate_changes_shortcut(old_file_content: bytes, new_file_content: bytes):
    """Shortcut for testing if the changes from `get_changes` result on the updated file.

    Steps taken:
        1. Creates two temporary files as 'old version' and 'new version' of a file
        2. Runs `get_changes` and `apply_changes`
        3. Asserts that the output from `apply_changes` is exactly equal to the 'new version' of the file
    """
    with TempFileHelper() as helper:
        old_file_path = helper.create(old_file_content)
        new_file_path = helper.create(new_file_content)

        changes = get_changes(old_file_path, new_file_path)
        apply_changes(changes, old_file_path)

        with open(old_file_path, "rb") as old_file:
            with open(new_file_path, "rb") as new_file:
                assert old_file.read() == new_file.read()


class TestCore:
    def test_get_changes_merge_consecutive_changes(self):
        """Test two byte sequences that used to result on a character being wrong due to an error on the logic that groups consecutive changes together"""
        validate_changes_shortcut(
            b"XuqyvnfxggbN1Wr1uIrfOE5gB53JA",
            b"gDxv7liQ9GzFhcUk",
        )

    def test_get_changes_consecutive_changes_bth_rmv(self):
        """Test two byte sequences where both an addition and a deletion occur in the exact same cycle followed by a deletion on the next cyle.

        This should result on the deletion from the later cycle being appended to the one from the previous cycle (instead of creating a new deletion).
        """
        validate_changes_shortcut(
            b"this is an example of very short a file",
            b"this is an example from a file",
        )

    def test_get_changes_consecutive_changes_bth_add(self):
        """Test two byte sequences where both an addition and a deletion occur in the exact same cycle followed by an addition on the next cyle.

        This should result on the addition from the later cycle being appended to the one from the previous cycle (instead of creating a new addition).
        """
        validate_changes_shortcut(
            b"this is an example from a file",
            b"this is an example of very short a file",
        )

    def test_get_changes_files_end_simultaneusly(self):
        """Test two byte sequences where both files end simultaneusly, resulting on the last byte being lost if the program doesn't handle this scenario correctly"""
        validate_changes_shortcut(
            b"3tWpQlfCWlTOWxY7Cc2Lt",
            b"gxTVznFfHd4Izlvmq",
        )

    def test_get_changes_offset_fix(self):
        """Test two byte sequences that result on a slightly offseted output if the file positions aren't handled correctly on the program"""
        validate_changes_shortcut(
            b"SMfJTV6rN3N9NYFsj6K8UIaZndg",
            b"xizAxQkVNEzVY",
        )

    def test_get_changes_with_break_condition_and_empty_file_on_same_cycle(self):
        """Test two byte sequences where one of the break conditions is met on the exact same cycle as a file ends.

        This should prioritize the break contition, as that is what will result on the actual change being saved.
        If this is not the case, an empty change will be saved instead of the real change.
        """
        validate_changes_shortcut(
            b"new file with some extra content and this",
            b"old content with a whole whole lot of removed contentaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )

    def test_get_changes_random_chars(self):
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

    def test_get_changes_random_bytes(self):
        """Test the program with two randomly generated sequences of bytes."""
        with TempFileHelper() as helper:
            # assign a random size for each file
            old_file_size = random.randint(50, 150)
            new_file_size = random.randint(50, 150)

            # fill both files with random characters
            old_file_path = helper.create(random.randbytes(old_file_size))
            new_file_path = helper.create(random.randbytes(new_file_size))

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
