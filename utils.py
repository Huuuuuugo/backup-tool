import os


def get_global_backups_list_and_next_index(backup_list_path: str):
    # get the list of existing backups
    backup_list = {}
    with open(backup_list_path, "r", encoding="utf8") as backup_list_file:
        # map each path on the list to its index on the backup folders
        for index, line in enumerate(backup_list_file):
            backup_list.update({os.path.realpath(line.strip()): index})

        # set the next entry index to zero if the list is empty
        try:
            next_entry = index + 1
        except UnboundLocalError:
            next_entry = 0

    return (backup_list, next_entry)
