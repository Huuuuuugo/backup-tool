import threading
import argparse
import tempfile
import zipfile
import hashlib
import shutil
import enum
import time
import io
import os

from platformdirs import user_data_dir

from utils import JSONManager, date_from_ms, get_tracked_path, timestamp_exists


# set up global variables
USER_DATA_DIR = user_data_dir("BackTrack", "Huuuuuugo", ensure_exists=True)
DEFAULT_BACKUP_DATA_DIR = os.path.join(USER_DATA_DIR, "backups")

# get backup data dir
NEW_DIR_FILE_PATH = os.path.join(USER_DATA_DIR, "new_dir.txt")
if "new_dir.txt" in os.listdir(USER_DATA_DIR):
    with open(NEW_DIR_FILE_PATH, "r", encoding="utf8") as new_dir_file:
        BACKUP_DATA_DIR = new_dir_file.read()
        os.makedirs(BACKUP_DATA_DIR, exist_ok=True)
else:
    BACKUP_DATA_DIR = DEFAULT_BACKUP_DATA_DIR
    os.makedirs(BACKUP_DATA_DIR, exist_ok=True)

TRACKED_FILES_LIST_PATH = os.path.realpath(os.path.join(BACKUP_DATA_DIR, "tracked.json"))


# class to group all custom exceptions together
class BackupExceptions:
    class UnsavedChangesException(Exception):
        """Indicates that the original file contains changes that will be lost on restoration"""

    class NoChangesException(Exception):
        """Indicates that the file being backed up hasn't changed"""

    class BackupNotFoundError(Exception):
        """Indicates that no backup with the given index exist"""

    class TimestampNotFound(Exception):
        """Indicates that no backup with the given timestamp exist"""


class Change:
    class ChangeTypes(enum.Enum):
        ADD = 0
        RMV = 1

    def __init__(self, type: ChangeTypes, position: int = 0, content: bytes = b""):
        self.type = type
        self.position = position
        self.content = content

    @property
    def size(self):
        return len(self.content)

    def __str__(self):
        return f"<type: {Change.ChangeTypes(self.type).name} | position: {self.position} | content: {self.content}>"


types = Change.ChangeTypes


