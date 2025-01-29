def get_changes(old_file_path: str, new_file_path: str):
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
                    offset = 0
                    diff_type = ""
                    diff = {"rmv": [old_byte, 0], "add": [new_byte, 0]}
                    rmv_break = False
                    add_break = False

                    # cycle through every different byte on both files until a
                    # similar byte is found or one of the files reaches its end
                    while True:
                        next_old_byte = old_file.read(1)
                        next_new_byte = new_file.read(1)
                        offset += 1

                        # test new_byte against old_file bytes
                        # gets the bytes removed
                        if new_byte == next_old_byte:
                            diff["rmv"][1] = old_file_pos - 1  # set the position where the change beggins
                            rmv_break = True  # sets the flag for breaking and labeling the change as an deletion
                        else:
                            # save the different bytes
                            diff["rmv"][0] += next_old_byte  # append the current byte to the chain of different bytes

                        # test old_byte against new_file bytes
                        # gets the bytes added
                        if old_byte == next_new_byte:
                            diff["add"][1] = old_file_pos - 1  # set the position where the change beggins
                            add_break = True  # sets the flag for breaking and labeling the change as an adition
                        else:
                            diff["add"][0] += next_new_byte  # append the current byte to the chain of different bytes

                        # check if both or any of the normal break conditions were met
                        # and specify how the changes should be labeled
                        if rmv_break or add_break:
                            if rmv_break and add_break:
                                diff_type = "bth"  # label changes as both
                            elif rmv_break:
                                diff_type = "rmv"  # label changes as deletion
                            else:
                                diff_type = "add"  # label changes as addition
                            break

                        # check if any of the bytes are empty, wich means one of the files are already finished
                        elif not (next_old_byte and next_new_byte):
                            same_change_flag = True
                            # if the new_file ended first, keep removing bytes until there's nothing left to be tested on any of the files
                            if not next_new_byte:
                                diff_type = "rmv"
                                diff["rmv"][1] = old_file_pos - 1

                                # check if the length of the content being changed is gratter tha one byte
                                # if this is true, it means that there's no more bytes avaliable on the other file
                                # and the last set shouldn't be reused (as it only contains the very last byte, which would endup being reused forever)
                                if len(diff["rmv"][0]) > 1:
                                    new_file_pos -= 1  # move the cursor of the finalized file one byte back,
                                    # allowing the same last set of bytes to be tested against all the bytes of the larger file
                                break

                            # if the new_file ended first, keep removing bytes until there's nothing left to be tested on any of the files
                            if not next_old_byte:
                                diff_type = "add"
                                diff["add"][1] = old_file_pos - 1

                                # check if the length of the content being changed is gratter tha one byte
                                # if this is true, it means that there's no more bytes avaliable on the other file
                                # and the last set shouldn't be reused (as it only contains the very last byte, which would endup being reused forever)
                                if len(diff["add"][0]) > 1:
                                    old_file_pos -= 1  # move the cursor of the finalized file one byte back,
                                    # allowing the same last set of bytes to be tested against all the bytes of the larger file
                                break

                    # save the changes according to the label and move the cursor of the file that
                    # generated the unused diff back to the beggining of the byte chain
                    match diff_type:
                        case "add":
                            new_file_pos += offset
                            new_file.seek(new_file_pos)  # move to the end of the byte chain
                            old_file.seek(old_file_pos)  # move to the beggining of the byte chain

                            if same_change_flag and (prev_change_type == diff_type):
                                changes[-1][0][0] += diff["add"][0]
                            else:
                                changes.append((diff["add"], "add"))  # save change

                        case "rmv":
                            old_file_pos += offset
                            new_file.seek(new_file_pos)  # move to the beggining of the byte chain
                            old_file.seek(old_file_pos)  # move to the end of the byte chain

                            if same_change_flag and (prev_change_type == diff_type):
                                changes[-1][0][0] += diff["rmv"][0]
                            else:
                                changes.append((diff["rmv"], "rmv"))  # save change

                        # TODO: test how this should interact with the logic to group changes together
                        case "bth":
                            old_file_pos += offset
                            new_file_pos += offset

                            # move both files to the end of the chain
                            new_file.seek(new_file_pos)
                            old_file.seek(old_file_pos)

                            # add both next bytes to their appropriate byte chain
                            diff["add"][0] += next_new_byte
                            diff["rmv"][0] += next_old_byte

                            changes.append((diff["add"], "add"))  # save changes
                            changes.append((diff["rmv"], "rmv"))  # save changes

                    prev_change_type = diff_type

                elif same_change_flag:
                    same_change_flag = False  # update the flag if the changes loop didn't trigger on the first iteration
                    prev_change_type = ""

            # get all the content that was left on any of the files
            remaining_old_bytes = old_file.read()
            remaining_new_bytes = new_file.read()

            # save the remaining content to the list of changes accordingly
            if remaining_old_bytes:
                changes.append(([remaining_old_bytes, old_file_pos], "rmv"))
            elif remaining_new_bytes:
                changes.append(([remaining_new_bytes, old_file_pos], "add"))

    return changes


def apply_changes(changes, file_path: str):
    with open(file_path, "rb+") as file:
        offset = 0
        for change in changes:
            bytes_changed = change[0][0]
            size = len(bytes_changed)
            position = change[0][1] + offset
            diff_type = change[1]

            match diff_type:
                case "rmv":
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

                case "add":
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
    print(changes)

    with open(old_file, "rb") as file:
        original_content = file.read()

    apply_changes(changes, old_file)

    input("Press enter to restore the test file.")
    with open(old_file, "wb") as file:
        original_content = file.write(original_content)
