import datetime
import json
import os


class JSONManager:
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
    return datetime.datetime.fromtimestamp(timestamp // 1000000000)
