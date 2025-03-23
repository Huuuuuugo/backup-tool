from setuptools import setup


setup(
    name="BackTrack",
    version="0.1",
    description="simple tool for creating versioned delta backups",
    author="Huuuuuugo",
    url="https://github.com/Huuuuuugo/backup-tool",
    py_modules=["backup", "utils"],
    install_requires=["platformdirs"],
    entry_points={
        "console_scripts": [
            "bak = backup:main",
        ],
    },
)
