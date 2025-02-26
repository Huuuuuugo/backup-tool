# BackTrack
A pure python tool for creating versioned backups globally.

TODO

## Installation
TODO

## Usage
### General usage:
```console
python backup.py <operation> [arguments]
```

There are a few different operations BackTrack can perform, each one with it's own set of optional and required arguments. You can get a full list of them by simply using:
```console
python backup.py -h
```

Which should return something like this:
```console
usage: backup.py [-h] {create,restore,list,reword} ...

positional arguments:
  {create,restore,list,reword}
                        avaliable commands:
    create              creates a new backup
    restore             restores a backup
    list                lists all the tracked files and their respective indexes or backups with their respective timestamps
    reword              creates or updates a backup message

options:
  -h, --help            show this help message and exit
```

Furthermore, you can get a full list of the arguments an operation takes by running:
```console
python backup.py <operation> -h
```

Here's an example for the `create` operation:

Input:
```console
python backup.py create -h
```

Output:
```console
usage: backup.py create [-h] path_or_index [message]

positional arguments:
  path_or_index  the path or backup index of the file being backed up
  message        message describing what changed

options:
  -h, --help     show this help message and exit
```
----


### Creating backups
Before anything else, you'll need to know how to create backups. Here's how you can do it:
```console
backup.py create <path_or_index> [message]
```

The required `path_or_index` argument, as the name implies, can be either a **string** containing the **full/relative path** to the file being backed up or a **integer** **index** representing that file. 

  - The `path` option is **only required for the first backup**, as the file will only have an associated index **after** that, altho you can still use it for subsequent backups if you prefer.

  - The `index` option refers to the auto-incrementing integer number associated with the file after the first backup, you can easilly retreive it by using the `list` operation (see [Listing backups](#listing-backups) for more information).


The optional `message` argument expects a string to be associated with the backup being made. This is used as a way to describe it and help differentiate it form the other backups on the history. 
  - This message will be displayed alongside the backup when listing changes (see [Listing backups](#listing-backups) for more information).
   
  - This message can be altered at any time using the `reword` operation (see [Managing messages](#managing-messages) for more information).
----


### Listing backups
After creating a backup, you'll need to be able to reference it in order to actually use/modify it, that's when `list` comes in. The `list` operation can be used to retrieve either a **list of all tracked files and their respective indexes** or a **history of changes made to a file** alongside their **timestamp index**, **timestamp**, **date** and **message**.

Here's how you can use the `list` operation:
```console
python backup.py list [index]
```
The only argument here is an optional `index`, this referes to the **index of the file whose history you want to see**. If this argument is omitted, a **full list of tracked files and their indexes** is showed instead.


#### Example
Let's say you have two files currently tracked, `test_file.txt` and `another_test_file.txt`, and you want to see the history of changes of the later.

To start, you would first need to get the index associated with it, which can be done by **omitting the `index` argument** to **get the list of tracked files**:

Input:
```console
python backup.py list
```

Output:
```console
Showing list of tracked files:
( backup index | file path )
0 | C:\VSCode\Python\backup\test_file.txt
1 | C:\VSCode\Python\backup\another_test_file.txt
```

Looking at the list, you can see that the index for `another_test_file.txt` is `1`, so now can retrieve it's history by simply **setting the `index` argument to `1`**:

Input:
```console
python backup.py list 1
```

Output:
```console
Showing backups for:
  1 | C:\VSCode\Python\backup\another_test_file.txt
( timestamp index | timestamp | date | message )
0 | 1740670275737780000 | 2025-02-27 12:31:15 | "add even more text"
1 | 1740670261325164000 | 2025-02-27 12:31:01 | "add some text"
2 | 1740670216326312000 | 2025-02-27 12:30:16 | "first backup"
```
----


### Restoring backups
> [!IMPORTANT] 
> Make sure to read the [Listing backups](#listing-backups) section before proceeding.

TODO

----


### Managing messages
> [!IMPORTANT] 
> Make sure to read the [Listing backups](#listing-backups) section before proceeding.

TODO

----


## How it Works
TODO