def get_changes(old_file_path: str, new_file_path: str) -> list[Change]:
    """Get a complete list of all the diferent sections between two files.

    This function cyles through every byte of both files in search of sections where they differ and then lables those sections as addition or deletion.
    All change objects store the type of change, position where the change occurs and content changed in a way that efectivelly creates a list of steps needed to go from "old file" to "new file".
    This approach also allows files to be reconstructed the other way around, going from "new file" to "old file".

    Parameters
    ----------
    old_file_path: str
        The path to the file that will be used as base for getting the differences.

    new_file_path: str
        The path of the file that'll be compared to the old file.

    Returns
    -------
    list[Change]
        A list containing every difference between the two files in the form of Change objects.
    """
    with open(old_file_path, "rb") as old_file:
        with open(new_file_path, "rb") as new_file:
            same_change_flag = False  # indicates that a new byte chain can be grouped with the last saved chain
            prev_change_type = ""  # saves the last change type for later use when checking whether to group two chains or not
            new_file_pos = 0
            old_file_pos = 0
            old_byte = 1
            new_byte = 1
            changes = []

            # cycle through each byte on both files simultaneously untill any of them
            # reaches its end
            while old_byte and new_byte:
                old_byte = old_file.read(1)
                new_byte = new_file.read(1)
                new_file_pos += 1
                old_file_pos += 1

                # if the bytes are different, get the entire chain of different bytes
                # and label it as an addition (add) or deletion (rmv)
                if old_byte != new_byte:
                    temp_same_change_flag = False  # stores the value of same_change_flag to be assigned after the loop
                    old_pos_offset = 0
                    new_pos_offset = 0
                    change_type = ""
                    add = Change(types.ADD.value, 0, new_byte)
                    rmv = Change(types.RMV.value, 0, old_byte)
                    rmv_break = False
                    add_break = False

                    # cycle through every different byte on both files until a
                    # similar byte is found or one of the files reaches its end
                    while True:
                        next_old_byte = old_file.read(1)
                        next_new_byte = new_file.read(1)

                        # test new_byte against old_file bytes
                        # gets the bytes removed
                        if new_byte == next_old_byte:
                            old_pos_offset = rmv.size
                            rmv.position = old_file_pos - 1  # set the position where the change beggins
                            rmv_break = True  # sets the flag for breaking and labeling the change as an deletion
                        else:
                            # save the different bytes
                            rmv.content += next_old_byte  # append the current byte to the chain of different bytes

                        # test old_byte against new_file bytes
                        # gets the bytes added
                        if old_byte == next_new_byte:
                            new_pos_offset = add.size
                            add.position = old_file_pos - 1  # set the position where the change beggins
                            add_break = True  # sets the flag for breaking and labeling the change as an adition
                        else:
                            add.content += next_new_byte  # append the current byte to the chain of different bytes

                        # check if both or any of the normal break conditions were met
                        # and specify how the changes should be labeled
                        if rmv_break or add_break:
                            if rmv_break and add_break:
                                change_type = "both"  # label changes as both
                            elif rmv_break:
                                change_type = types.RMV.value  # label changes as deletion
                            else:
                                change_type = types.ADD.value  # label changes as addition
                            break

                        # check if any of the bytes are empty, wich means one of the files are already finished
                        elif not (next_old_byte and next_new_byte):
                            temp_same_change_flag = True
                            if (not next_new_byte) and (not next_old_byte):
                                old_pos_offset = rmv.size
                                new_pos_offset = add.size
                                rmv.position = old_file_pos - 1
                                add.position = old_file_pos - 1
                                change_type = "both"
                                break

                            # if the new_file ended first, keep removing bytes until there's nothing left to be tested on any of the files
                            if not next_new_byte:
                                old_pos_offset = rmv.size
                                rmv.position = old_file_pos - 1
                                change_type = types.RMV.value

                                # check if the length of the content being changed is gratter tha one byte
                                # if this is true, it means that there's no more bytes avaliable on the other file
                                # and the last set shouldn't be reused (as it only contains the very last byte, which would endup being reused forever)
                                if rmv.size > 1:
                                    old_pos_offset -= 1
                                    new_file_pos -= 1  # move the cursor of the finalized file one byte back,
                                    # allowing the same last set of bytes to be tested against all the bytes of the larger file
                                break

                            # if the new_file ended first, keep removing bytes until there's nothing left to be tested on any of the files
                            if not next_old_byte:
                                new_pos_offset = add.size
                                add.position = old_file_pos - 1
                                change_type = types.ADD.value

                                # check if the length of the content being changed is gratter tha one byte
                                # if this is true, it means that there's no more bytes avaliable on the other file
                                # and the last set shouldn't be reused (as it only contains the very last byte, which would endup being reused forever)
                                if add.size > 1:
                                    new_pos_offset -= 1
                                    old_file_pos -= 1  # move the cursor of the finalized file one byte back,
                                    # allowing the same last set of bytes to be tested against all the bytes of the larger file
                                break

                    # save the changes according to the label and move the cursor of the file that
                    # generated the unused diff back to the beggining of the byte chain
                    match change_type:
                        case types.ADD.value:
                            new_file_pos += new_pos_offset
                            new_file.seek(new_file_pos)  # move to the end of the byte chain
                            old_file.seek(old_file_pos)  # move to the beggining of the byte chain

                            if same_change_flag and (prev_change_type in (change_type, "both")):
                                if prev_change_type == "both":
                                    changes[-2].content += add.content
                                else:
                                    changes[-1].content += add.content
                            else:
                                changes.append(add)  # save change

                        case types.RMV.value:
                            old_file_pos += old_pos_offset
                            new_file.seek(new_file_pos)  # move to the beggining of the byte chain
                            old_file.seek(old_file_pos)  # move to the end of the byte chain

                            if same_change_flag and (prev_change_type in (change_type, "both")):
                                changes[-1].content += rmv.content
                            else:
                                changes.append(rmv)  # save change

                        case "both":
                            temp_same_change_flag = True
                            old_file_pos += old_pos_offset
                            new_file_pos += new_pos_offset

                            # move both files to the end of the chain
                            new_file.seek(new_file_pos)
                            old_file.seek(old_file_pos)

                            # add both next bytes to their appropriate byte chain
                            add.content += next_new_byte
                            rmv.content += next_old_byte

                            changes.append(add)  # save changes
                            changes.append(rmv)  # save changes

                    same_change_flag = temp_same_change_flag
                    prev_change_type = change_type

                elif same_change_flag:
                    same_change_flag = False  # update the flag if the changes loop didn't trigger on the first iteration
                    prev_change_type = ""

            # get all the content that was left on any of the files
            remaining_old_bytes = old_file.read()
            remaining_new_bytes = new_file.read()

            # save the remaining content to the list of changes accordingly
            # TODO: make it append to the last change when appropriate
            if remaining_old_bytes:
                changes.append(Change(types.RMV.value, old_file_pos, remaining_old_bytes))
            elif remaining_new_bytes:
                changes.append(Change(types.ADD.value, old_file_pos, remaining_new_bytes))

    return changes


