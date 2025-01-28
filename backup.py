def get_changes(old_file_path: str, new_file_path: str):
    with open(old_file_path, "rb") as old_file:
        with open(new_file_path, "rb") as new_file:
            new_file_pos = 0
            old_file_pos = 0
            old_byte = 1
            new_byte = 1
            changes = []
            while old_byte and new_byte:
                old_byte = old_file.read(1)
                new_byte = new_file.read(1)
                new_file_pos += 1
                old_file_pos += 1

                if old_byte != new_byte:
                    offset = 0
                    diff_type = ""
                    diff = {"rmv": [old_byte, 0], "add": [new_byte, 0]}
                    rmv_break = False
                    add_break = False

                    # TODO FIXME: it gets stuck on this loop some times (probably related to a byte being empty)
                    while True:
                        next_old_byte = old_file.read(1)
                        next_new_byte = new_file.read(1)
                        offset += 1
                        # test new_byte against old_file bytes
                        # gets the bytes removed

                        if new_byte == next_old_byte:
                            diff["rmv"][1] = old_file_pos - 1
                            rmv_break = True
                        else:
                            # save the different bytes
                            diff["rmv"][0] += next_old_byte

                        # test old_byte against new_file bytes
                        # gets the bytes added
                        if old_byte == next_new_byte:
                            diff["add"][1] = old_file_pos - 1
                            add_break = True
                        else:
                            diff["add"][0] += next_new_byte

                        # decides weather to break and what's the type of the changes
                        if rmv_break and add_break:
                            diff_type = "bth"
                            break

                        elif rmv_break or add_break:
                            if rmv_break:
                                diff_type = "rmv"
                            else:
                                diff_type = "add"
                            break

                    # save the smallest one
                    # offset the file where the main byte (old_byte or new_byte, wichever generated the smallest diff) came from to the position of said byte
                    match diff_type:
                        case "add":
                            new_file_pos += offset
                            new_file.seek(new_file_pos)
                            old_file.seek(old_file_pos)

                            changes.append((diff["add"], "add"))

                        case "rmv":
                            old_file_pos += offset
                            new_file.seek(new_file_pos)
                            old_file.seek(old_file_pos)

                            changes.append((diff["rmv"], "rmv"))

                        case "bth":
                            old_file_pos += offset - 1
                            new_file_pos += offset - 1
                            new_file.seek(new_file_pos)
                            old_file.seek(old_file_pos)

                            diff["rmv"][0] += old_file.read(1)
                            old_file_pos += 1

                            changes.append((diff["add"], "add"))
                            changes.append((diff["rmv"], "rmv"))

    return changes


def apply_changes(changes, file_path: str):
    with open(file_path, "rb+") as file:
        offset = 0
        for change in changes:
            print(offset)
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
    changes = get_changes("examples/ex-1.txt", "examples/ex-2.txt")
    print(changes)

    apply_changes(changes, "examples/ex-1.txt")
