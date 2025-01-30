from enum import Enum


class Change:
    class ChangeTypes(Enum):
        ADD = 0
        RMV = 1

    def __init__(self, type: ChangeTypes, position: int = 0, content: bytes = b""):
        self.type = type.value
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
                    add = Change(types.ADD, 0, new_byte)
                    rmv = Change(types.RMV, 0, old_byte)
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
            if remaining_old_bytes:
                changes.append(Change(types.RMV, old_file_pos, remaining_old_bytes))
            elif remaining_new_bytes:
                changes.append(Change(types.ADD, old_file_pos, remaining_new_bytes))

    return changes


def apply_changes(changes: list[Change], file_path: str) -> None:
    with open(file_path, "rb+") as file:
        offset = 0
        for change in changes:
            bytes_changed = change.content
            size = change.size
            position = change.position + offset
            change_type = change.type

            match change_type:
                case types.RMV.value:
                    # update offset
                    offset -= size

                    # move to the position after the removed portion
                    file.seek(position + size)

                    # save the content from there onward
                    original_content = file.read()

                    # delete everything up until the beggining of the removed portion
                    file.truncate(position)

                    # move to the beggining of the removed portion and rewrite the content
                    file.seek(position)
                    file.write(original_content)

                case types.ADD.value:
                    # update offset
                    offset += size

                    # move to the position after the added portion
                    file.seek(position)

                    # save the new content and everything from there onward
                    content = bytes_changed + file.read()

                    # delete everything up until the beggining of the added portion
                    file.truncate(position)

                    # move to the beggining of the removed portion and rewrite the content
                    file.seek(position)
                    file.write(content)


if __name__ == "__main__":
    import sys

    old_file = sys.argv[1]
    new_file = sys.argv[2]

    changes = get_changes(old_file, new_file)
    for change in changes:
        print(change)

    with open(old_file, "rb") as file:
        original_content = file.read()

    apply_changes(changes, old_file)

    with open(old_file, "rb") as old:
        with open(new_file, "rb") as new:
            print(old.read() == new.read())

    input("Press enter to restore the test file.")

    with open(old_file, "wb") as file:
        original_content = file.write(original_content)