def apply_changes(changes: list[Change], file_path: str) -> None:
    """Apply a list of changes to a file using a fast multithreaded implementation.

    This function is used to apply a list of changes created by the `get_changes` function and efectively turn the "old file" into the "new file".
    When used in the context of version control, this function is responsible for restoring changes saved within the history.

    This function also uses a multithreaded implementation that allows for lists with hundreads of thousands of changes to be applied in just a few seconds (aroud 1 second per 100000 changes).

    Parameters
    ----------
    changes: list[Change]
        A list of changes generated by the `get_changes` function to be applied to a file.

    file_path: str
        The path of the file where the changes should be applied.

    Effects
    -------
    Replaces the file within the given file path with its changed version.
    """
    timer = time.perf_counter()

    # apply a set of changes to a buffer containing only a section of the original file
    # TODO: make it work on reverse (newer version to older version)
    def apply_changes_worker(changes: list[Change], file_path: str, buffer_info: list[io.BytesIO, bool], next_change: Change) -> None:
        buffer = buffer_info[0]

        # get first and last change
        first_change = changes[0]
        last_change = changes[-1]

        # get position of the last change
        ending_pos = last_change.position
        if last_change.type == types.RMV.value:
            ending_pos += last_change.size

        buffer_size = ending_pos - first_change.position

        # get the portion of the file where the changes need to be applied
        with open(file_path, "rb") as file:
            file.seek(first_change.position)
            buffer.write(file.read(buffer_size))
            buffer.seek(0)

        # apply changes sequentially
        offset = 0
        for change in changes:
            bytes_changed = change.content
            size = change.size
            position = change.position - first_change.position + offset
            change_type = change.type

            match change_type:
                case types.RMV.value:
                    # update offset
                    offset -= size

                    # move to the position after the removed portion
                    buffer.seek(position + size)

                    # save the content from there onward
                    original_content = buffer.read()

                    # move to the beggining of the removed portion and rewrite the content
                    buffer.seek(position)
                    buffer.write(original_content)

                case types.ADD.value:
                    # update offset
                    offset += size

                    # move to the position after the added portion
                    buffer.seek(position)

                    # save the new content and everything from there onward
                    content = bytes_changed + buffer.read()

                    # move to the beggining of the removed portion and rewrite the content
                    buffer.seek(position)
                    buffer.write(content)

        # get the unchanged section in between the last change of the current change set and first one of the next set
        offset_betwen_changes = next_change.position - last_change.position
        unchanged_between = io.BytesIO()
        if offset_betwen_changes > 0:
            with open(file_path, "rb") as file:
                file.seek(last_change.position)
                unchanged_between.write(file.read(offset_betwen_changes))
                unchanged_between.seek(0)

                # remove the portion that would be deleted by the last change
                # TODO: remember to modify this, since it does not take into account changes of the "both" type and might cause issues when applying changes in reverse
                if last_change.type == types.RMV.value:
                    unchanged_between.seek(last_change.size)

        # remove leftovers from the operations
        buffer.truncate(buffer_size + offset)
        buffer.seek(buffer_size + offset)

        # append the unchanged section in between changes
        buffer.write(unchanged_between.read())
        unchanged_between.close()

        # signalize that all necessary changes have been applied
        buffer_info[1] = True

    # apply the changes made by each worker thread to a temporary file in the correct order
    def apply_changes_supervisor(buffers_list: list[list[io.BytesIO, bool]], file_path: str, first_change: Change, last_change: Change):
        with tempfile.TemporaryDirectory() as temp_dir:
            # get the unchanged portions of the original file
            with open(file_path, "rb") as file:
                # get unchanged portion on the beginning of the file
                unchanged_start = file.read(first_change.position)

                # get unchanged portion on the ending of the file
                ending_pos = last_change.position
                if last_change.type == types.RMV.value:
                    ending_pos += last_change.size
                file.seek(ending_pos)
                unchanged_end = file.read()

            # create a temporary file to save the changes
            temp_file_path = os.path.join(temp_dir, "temp")
            with open(temp_file_path, "wb") as temp:
                # write the unchanged beginning
                temp.write(unchanged_start)

                while buffers_list:
                    # get next buffer on the queue
                    curr_buffer = buffers_list.pop(0)

                    # wait for the buffer to be fully written
                    while not curr_buffer[1]:
                        time.sleep(0.01)

                    # write the buffer to the original file
                    curr_buffer[0].seek(0)
                    temp.write(curr_buffer[0].read())
                    curr_buffer[0].close()

                # write the unchanged end
                temp.write(unchanged_end)

            # copy to the original file
            shutil.copy(temp_file_path, file_path)

    # split the changes into groups os 255 and set up a thread for each group
    # then add them in sequence to a queue
    buffers_list = []
    thread_queue = []
    thread_supervisor = threading.Thread(target=apply_changes_supervisor, args=(buffers_list, file_path, changes[0], changes[-1]), daemon=True)
    while changes:
        # setup the buffer and change set
        change_set = changes[0:255]  # take the first 255 changes
        changes_buffer = io.BytesIO()
        buffer_info = [changes_buffer, False]  # the first value is the actual buffer and the second indicates if all changes have been applied
        buffers_list.append(buffer_info)

        # update the list of changes
        changes = changes[255:]

        # get the change that comes after the current set of changes
        if changes:
            next_change = changes[0]
        else:
            next_change = change_set[-1]

        # set up the worker thread with the change_set, file_path (for reference when creating the buffer), buffer_info and next_change (to calculate and preserve the unchanged sections in between change sets)
        thread = threading.Thread(target=apply_changes_worker, args=(change_set, file_path, buffer_info, next_change), daemon=True)
        thread_queue.append(thread)

    # start the supervisor thread to manage writes to the final file
    thread_supervisor.start()

    # start the worker threads allowing up to 20 concurrent ones (besides main and supervisor)
    while thread_queue:
        if threading.active_count() <= 22:
            thread_queue.pop(0).start()
        else:
            time.sleep(0.01)

    # wait for all threads to finish before ending
    while threading.active_count() > 1:
        time.sleep(0.01)

    print(f"apply time: {time.perf_counter() - timer}")


