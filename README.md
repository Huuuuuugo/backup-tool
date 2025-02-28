# BackTrack: Simple Versioned Backups for Files Anywhere on the System
BackTrack is a lightweight, command-line backup tool written in pure Python that lets you create timestamped versions of files anywhere on the system. Designed for simplicity and storage efficiency, it helps you track changes, restore previous states, and add context to backups with descriptive messages without worring about wasting storage space — perfect for users who want Git-like versioning on limited storage without the complexity of full VCS systems.

Key Features:
  - **Versioned Backups**: Automatically track file changes with incremental timestamps.
  
  - **Storage efficiency**: Save a compressed version containing only the changed portions of a file.

  - **Global backups**: Create or restore backups from anywhere on the sytem.

  - **Intuitive Index System**: Reference files by auto-generated backup indexes for quick operations.

  - **Backup Messaging**: Add/update descriptions to backups (e.g., "Fixed config bug").


  - **Cross-Platform**: Works anywhere Python runs (Windows/macOS/Linux).

  - **CLI-First Design**: Simple commands for creating, restoring, and managing backups.

## Installation
TODO

## Usage
### General usage
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

> [!TIP]
> #### Example
> Let's say you want to create the first backup of a file named `test_file.txt` located on the current working directory, to do so, you can run the following command:
>
> Input:
> ```console
> python backup.py test_file.txt
> ```
>
> Output:
> ```console
> New backup created for file 'C:\VSCode\Python\backup\test_file.txt'
> ```
>
> After this initial backup, you can now use the **backup index** of the tracked file for all subsequent backups (see [Listing backups](#listing-backups) for more information on how to retrieve this value):
>
> Input:
> ```console
> python backup.py 0
> ```
>
> Output:
> ```console
> New backup created for file 'C:\VSCode\Python\backup\test_file.txt'
> ```


----


### Listing backups
After creating a backup, you'll need to be able to reference it in order to actually use/modify it, that's where `list` comes in. The `list` operation can be used to retrieve either a **list of all tracked files and their respective indexes** or a **history of changes made to a file** alongside their **timestamp index**, **timestamp**, **date** and **message**.

Here's how you can use the `list` operation:
```console
python backup.py list [index]
```
The only argument here is an optional `index`, this referes to the **backup index of the tracked file whose history you want to see**. If this argument is omitted, a **full list of tracked files and their indexes** is shown instead.

> [!TIP]
> #### Example
> Let's say you have two files currently tracked, `test_file.txt` and `another_test_file.txt`, and you want to see the backup history of the later.
> 
> To start, you would first need to get the index associated with it, which can be done by **omitting the `index` argument** to **get the list of tracked files**:
> 
> Input:
> ```console
> python backup.py list
> ```
> 
> Output:
> ```console
> Showing list of tracked files:
> ( backup index | file path )
> 0 | C:\VSCode\Python\backup\test_file.txt
> 1 | C:\VSCode\Python\backup\another_test_file.txt
> ```
> 
> Looking at the list, you can see that the index for `another_test_file.txt` is `1`, so now can retrieve its history by simply **setting the `index` argument to `1`**:
> 
> Input:
> ```console
> python backup.py list 1
> ```
> 
> Output:
> ```console
> Showing backups for:
>   1 | C:\VSCode\Python\backup\another_test_file.txt
> ( timestamp index | timestamp | date | message )
> 0 | 1740670275737780000 | 2025-02-27 12:31:15 | "add even more text"
> 1 | 1740670261325164000 | 2025-02-27 12:31:01 | "add some text"
> 2 | 1740670216326312000 | 2025-02-27 12:30:16 | "first backup"
> ```
----


### Restoring backups
> [!IMPORTANT] 
> Make sure to read the [Listing backups](#listing-backups) section before proceeding.

> [!CAUTION]
> When restoring a file, make sure to backup any unsaved changes or else those **will be lost** when replacing the file with the restored version!

To restore a backup, use the following command:
```console
python backup.py restore <index> <timestamp_or_index>
```
The `index` argument is used to **identify the file being restored**, it expects an integer containing the **backup index of a tracked file**. 
  - This value should be retrieved using the `list` operation as shown in the example from the [Listing backups](#listing-backups) section.

The `timestamp_or_index` argument, on the other hand, is used to **identify the backup being restored**, it expects the **timestamp** or **timestamp index** of the backup.
  - This index auto increments starting at **0** on the **most recent backup**, so the latest backup has index 0, de second last has index 1, and so on.
  - This value should also be retrieved using the `list` operation as shown in the example from the [Listing backups](#listing-backups) section.


> [!TIP]
> #### Example
> Going back to the example from the [Listing backups](#listing-backups) section, after using the `list` command we retrieved the following output:
> ```console
> Showing backups for:
>   1 | C:\VSCode\Python\backup\another_test_file.txt
> ( timestamp index | timestamp | date | message )
> 0 | 1740670275737780000 | 2025-02-27 12:31:15 | "add even more text"
> 1 | 1740670261325164000 | 2025-02-27 12:31:01 | "add some text"
> 2 | 1740670216326312000 | 2025-02-27 12:30:16 | "first backup"
> ```
> Now, let's say you want to restore the backup with the message "first backup". Looking at the output we can see that the **backup index** is **1**, as shown on the top left, and the **timestamp index** is **2**, as shown on the first column of the bottom row, so, to restore that version of the file we simply run the following command:
> 
> Input:
> ```console
> python backup.py restore 1 2
> ```
>
> Output:
> ```console
> Backup with timestamp '1740670216326312000' and message "first backup" restored for file 'C:\VSCode\Python\backup\another_test_file.txt'
> ```
----


### Managing messages
> [!IMPORTANT] 
> Make sure to read the [Listing backups](#listing-backups) section before proceeding.

> [!NOTE]
> It's recommended to read the [Restoring backups](#restoring-backups) section before proceeding.

To create or update the message from a backup, use:
```console
python backup.py reword <index> <timestamp_or_index> <message>
```
The `index` and `timestamp_or_index` work exactly the same way as in the `restore` operation:
  - `index`: identifies the file being restored;
  - `timestamp_or_index`: identifies the backup being restored;
  - both values should be retrieved using the `list` operation as shown in the example from the [Listing backups](#listing-backups) section.

> [!TIP]
> #### Example
> Going back to the example from the [Listing backups](#listing-backups) section, after using the `list` command we retrieved the following output:
> ```console
> Showing backups for:
>   1 | C:\VSCode\Python\backup\another_test_file.txt
> ( timestamp index | timestamp | date | message )
> 0 | 1740670275737780000 | 2025-02-27 12:31:15 | "add even more text"
> 1 | 1740670261325164000 | 2025-02-27 12:31:01 | "add some text"
> 2 | 1740670216326312000 | 2025-02-27 12:30:16 | "first backup"
> ```
> Now, let's say you want to change the message of the latest backup "new message". Looking at the output we can see that the **backup index** is **1** and the **timestamp index** is **2**, to change the message, we can run:
>
> Input:
> ```console
> python backup.py reword 1 0 "new message"
> ```
>
> Output:
> ```console
> Update message from 'add even more text' to 'new message' for backup with timestamp '1740670275737780000' for file 'C:\VSCode\Python\backup\another_test_file.txt'
> ```
----

### Migrating backups
By default, BackTrack uses the `platformdirs` module to get the most appropriate place for backups depending on your operating system, but you may want to change it to a directory that's automatically synced to a cloud storage service, for example. To do that you can use the following command:
```console
python backup.py [new_dir]
```
The argument `new_dir`, as the name implies, expects the path of the new directory to where you want to move your backups. If this value is omitted, the backups will be moved back to the default location instead.

----


## How it Works
TODO