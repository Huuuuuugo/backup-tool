import datetime
import json
import os


# TODO: refactor this to work exclusively with properties and be more intuitive to use
class JSONManager:
    """A helper class to manage writes and reads to json files more easily."""

    def __init__(self, json_path: str, default_value: dict | list):
        self.path = json_path

        # read content from the file if it already exists
        if os.path.exists(json_path):
            self.content = self.read()

        # create file with the default value if not
        else:
            self.content = self.save(default_value)

    def read(self):
        with open(self.path, "r", encoding="utf8") as file:
            self.content = json.loads(file.read())

        return self.content

    def save(self, content: dict | list):
        with open(self.path, "w", encoding="utf8") as file:
            self.content = content
            file.write(json.dumps(self.content, indent=2))


def date_from_ms(timestamp: int):
    """Convert a ms unix timestamp to a date time object."""
    return datetime.datetime.fromtimestamp(timestamp // 1000000000)


def get_tracked_path(backup_index: int):
    """Get the path of the tracked file with a corresponding backup index.

    Arguments
    ---------
    backup_index: int
        The backup index of the tracked file whose path need to be retrieved.

    Returns
    -------
    str
        A string containing the path of the track file.

    Raises
    ------
    BackupNotFoundError
        If the given backup index doesn't correspond to any tracked file.
    """
    from backup import list_tracked_files, BackupExceptions

    # return the path of the tracked file if the given backup index exists or raise exception if not
    tracked_list = list_tracked_files()
    for file in tracked_list:
        if file["index"] == backup_index:
            return file["path"]

    raise BackupExceptions.BackupNotFoundError(f"Backup with index '{backup_index}' does not exist.")


def timestamp_exists(backup_index: int, timestamp: int):
    """Check if a backup with the given timestamp exists for the specified file index.

    Parameters
    ----------
    backup_index: int
        The backup index of the file that's suposed to contain the timestamp.

    timestamp: int
        The timestamp expected.

    Raises
    ------
    TimestampNotFound
        If the timestamp is not found within the given backup index.

    BackupNotFoundError
        If the given backup index doesn't corespond to any of the tracked files.
    """
    from backup import list_file_backups, BackupExceptions

    # check if the given backup exists
    backup_list = list_file_backups(backup_index)  # implicitly check if this backup index is being used
    if timestamp not in backup_list:
        raise BackupExceptions.TimestampNotFound(f"A backup with timestamp '{timestamp}' does not exist for the file '{get_tracked_path(backup_index)}'")