def create_backup(old_file: str, new_file: str, backup_file: str) -> None:
    """Create a delta backup file using the `get_changes` function.

    This functions uses the output from `get_changes` to create a backup file that can be stored on the system.
    This backup file consists of a LZMA compressed file composed of two other files: "changes" and "instructions".

    The "changes" file is simply a binary file composed of all the changed content one right after the other.

    The "instructions" file is a plain text file with instructions on how to recreate the file using the content from "changes".
    Every line of this file represents a change and every change is composed of:
    - 'change id', that represents the type of change (0 for addition and 1 for deletion);
    - 'change position', that stores the exact byte where the change starts;
    - 'change size', that stores the exact size of the change in bytes;

    all that information, as stated above, is stored in a lingle line and separated by space characters.

    Example: "0 255 10". Here '0' would indicate that the change is an addition, '255' would be the exact position where it starts at and '10' is how many bytes where added.

    The information from "instruction" is later used on the `restore_backup` function to sequentially parse the "changes" file and recreate the original file.

    Parameters
    ----------
    old_file: str
        The path to the "old file" used as input for the `get_changes` function.

    new_file: str
        The path to the "new file" used as input for the `get_changes` function.

    backup_file: str
        The path where the backup file will be saved when finished.

    Effects
    -------
    Creates a backup file on the specified location.

    Raises
    ------
    NoChangesException
        If "old file" and "new file" are exactly equal.
    """
    # get everything that changed between the two files
    changes = get_changes(old_file, new_file)

    if not changes:
        raise BackupExceptions.NoChangesException("The file is exactly the same as the last backup.")

    # save instructions and changes to temporary files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_changes_path = os.path.join(temp_dir, "changes")
        temp_instructions_path = os.path.join(temp_dir, "instructions")
        with open(temp_instructions_path, "w") as instructions_file:
            with open(temp_changes_path, "wb") as changes_file:
                for change in changes:
                    # save instruction for current change
                    instruction_str = f"{change.type} {change.position} {change.size}\n"
                    instructions_file.write(instruction_str)

                    # save bytes changed
                    changes_file.write(change.content)

        # compress both files together
        temp_zip_path = os.path.join(temp_dir, "backup")
        with zipfile.ZipFile(temp_zip_path, "w", compression=zipfile.ZIP_LZMA) as zip_file:
            zip_file.write(temp_instructions_path, "instructions")
            zip_file.write(temp_changes_path, "changes")

        # save output file
        shutil.move(temp_zip_path, backup_file)


def restore_backup(backup_file: str, input_file: str, output_file: str | None = None) -> None:
    """Restore a backup using a file created by `create_backup`.

    See `create_backup` for more information on how the backup file works.

    This function starts by extracting the contents of the backup file into a temporary directory and then cycling through each instruction of the "instructions" file, recostructing the original list of changes.
    For each instruction it sequentially consumes the current change size from the "changes" file and uses this in conjunction to the position and type values to instantiate a new Change object that's later appended to a list of changes.

    After that, it simply calls the `apply_changes` function to apply the retrieved list of changes to the original file.

    Parameters
    ----------
    backup_file: str
        The path to the backup file generated by `create_backup`.

    input_file: str
        The path to the original file to which the backup belongs.


    output_file: str, None, optional
        The path to a separate file to store the restored version of the original file.

    Effects
    -------
    Replaces the original file or the specified output file with the version contained within the given backup file.
    """
    if output_file is None:
        output_file = input_file

    with tempfile.TemporaryDirectory() as temp_dir:
        # extract files from the backup
        with zipfile.ZipFile(backup_file, "r") as backup_file:
            backup_file.extractall(path=temp_dir)

        # create a list of change objects
        changes = []
        temp_changes_path = os.path.join(temp_dir, "changes")
        temp_instructions_path = os.path.join(temp_dir, "instructions")

        with open(temp_instructions_path, "r") as instructions_file:
            with open(temp_changes_path, "rb") as changes_file:
                for line in instructions_file.readlines():
                    type, position, size = line.strip().split(" ")
                    content = changes_file.read(int(size))

                    changes.append(Change(int(type), int(position), content))

    # apply changes to the input_file
    apply_changes(changes, output_file)


