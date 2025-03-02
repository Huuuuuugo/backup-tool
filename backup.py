import argparse
import tempfile
import zipfile
import shutil
import enum
import time
import io
import os

from platformdirs import user_data_dir

from utils import JSONManager, date_from_ms


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


class BackupExceptions:
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


# TODO: make it work on reverse (new_file to old_file)
def apply_changes(changes: list[Change], file_path: str) -> None:
    # separate the changed portion from the rest of the file
    with open(file_path, "rb") as file:
        # get first and last change
        first_change = changes[0]
        last_change = changes[-1]

        # get unchanged portion on the beginning of the file
        unchanged_start = file.read(first_change.position)

        # get unchanged portion on the ending of the file
        ending_pos = last_change.position
        if last_change.type == types.RMV.value:
            ending_pos += last_change.size
        file.seek(ending_pos)
        unchanged_end = file.read()

        # get the portion in the middle containing the bytes changed
        file.seek(first_change.position)  # got to the position of the first change
        changed_size = ending_pos - first_change.position
        changed = io.BytesIO(file.read(changed_size))
        changed.seek(0)

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
                changed.seek(position + size)

                # save the content from there onward
                original_content = changed.read()

                # move to the beggining of the removed portion and rewrite the content
                changed.seek(position)
                changed.write(original_content)

            case types.ADD.value:
                # update offset
                offset += size

                # move to the position after the added portion
                changed.seek(position)

                # save the new content and everything from there onward
                content = bytes_changed + changed.read()

                # move to the beggining of the removed portion and rewrite the content
                changed.seek(position)
                changed.write(content)

    # save changes to the file
    with open(file_path, "wb") as file:
        file.write(unchanged_start)
        changed.seek(0)
        file.write(changed.read(changed_size + offset))
        file.write(unchanged_end)
    changed.close()


def create_backup(old_file: str, new_file: str, backup_file: str) -> None:
    # get everything that changed between the two files
    changes = get_changes(old_file, new_file)

    if not changes:
        raise BackupExceptions.NoChangesException("The file is exactly the same as the last backup.")

    # save instructions and changes to temporary files
    with tempfile.TemporaryDirectory(dir="") as temp_dir:
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
    if output_file is None:
        output_file = input_file

    with tempfile.TemporaryDirectory(dir="") as temp_dir:
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


def list_tracked_files(backup_index: int | None = None):
    # read the list of tracked files inside tracked.json
    tracked_list_manger = JSONManager(TRACKED_FILES_LIST_PATH, {"last": -1, "list": []})
    tracked_list = tracked_list_manger.read()["list"]

    # return the entire list of tracked files if no index was specified
    if backup_index is None:
        return tracked_list

    # return the path of the tracked file if the given backup index exists or raise exception if not
    else:
        for file in tracked_list:
            if file["index"] == backup_index:
                return file["path"]

        raise BackupExceptions.BackupNotFoundError(f"Backup with index '{backup_index}' does not exist.")


def list_file_backups(backup_index: int, reverse: bool = False):
    # implicitly check if this backup index is being used
    list_tracked_files(backup_index)

    # get the list of timestamps
    backups_dir = os.path.join(BACKUP_DATA_DIR, f"{backup_index}/changes/")
    backup_list = [int(backup) for backup in os.listdir(backups_dir)]
    if reverse:
        backup_list.reverse()

    return backup_list


def get_backup_message(backup_index: int, timestamp: int):
    # check if the given backup exists
    backup_list = list_file_backups(backup_index)  # implicitly check if this backup index is being used
    if timestamp not in backup_list:
        raise BackupExceptions.TimestampNotFound(f"A backup with timestamp '{timestamp}' does not exist for the file '{list_tracked_files(backup_index)}'")

    # read the messages.json
    messages_path = os.path.join(BACKUP_DATA_DIR, str(backup_index), "messages.json")
    messages_manager = JSONManager(messages_path, {})
    messages_json = messages_manager.read()

    # return the message associated with the backup
    try:
        return messages_json[str(timestamp)]
    except KeyError:
        return ""


