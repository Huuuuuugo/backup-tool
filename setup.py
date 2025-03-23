from setuptools import setup


setup(
    name="BackTrack",
    version="0.1",
    author="Huuuuuugo",
    description="simple tool for creating versioned delta backups",
    url="https://github.com/Huuuuuugo/backup-tool",
    py_modules=["backup", "utils"],
    install_requires=["platformdirs"],
    entry_points={
        "console_scripts": [
            "bak = backup:main",
        ],
    },
)