def list_tracked_files() -> list[dict]:
    """Get a list containing all the tracked files and their corresponding backup indexes and paths.

    Returns
    -------
    list[dict]
        A list of dicts, each one representing a different tracked file.
        Each dict is made out of two fields:
            index: which contains the backup index of the tracked file;
            path: which contains the absolute path of the tracked file.
    """
    # read the list of tracked files inside tracked.json
    tracked_list_manger = JSONManager(TRACKED_FILES_LIST_PATH, {"last": -1, "list": []})
    tracked_list = tracked_list_manger.read()["list"]

    # return the entire list of tracked files if no index was specified
    return tracked_list


def list_file_backups(backup_index: int, reverse: bool = False) -> list[int]:
    """Get a list containing all the timestamps of all the backups of a given tracked file.

    Arguments
    ---------
    backup_index: int
        The backup index of the file whose timestamps need to be retrieved.

    reverse: bool, optional
        By default, the returned list is sorted from oldest to newest backup. When this argument is set to True, the list will be reversed before being returned.

    Returns
    -------
    list[int]
        A list containing all the timestamps for every backup of the given tracked file ordered from oldest to newest or the other way around.

    Raises
    ------
    BackupNotFoundError
        If the given backup index doesn't correspond to any tracked file.
    """
    # implicitly check if the given backup index is being used
    get_tracked_path(backup_index)

    # get the list of timestamps
    backups_dir = os.path.join(BACKUP_DATA_DIR, f"{backup_index}/changes/")
    backup_list = [int(backup) for backup in os.listdir(backups_dir)]
    if reverse:
        backup_list.reverse()

    return backup_list


def get_backup_message(backup_index: int, timestamp: int) -> str:
    """Get the message of a given backup.

    Arguments
    ---------
    backup_index: int
        The backup index of the file to which the backup belongs.

    timestamp: int
        The timestamp of the backup whose message need to be retrieved.

    Returns
    -------
    str
        A string containing the message.

    Raises
    ------
    TimestampNotFound
        If the timestamp is not found within the given backup index.

    BackupNotFoundError
        If the given backup index doesn't corespond to any of the tracked files.
    """
    # check if the given backup exists
    timestamp_exists(backup_index, timestamp)

    # read messages.json
    messages_path = os.path.join(BACKUP_DATA_DIR, str(backup_index), "messages.json")
    messages_manager = JSONManager(messages_path, {})
    messages_json = messages_manager.read()

    # return the message associated with the backup
    try:
        return messages_json[str(timestamp)]
    except KeyError:
        return ""


def create_backup_message(backup_index: int, timestamp: int, message: str) -> None:
    """Update the message of a given backup.

    Arguments
    ---------
    backup_index: int
        The backup index of the file to which the backup belongs.

    timestamp: int
        The timestamp of the backup whose message need to be updated.

    message: str
        The new backup message.

    Effects
    -------
    Replaces the backup message of the specified bckup with the new one.

    Raises
    ------
    TimestampNotFound
        If the timestamp is not found within the given backup index.

    BackupNotFoundError
        If the given backup index doesn't corespond to any of the tracked files.
    """
    # check if the given backup exists
    timestamp_exists(backup_index, timestamp)

    # read messages.json
    messages_path = os.path.join(BACKUP_DATA_DIR, str(backup_index), "messages.json")
    messages_manager = JSONManager(messages_path, {})
    messages_json = messages_manager.read()

    # save the new message to messages.json
    messages_json.update({str(timestamp): message})
    messages_manager.save(messages_json)


def get_checksum(backup_index: int, timestamp: int) -> str:
    """Get the sha256 checksum of a given backup.

    Arguments
    ---------
    backup_index: int
        The backup index of the file to which the backup belongs.

    timestamp: int
        The timestamp of the backup whose checksum need to be retrieved.

    Returns
    -------
    str
        A string containing the sha256 checksum.

    Raises
    ------
    TimestampNotFound
        If the timestamp is not found within the given backup index.

    BackupNotFoundError
        If the given backup index doesn't corespond to any of the tracked files.
    """
    # check if the given backup exists
    timestamp_exists(backup_index, timestamp)

    # read checksums.json
    checksums_path = os.path.join(BACKUP_DATA_DIR, str(backup_index), "checksums.json")
    checksums_manager = JSONManager(checksums_path, {})
    checksums_json = checksums_manager.read()

    # return the checksum associated with the backup
    return checksums_json[str(timestamp)]


