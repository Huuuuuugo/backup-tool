import enum
import os


class FileState(enum.Enum):
    UPDATE = 0  # represents a file being partially altered
    ADD = 1  # represents a file being tracked for the first time
    DELETE = 2  # represensts a file being deleted from tracking
    NO_FILE = 3  # represents a file that isn't being tracked and doesn't exist


def get_changes(
    file_path: str, backup_dir: str = ".bak/", chunk_size: int = 8
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
                                add.append((chunk_index, new_chunk))

                            else:
                                update.append((chunk_index, new_chunk))

                        chunk_index += 1

            return (FileState.UPDATE, {"add": add, "delete": delete, "update": update})


if __name__ == "__main__":
    from pprint import pprint
    import sys

    pprint(get_changes(sys.argv[1]))