def create_backup_message(backup_index: int, timestamp: int, message: str):
    # check if the given backup exists
    backup_list = list_file_backups(backup_index)  # implicitly check if this backup index is being used
    if timestamp not in backup_list:
        raise BackupExceptions.TimestampNotFound(f"A backup with timestamp '{timestamp}' does not exist for the file '{list_tracked_files(backup_index)}'")

    # read messages.json
    messages_path = os.path.join(BACKUP_DATA_DIR, str(backup_index), "messages.json")
    messages_manager = JSONManager(messages_path, {})
    messages_json = messages_manager.read()

    # save the new message to messages.json
    messages_json.update({str(timestamp): message})
    messages_manager.save(messages_json)


def create_global_backup(file_path: str, message: str = "") -> None:
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
    with tempfile.TemporaryDirectory(dir=BACKUP_DATA_DIR) as temp_dir:
        # create backup
        temp_bak_path = os.path.join(temp_dir, "bak")
        create_backup(head_file_path, file_path, temp_bak_path)

        # copy temporary backup to its approrpiate path
        shutil.move(temp_bak_path, new_backup_path)

    # save backup message
    if message:
        create_backup_message(backup_index, timestamp, message)

    # copy current version of the file to head
    shutil.copy(file_path, head_file_path)


# TODO: create automatic backup when restoring with unsaved changes
# TODO: make it also work form newest to oldest backup
def restore_global_backup(backup_index: int, timestamp: int) -> None:
    # get path to the original file
    for file in list_tracked_files():
        if file["index"] == backup_index:
            file_path = file["path"]

    # get dir where the backups are stored
    backups_dir = os.path.join(BACKUP_DATA_DIR, f"{backup_index}/changes/")

    # get list of steps untill the target backup
    backup_list = list_file_backups(backup_index)
    for i, backup in enumerate(backup_list):
        if backup == timestamp:
            break
    backup_steps = backup_list[0 : i + 1]

    # apply all backups in sequence from oldest to newest
    with tempfile.TemporaryDirectory(dir="") as temp_dir:
        # save changes to a temporary file
        temp_file = os.path.join(temp_dir, "temp")
        open(temp_file, "wb").close()
        for backup in backup_steps:
            backup_path = os.path.join(backups_dir, str(backup))
            restore_backup(backup_path, temp_file)

        shutil.copy(temp_file, file_path)


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
                args.path_or_index = list_tracked_files(int(args.path_or_index))

            # run command
            create_global_backup(args.path_or_index, args.message)

            # success message
            print(f"New backup created for file '{os.path.realpath(args.path_or_index)}'")

        # TODO: warn about unsaved changes before overwriting the original file
        case "restore":
            # convert timestamp index into timestamp
            backup_list = list_file_backups(args.index, True)
            if args.timestamp_or_index < len(backup_list):
                args.timestamp_or_index = backup_list[args.timestamp_or_index]

            # run command
            restore_global_backup(args.index, args.timestamp_or_index)

            # success message
            print(f"Backup with timestamp '{args.timestamp_or_index}' and message \"{get_backup_message(args.index, args.timestamp_or_index)}\" restored for file '{list_tracked_files(args.index)}'")

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
                print(f"  {args.index} | {list_tracked_files(args.index)}")
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
            print(f"Update message from '{original_message}' to '{args.message}' for backup with timestamp '{args.timestamp_or_index}' from file '{list_tracked_files(args.index)}'")

        case "migrate":
            if args.new_dir is not None:
                new_dir = os.path.realpath(args.new_dir)
                shutil.move(BACKUP_DATA_DIR, new_dir)
                with open(NEW_DIR_FILE_PATH, "w", encoding="utf8") as new_dir_file:
                    new_dir_file.write(new_dir)

                print(f"Successfully migrate backups from '{BACKUP_DATA_DIR}' to '{new_dir}'")
            else:
                shutil.move(BACKUP_DATA_DIR, DEFAULT_BACKUP_DATA_DIR)
                os.remove(NEW_DIR_FILE_PATH)

                print(f"Successfully migrate backups from '{BACKUP_DATA_DIR}' to '{DEFAULT_BACKUP_DATA_DIR}'")


if __name__ == "__main__":
    main()