def create_global_backup(file_path: str, message: str = "") -> None:
    """Create a globally accessible and automatically managed delta backup with version history.

    This funtion uses the `create_backup` function to create a backup file following a set of restrictions that allows for a version history to be created and accesed from anywhere on the system.

    In a folder specified by the `BACKUP_DATA_DIR` global variable, a file named `tracked.json` is created to link tracked files to their respective "backup index", which is an auto incrementing positive integer.
    This index is used to reference a "backup folder" named after it, which stores all backups of a tracked file along with the relevant information about them.
    Each "backup folder" is composed of the following files:
    - a folder named "changes", where all the actual backup files are stored with their timestamp as the file name for easy reference;
    - "checksums.json", where the sha264 checksums of each backup are stored and linked to their respective backup timestamp;
    - "messages.json", where the messages of each backup are stored and linked to their respective backup timestamp;
    - "timestamps", where the timestamp of the current active backup is stored for reference when looking up its checksum;
    - "head", which stores a full copy of the last backed up version of the original file for quick lookup when creating a new backup.

    In sumary, the folder structure of the global backups folder looks something like this:
    ```
    | 0/    # a backup folder named after the backup index of a tracked file
    | | changes/    # a folder storing all the backup files
    | | | 1743175897507    # a backup file created at March 28 2025 15:31:37.507 UTC
    | | messages.json   # a file linking each backup message to its timestamp
    | | checksums.json  # a file linking each backup checksum to its timestamp
    | | timestamp       # a file storing the timestamp of the last active backup
    | | head            # a file storing a full copy of the last backed version of the file
    | tracked.json  # a file linking the full path of each tracked file to its backup index
    ```

    Parameters
    ----------
    file_path: str
        The path of the file being backed up.

    message: str, optional
        A message describing the current backup.

    Effects
    -------
    Create a backup file at the "changes" directory for the tracked file and update "head", "timestamp", "checksums.json" and "messages.json".

    If the file being backed up doesn't have a backup index or backup folder yet, a backup index will be assigned to it and added to "tracked.json".
    A backup folder will also be created along with all the other necessary files.

    Raises
    ------
    NoChangesException
        If the content of the file being backed up is exactly equal to the content from the last backup.
    """
    file_path = os.path.realpath(file_path)  # get the normalized absolute path of the file
    timestamp = time.time_ns()  # get the timestamp of the backup

    # get the list of tracked files and index of a possible new tracked file
    tracked_list_manager = JSONManager(TRACKED_FILES_LIST_PATH, {"last": -1, "list": []})
    tracked_list = tracked_list_manager.read()
    next_entry = tracked_list["last"] + 1

    # check if a backup already exists for the file and get its index
    backup_exists = False
    backup_index = next_entry
    for backup in tracked_list["list"]:
        if backup["path"] == file_path:
            backup_exists = True
            backup_index = backup["index"]

    # get the appropriate directory for backups of the selected file and the
    # exact path where the new backup and head will be stored
    backups_dir = os.path.join(BACKUP_DATA_DIR, f"{backup_index}/")
    new_backup_path = os.path.join(backups_dir, f"changes/{timestamp}")
    head_file_path = os.path.join(backups_dir, "head")

    # if the file is being backed up for the first time
    if not backup_exists:
        # create backup directory
        os.makedirs(os.path.dirname(new_backup_path), exist_ok=True)

        # creat an empty head file
        open(head_file_path, "wb").close()

        # add the new file to the list of backups
        new_backup = {"index": backup_index, "path": file_path}
        tracked_list["list"].append(new_backup)
        tracked_list["last"] = backup_index
        tracked_list_manager.save(tracked_list)

    # create a temporary backup file
    with tempfile.TemporaryDirectory() as temp_dir:
        # create backup
        temp_bak_path = os.path.join(temp_dir, "bak")
        create_backup(head_file_path, file_path, temp_bak_path)

        # copy temporary backup to its approrpiate path
        shutil.move(temp_bak_path, new_backup_path)

    # save backup checksum
    with open(file_path, "rb") as file:
        # get checksum
        checksum = hashlib.sha256(file.read()).hexdigest()

        # read checksums.json
        checksums_path = os.path.join(BACKUP_DATA_DIR, str(backup_index), "checksums.json")
        checksums_manager = JSONManager(checksums_path, {})
        checksums_json = checksums_manager.read()

        # save the new checksum to checksums.json
        checksums_json.update({str(timestamp): checksum})
        checksums_manager.save(checksums_json)

    # save backup message
    if message:
        create_backup_message(backup_index, timestamp, message)

    # copy current version of the file to head
    shutil.copy(file_path, head_file_path)

    # update current timestamp
    curr_timestamp_path = os.path.join(BACKUP_DATA_DIR, str(backup_index), "timestamp")
    with open(curr_timestamp_path, "w") as curr_timestamp:
        curr_timestamp.write(str(timestamp))


