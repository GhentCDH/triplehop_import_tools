TripleHop import tools
======================

Add basic db structure
----------------------

The basic db structure can be set up using the `db_app.py` python script. Make sure a `config.py` file exists at the same level as the `triplehop_import_tools` with a `DATABASE` variable:

```py
DATABASE = {
    "host": "",
    "database": "",
    "user": "",
    "password": "",
}
```

The script can then be used as follows:

```sh
python triplehop_import_tools/triplehop_import_tools/db_app.py
```

Add User data
-------------

The user data can be imported using the `db_user_data.py` python script. A system user and anonymous user are created automatically, as well as an anonymous and global_admin group and all required permissions. The anonymous user is automatically linked to the anonymous group. Make sure a `config.py` file exists at the same level as the `triplehop_import_tools` with a `DATABASE`, `USERS` and a `USERS_GROUPS` variable:

```py
DATABASE = {
    "host": "",
    "database": "",
    "user": "",
    "password": "",
}

USERS = [
    {
        "username": "",
        "display_name": "",
        "hashed_password": "",
        "disabled": False,
    },
]

USERS_GROUPS = [
    {
        "username": "",
        "group_name": "",
    },
]
```

The script can then be used as follows:

```sh
python triplehop_import_tools/triplehop_import_tools/db_user_data.py
```

Add db structure for revisions
------------------------------

The db structure for revisions can be set up using the `db_revision.py` python script. Make sure a `config.py` file exists at the same level as the `triplehop_import_tools` with a `DATABASE` variable:

```py
DATABASE = {
    "host": "",
    "database": "",
    "user": "",
    "password": "",
}
```

The script can then be used as follows:

```sh
python triplehop_import_tools/triplehop_import_tools/db_revision.py
```

Generate group config
---------------------

Group configs can be exported to JSON files using the `generate_group_config.py` python script. Make sure a `config.py` file exists at the same level as the `triplehop_import_tools` with a `PROJECT_NAME` and `DATABASE` variable:

```py
PROJECT_NAME = ""

DATABASE = {
    "host": "",
    "database": "",
    "user": "",
    "password": "",
}
```

The script can then be used as follows:

```sh
python triplehop_import_tools/triplehop_import_tools/generate_group_config.py
```

Process config
--------------

Human readable config files can be converted to machine readable ones using the `process_config.py` python script.

The human readable config files should be contained in a folder named `human_readable_config`. The script can then be used as follows:

```sh
python triplehop_import_tools/triplehop_import_tools/process_config.py
```
