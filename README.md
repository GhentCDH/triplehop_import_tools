TripleHop import tools
======================

Add basic db structure
----------------------

The basic db structure can be set up using the `db_app.py` python script. Make sure a `config.py` file exists at the same level as the `triplehop_import_tools` with a `DATABASE` variable:

```py
DATABASE = {
    'host': '',
    'database': '',
    'user': '',
    'password': '',
}
```

The script can then be used as follows:

```sh
python triplehop_import_tools/triplehop_import_tools/db_app.py
```

Process config
--------------

Human readable config files can be converted to machine readable ones using the `process_config.py` python script.

The human readable config files should be contained in a folder named `human_readable_config`. The script can then be used as follows:

```sh
python triplehop_import_tools/triplehop_import_tools/process_config.py
```