# TODO: make it also work form newest to oldest backup
def restore_global_backup(backup_index: int, timestamp: int, unsaved_changes_ok: bool = False) -> None:
    """Restore a backup created by the `create_global_backup` function.

    See `create_global_backup`for more information on how global backups work.

    This function starts by checking if the backup exists and the file being restored doesn't contain unsaved changes, which is done by comparing its checksum to the checksum of the current active backup, avoiding accidently overwriting any new data.
    After that, it starts the reconstruction by geting a list of all the backups within the "changes" directory and searching for the one with the specified timestamp, this list is then sliced and only the timestamps necessary to reconstruct the target backup are left.
    This new list is then iterated through and each backup is restored sequentially up until the target backup.
    The function finishes by changing the value of the current active backup to the one that was just restored by updating the "timestamp" file.

    Parameters
    ----------
    backup_index: str
        The backup index of the file to which the backup belongs.

    timestamp: int
        The timestamp of the backup that's going to be restored.

    unsaved_changes_ok: bool, optional
        If set to True, the check for unsaved changes on the original file is ignored and the backup will forcibly overwrite whatever was there before.

    Effects
    -------
    Restore a globally tracked file to a previously backed up state.

    Update the value of the "timestamp" file to the timestamp of the backup restored.

    Raises
    ------
    TimestampNotFound
        If the timestamp is not found within the given backup index.

    BackupNotFoundError
        If the given backup index doesn't corespond to any of the tracked files.

    UnsavedChangesException
        If the file being restored contains unsaved changes.
    """
    # check if the given backup exists
    timestamp_exists(backup_index, timestamp)

    # get path to the original file
    for file in list_tracked_files():
        if file["index"] == backup_index:
            file_path = file["path"]

    # check if there's unsaved changes
    if not unsaved_changes_ok:
        # get checksum of the original file before being restored
        with open(file_path, "rb") as original_file:
            original_checksum = hashlib.sha256(original_file.read()).hexdigest()

        # get current timestamp
        curr_timestamp_path = os.path.join(BACKUP_DATA_DIR, str(backup_index), "timestamp")
        with open(curr_timestamp_path, "r") as curr_timestamp_file:
            curr_timestamp = int(curr_timestamp_file.read())

        # get checksum of the current backup
        backup_checksum = get_checksum(backup_index, curr_timestamp)

        # check if the checksums are different
        if original_checksum != backup_checksum:
            raise BackupExceptions.UnsavedChangesException("The original file contains unsaved changes")

    # get dir where the backups are stored
    backups_dir = os.path.join(BACKUP_DATA_DIR, f"{backup_index}/changes/")

    # get list of steps untill the target backup
    backup_list = list_file_backups(backup_index)
    for i, backup in enumerate(backup_list):
        if backup == timestamp:
            break
    backup_steps = backup_list[0 : i + 1]

    # apply all backups in sequence from oldest to newest
    with tempfile.TemporaryDirectory() as temp_dir:
        # save changes to a temporary file
        temp_file = os.path.join(temp_dir, "temp")
        open(temp_file, "wb").close()
        for backup in backup_steps:
            backup_path = os.path.join(backups_dir, str(backup))
            restore_backup(backup_path, temp_file)

        shutil.copy(temp_file, file_path)

    # update current timestamp
    curr_timestamp_path = os.path.join(BACKUP_DATA_DIR, str(backup_index), "timestamp")
    with open(curr_timestamp_path, "w") as curr_timestamp:
        curr_timestamp.write(str(timestamp))


def migrate_global_backups(new_dir: str | None = None) -> None:
    """Move global backups to some other folder.

    Parameters
    ----------
    new_dir: str, None, optional
        The path of the folder to where the backups will be moved.
        If omited, the backups will move back to the default directory.

    Effects
    -------
    Moves all the global backups to the specified folder.

    Creates a file named "new_dir.txt" inside the original directory to reference the new directory.

    Deletes the "new_dir.txt" file if moving back to the default directory instead.
    """
    # move backups to the new directory
    if new_dir is not None:
        new_dir = os.path.realpath(new_dir)
        shutil.move(BACKUP_DATA_DIR, new_dir)
        with open(NEW_DIR_FILE_PATH, "w", encoding="utf8") as new_dir_file:
            new_dir_file.write(new_dir)

    # move backups to the default location if new_dir is None
    else:
        shutil.move(BACKUP_DATA_DIR, DEFAULT_BACKUP_DATA_DIR)
        os.remove(NEW_DIR_FILE_PATH)


