import time
import shutil
import enum
import json
import uuid
import os


class FileState(enum.Enum):
    UPDATE = "U"  # represents a file being partially altered
    ADD = "A"  # represents a file being tracked for the first time
    DELETE = "D"  # represensts a file being deleted from tracking
    NO_FILE = "E"  # represents a file that isn't being tracked and doesn't exist


def get_changes(
    file_path: str, backup_dir: str = ".bak/", chunk_size: int = 32
) -> tuple[FileState, dict]:
    head_dir = os.path.join(backup_dir, "head/")
    head_file_path = os.path.join(head_dir, file_path)

    # runs if the file is being added
    if not os.path.exists(head_file_path):
        if os.path.exists(file_path):
            return (FileState.ADD, {})
        else:
            return (FileState.NO_FILE, {})

    else:
        # runs if the file was deleted
        if not os.path.exists(file_path):
            return (FileState.DELETE, {})

        # runs if the file is being updated
        else:
            add = []
            update = []
            delete = []
            chunk_index = 0
            with open(head_file_path, "rb") as head:
                with open(file_path, "rb") as new:
                    new_chunk = 1
                    head_chunk = 1
                    while new_chunk or head_chunk:
                        new_chunk = new.read(chunk_size)
                        head_chunk = head.read(chunk_size)

                        # runs if the chunks are different
                        if new_chunk != head_chunk:
                            # runs if something was deleted
                            if not new_chunk:
                                delete.append(chunk_index)

                            # runs if the chunk was created
                            elif not head_chunk:
                                add.append((chunk_index, new_chunk.decode()))

                            else:
                                update.append((chunk_index, new_chunk.decode()))

                        chunk_index += 1

            return (FileState.UPDATE, {"add": add, "delete": delete, "update": update})


def save_changes(file_path: str, backup_dir: str = ".bak/", chunk_size: int = 8):
    head_dir = os.path.join(backup_dir, "head/")
    parts_dir = os.path.join(backup_dir, "parts/")
    head_file_path = os.path.join(head_dir, file_path)
    os.makedirs(head_dir, exist_ok=True)
    os.makedirs(parts_dir, exist_ok=True)

    changes = get_changes(file_path)
    timestamp = float(f"{time.time():.2f}")
    message = ""
    changes_dict = {
        "timestamp": timestamp,
        "message": message,
        "type": changes[0].value,
        "changes": changes[1],
    }
    match changes[0]:
        case FileState.UPDATE:
            shutil.copy(file_path, head_file_path)

        case FileState.ADD:
            shutil.copy(file_path, head_file_path)

        case FileState.DELETE:
            os.remove(head_file_path)

    # read json file containing the changes
    if os.path.exists(f"{backup_dir}.changes"):
        with open(f"{backup_dir}.changes", "r") as changes_json:
            json_content = changes_json.read()
            json_content = json.loads(json_content)
    else:
        json_content = []

    # save the new changes to the json file
    with open(f"{backup_dir}.changes", "w") as changes_json:
        json_content.append(changes_dict)
        changes_json.write(json.dumps(json_content, indent=2))


if __name__ == "__main__":
    from pprint import pprint
    import sys

    save_changes(sys.argv[1])