def main():
    # arguments setup
    parser = argparse.ArgumentParser()
    subparser = parser.add_subparsers(dest="action", help="avaliable commands:")

    # arguments for creating backup
    create_parser = subparser.add_parser("create", help="creates a new backup")
    create_parser.add_argument("path_or_index", type=str, help="the path or backup index of the file being backed up")
    create_parser.add_argument("message", nargs="?", type=str, help="message describing what changed")

    # arguments for restoring a backup
    restore_parser = subparser.add_parser("restore", help="restores a backup")
    restore_parser.add_argument("index", type=int, help="the index of the file being restored")
    restore_parser.add_argument("timestamp_or_index", type=int, default="", help="the timestamp of the backup you want to restore")

    # arguments for listing information
    list_parser = subparser.add_parser("list", help="lists all the tracked files and their respective indexes or backups with their respective timestamps")
    list_parser.add_argument("index", nargs="?", type=int, default=None, help="the index of the file whose backups you want to list, omit it to get a list of all tracked files")

    # arguments for creating or updating a backup message
    reword_parser = subparser.add_parser("reword", help="creates or updates a backup message")
    reword_parser.add_argument("index", type=int, help="the index of the file being restored")
    reword_parser.add_argument("timestamp_or_index", type=int, default="", help="the timestamp of the backup you want to restore")
    reword_parser.add_argument("message", type=str, help="message describing what changed")

    # arguments for migrating backups to another directory
    migrate_parser = subparser.add_parser("migrate", help="migrate all backups to some other directory")
    migrate_parser.add_argument("new_dir", nargs="?", type=str, default=None, help="the path of the new directory, omit this to migrate back to the default directory")

    # main cli logic
    args = parser.parse_args()
    match args.action:
        case "create":
            # convert backup index into file path
            if args.path_or_index.isdigit():
                args.path_or_index = get_tracked_path(int(args.path_or_index))

            # run command
            create_global_backup(args.path_or_index, args.message)

            # success message
            print(f"New backup created for file '{os.path.realpath(args.path_or_index)}'")

        # TODO: allow the user to restore even with unsaved changes
        # TODO: update the warning on the readme about restoring files
        # TODO: improve error messages
        case "restore":
            # convert timestamp index into timestamp
            backup_list = list_file_backups(args.index, True)
            if args.timestamp_or_index < len(backup_list):
                args.timestamp_or_index = backup_list[args.timestamp_or_index]

            # run command
            restore_global_backup(args.index, args.timestamp_or_index)

            # success message
            print(f"Backup with timestamp '{args.timestamp_or_index}' and message \"{get_backup_message(args.index, args.timestamp_or_index)}\" restored for file '{get_tracked_path(args.index)}'")

        case "list":
            # list tracked files
            if args.index is None:
                tracked_list = list_tracked_files()
                print("Showing list of tracked files:")
                print("( backup index | file path )")
                for file in tracked_list:
                    print(f"{file['index']} | {file['path']}")

            # list backup timestamps for a tracked file
            else:
                backup_list = list_file_backups(args.index, reverse=True)
                print("Showing backups for:")
                print(f"  {args.index} | {get_tracked_path(args.index)}")
                print("( timestamp index | timestamp | date | message )")
                i = 0
                for timestamp in backup_list:
                    print(f'{i} | {timestamp} | {date_from_ms(timestamp)} | "{get_backup_message(args.index, timestamp)}"')
                    i += 1

        case "reword":
            # conver timestamp index into timestamp
            backup_list = list_file_backups(args.index, True)
            if args.timestamp_or_index < len(backup_list):
                args.timestamp_or_index = backup_list[args.timestamp_or_index]

            # run command
            original_message = get_backup_message(args.index, args.timestamp_or_index)
            create_backup_message(args.index, args.timestamp_or_index, args.message)

            # success message
            print(f"Update message from '{original_message}' to '{args.message}' for backup with timestamp '{args.timestamp_or_index}' from file '{get_tracked_path(args.index)}'")

        case "migrate":
            migrate_global_backups(args.new_dir)

            if args.new_dir is not None:
                print(f"Successfully migrate backups from '{BACKUP_DATA_DIR}' to '{os.path.abspath(args.new_dir)}'")
            else:
                print(f"Successfully migrated backups from '{BACKUP_DATA_DIR}' to '{DEFAULT_BACKUP_DATA_DIR}'")

        case _:
            parser.print_help()


if __name__ == "__main__":
    main()
