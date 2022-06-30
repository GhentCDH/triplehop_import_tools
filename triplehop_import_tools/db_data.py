import csv
import json
import re
import typing

import aiocache
import asyncpg
import tqdm

from triplehop_import_tools import db_base, db_structure

RE_SOURCE_PROP_INDEX = re.compile(r"^(?P<property>[a-z_]*)\[(?P<index>[0-9]*)\]$")


@aiocache.cached()
async def get_entity_props_lookup(
    pool: asyncpg.pool.Pool,
    project_name: str,
    entity_type_name: str,
) -> typing.Dict:
    result = await db_base.fetchval(
        pool,
        """
            SELECT entity.config->'data'
            FROM app.entity
            INNER JOIN app.project
                ON entity.project_id = project.id
            WHERE project.system_name = :project_name
                AND entity.system_name = :entity_type_name;
        """,
        {
            "project_name": project_name,
            "entity_type_name": entity_type_name,
        },
    )
    if result:
        config = json.loads(result)
        if "fields" in config:
            return {v["system_name"]: k for (k, v) in config["fields"].items()}
    return {}


@aiocache.cached()
async def get_relation_props_lookup(
    pool: asyncpg.pool.Pool,
    project_name: str,
    relation_type_name: str,
) -> typing.Dict:
    result = await db_base.fetchval(
        pool,
        """
            SELECT relation.config->'data'
            FROM app.relation
            INNER JOIN app.project
                ON relation.project_id = project.id
            WHERE project.system_name = :project_name
                AND relation.system_name = :relation_type_name;
        """,
        {
            "project_name": project_name,
            "relation_type_name": relation_type_name,
        },
    )
    if result:
        config = json.loads(result)
        if "fields" in config:
            return {v["system_name"]: k for (k, v) in config["fields"].items()}
    return {}


# If prefix is set, the placeholders should be prefixed, not the property keys themselves
def age_format_properties(properties: typing.Dict, prefix: str = ""):
    formatted_properties = {}
    prefix_id = "id"
    if prefix != "":
        prefix_id = f"{prefix}_id"
    for (key, value) in properties.items():
        value_type = value["type"]
        value_value = value["value"]
        if key == "id":
            if value_type == "int":
                formatted_properties[prefix_id] = int(value_value)
                continue
            else:
                raise Exception("Non-int ids are not yet implemented")
        else:
            key = db_base.dtu(key)
        # TODO: postgis (https://github.com/apache/incubator-age/issues/48)
        if value_type in ["int", "string", "edtf", "array", "geometry"]:
            formatted_properties[f"p_{key}"] = value_value
            continue
        raise Exception(f"Value type {value_type} is not yet implemented")
    return [
        ", ".join(
            [
                f'{k if k != prefix_id else "id"}: ${k}'
                for k in formatted_properties.keys()
            ]
        ),
        formatted_properties,
    ]


def create_properties(
    row: typing.Dict,
    db_props_lookup: typing.Dict,
    prop_conf: typing.Dict,
):
    properties = {}
    for (key, conf) in prop_conf.items():
        if key == "id":
            db_key = "id"
        else:
            db_key = db_props_lookup[key]
        if conf[0] == "int":
            value = row[conf[1]]
            if value in [""]:
                continue
            properties[db_key] = {
                "type": "int",
                "value": int(value),
            }
            continue
        if conf[0] == "string":
            value = row[conf[1]]
            if value in [""]:
                continue
            properties[db_key] = {
                "type": "string",
                "value": value,
            }
            continue
        if conf[0] == "edtf":
            value = row[conf[1]]
            if value in [""]:
                continue
            properties[db_key] = {
                "type": "edtf",
                "value": value,
            }
            continue
        if conf[0] == "[string]":
            value = row[conf[1]]
            if value in [""]:
                continue
            properties[db_key] = {
                "type": "array",
                "value": value.split(conf[2]),
            }
            continue
        if conf[0] == "geometry":
            value = row[conf[1]]
            if value in [""]:
                continue
            properties[db_key] = {
                "type": "geometry",
                "value": json.loads(value),
            }
            continue
        else:
            raise Exception(f"Type {conf[0]} has not yet been implemented")
    return properties


async def batch(method: typing.Callable, data: csv.DictReader, **kwargs):
    counter = 0
    batch = []
    for row in tqdm.tqdm([r for r in data]):
        counter += 1
        batch.append(row)
        if not counter % 5000:
            await method(**kwargs, batch=batch)
            batch = []
    if len(batch):
        await method(**kwargs, batch=batch)


async def import_entities(
    pool: asyncpg.pool.Pool,
    project_name: str,
    username: str,
    conf: typing.Dict,
    lookup: typing.Dict = None,
    lookup_props: typing.List[str] = None,
):
    print(f'Importing entity {conf["entity_type_name"]}')
    with open(f'data/{conf["filename"]}') as data_file:
        data_reader = csv.DictReader(data_file)

        params = {
            "project_name": project_name,
            "entity_type_name": conf["entity_type_name"],
            "username": username,
        }

        db_props_lookup = await get_entity_props_lookup(
            pool=pool,
            project_name=project_name,
            entity_type_name=conf["entity_type_name"],
        )

        await batch(
            method=create_entities,
            data=data_reader,
            pool=pool,
            params=params,
            db_props_lookup=db_props_lookup,
            prop_conf=conf["props"],
        )

    print(f'Creating lookup and index for entity {conf["entity_type_name"]}')

    if conf["entity_type_name"] not in lookup:
        lookup[conf["entity_type_name"]] = {}
    for lookup_prop in lookup_props:
        lookup[conf["entity_type_name"]][lookup_prop] = await create_lookup(
            pool=pool,
            project_name=project_name,
            type_name=conf["entity_type_name"],
            prop_name=lookup_prop,
            type="entity",
        )

    await create_entity_index(
        pool=pool,
        project_name=project_name,
        entity_type_name=conf["entity_type_name"],
    )


async def create_entities(
    pool: asyncpg.pool.Pool,
    params: typing.Dict,
    db_props_lookup: typing.Dict,
    prop_conf: typing.Dict,
    batch: typing.List,
) -> None:
    project_id = await db_structure.get_project_id(pool, params["project_name"])
    entity_type_id = await db_structure.get_entity_type_id(
        pool, params["project_name"], params["entity_type_name"]
    )

    if "id" not in prop_conf:
        id = await db_base.fetchval(
            pool,
            """
                SELECT current_id
                FROM app.entity_count
                WHERE id = :entity_type_id;
            """,
            {"entity_type_id": entity_type_id},
        )
    max_id = 0
    # key: placeholder string
    # value: typing.List with corresponding parameters
    props_collection = {}

    for row in batch:
        properties = create_properties(
            row=row,
            db_props_lookup=db_props_lookup,
            prop_conf=prop_conf,
        )
        if "id" in prop_conf:
            max_id = max(max_id, properties["id"]["value"])
        else:
            id += 1
            max_id = id
            properties["id"] = {
                "type": "int",
                "value": id,
            }

        props = age_format_properties(properties)
        if props[0] in props_collection:
            props_collection[props[0]].append(props[1])
        else:
            props_collection[props[0]] = [props[1]]

    # GREATEST is needed when id in prop_conf
    await db_base.execute(
        pool,
        """
            UPDATE app.entity_count
            SET current_id = GREATEST(current_id, :entity_id)
            WHERE id = :entity_type_id;
        """,
        {"entity_id": max_id, "entity_type_id": entity_type_id},
    )

    for placeholder in props_collection:
        await db_base.executemany(
            pool,
            (
                f"SELECT * FROM cypher("
                f"'{project_id}', "
                f"$$CREATE (\\:n_{db_base.dtu(entity_type_id)} {{{placeholder}}})$$, :params"
                f") as (a agtype);"
            ),
            [
                {"params": json.dumps(params)}
                for params in props_collection[placeholder]
            ],
            True,
        )

    # TODO: revision


async def create_relations(
    pool: asyncpg.pool.Pool,
    params: typing.Dict,
    db_props_lookup: typing.Dict,
    file_header_lookup: typing.Dict,
    domain_conf: typing.Dict,
    range_conf: typing.Dict,
    prop_conf: typing.Dict,
    lookups: typing.Dict,
    batch: typing.List,
) -> None:
    project_id = await db_structure.get_project_id(pool, params["project_name"])
    relation_type_id = await db_structure.get_relation_type_id(
        pool, params["project_name"], params["relation_type_name"]
    )

    if "id" not in prop_conf:
        id = await db_base.fetchval(
            pool,
            """
                SELECT current_id
                FROM app.relation_count
                WHERE id = :relation_type_id;
            """,
            {"relation_type_id": relation_type_id},
        )
    max_id = 0
    # key: placeholder strings separated by | (domain_placeholder|range_placeholder|placeholder)
    # value: typing.List with corresponding parameters
    props_collection = {}

    d_entity_type_name = params["domain_type_name"]
    d_prop_name = list(domain_conf.keys())[0]
    r_entity_type_name = params["range_type_name"]
    r_prop_name = list(range_conf.keys())[0]

    for row in batch:
        properties = create_properties(
            row, db_props_lookup, file_header_lookup, prop_conf
        )

        domain_prop_values = []
        d_prop_values = row[file_header_lookup[list(domain_conf.values())[0][1]]].split(
            "|"
        )
        for d_prop_value in d_prop_values:
            if d_prop_value == "":
                continue
            if list(domain_conf.values())[0][0] == "int":
                d_prop_value = int(d_prop_value)
            if d_prop_value not in lookups[d_entity_type_name][d_prop_name]:
                print(f"{d_prop_value} not found in {d_entity_type_name} {d_prop_name}")
                continue
            domain_prop_values.append(
                lookups[d_entity_type_name][d_prop_name][d_prop_value]
            )

        range_prop_values = []
        r_prop_values = row[file_header_lookup[list(range_conf.values())[0][1]]].split(
            "|"
        )
        for r_prop_value in r_prop_values:
            if r_prop_value == "":
                continue
            if list(range_conf.values())[0][0] == "int":
                r_prop_value = int(r_prop_value)
            if r_prop_value not in lookups[r_entity_type_name][r_prop_name]:
                print(f"{r_prop_value} not found in {r_entity_type_name} {r_prop_name}")
                continue
            range_prop_values.append(
                lookups[r_entity_type_name][r_prop_name][r_prop_value]
            )

        for domain_prop_value in domain_prop_values:
            for range_prop_value in range_prop_values:
                if "id" in prop_conf:
                    max_id = max(max_id, properties["id"]["value"])
                else:
                    id += 1
                    max_id = id
                    properties["id"] = {
                        "type": "int",
                        "value": id,
                    }

                props = age_format_properties(properties)
                key = f"$domain_id|$range_id|{props[0]}"
                if key not in props_collection:
                    props_collection[key] = []

                value = {
                    "domain_id": domain_prop_value,
                    "range_id": range_prop_value,
                    **props[1],
                }
                props_collection[key].append(value)

    # GREATEST is needed when id in prop_conf
    await db_base.execute(
        pool,
        """
            UPDATE app.relation_count
            SET current_id = GREATEST(current_id, :relation_id)
            WHERE id = :relation_type_id;
        """,
        {"relation_id": max_id, "relation_type_id": relation_type_id},
    )

    for placeholder in props_collection:
        query = (
            f"INSERT INTO "
            f'"{project_id}".e_{db_base.dtu(relation_type_id)} '
            f"(start_id, end_id, properties) "
            f"VALUES (:domain_id, :range_id, :properties) "
        )
        await db_base.executemany(
            pool,
            query,
            [
                {
                    "domain_id": params["domain_id"],
                    "range_id": params["range_id"],
                    "properties": json.dumps(
                        {
                            k: params[k]
                            for k in params
                            if k not in ["domain_id", "range_id"]
                        }
                    ),
                }
                for params in props_collection[placeholder]
            ],
            True,
        )
        # Create relation entities to enable source relations
        await db_base.executemany(
            pool,
            (
                f"SELECT * FROM cypher("
                f"'{project_id}', "
                f"$$CREATE (\\:en_{db_base.dtu(relation_type_id)} {{id: $id}})$$, :params"
                f") as (a agtype);"
            ),
            [
                {"params": json.dumps({"id": params["id"]})}
                for params in props_collection[placeholder]
            ],
            True,
        )

    # TODO: revision


async def create_lookup(
    pool: asyncpg.pool.Pool,
    project_name: str,
    type_name: str,
    prop_name: str,
    type: str,
) -> typing.Dict:
    project_id = await db_structure.get_project_id(pool, project_name)
    if type == "entity":
        entity_type_id = await db_structure.get_entity_type_id(
            pool, project_name, type_name
        )

        if prop_name == "id":
            key = "id"
        else:
            db_props_lookup = await get_entity_props_lookup(
                pool, project_name, type_name
            )
            key = f"p_{db_base.dtu(db_props_lookup[prop_name])}"

        records = await db_base.fetch(
            pool,
            (
                f"SELECT * FROM cypher("
                f"'{project_id}', "
                f"$$MATCH"
                f"        (n:n_{db_base.dtu(entity_type_id)})"
                f"return id(n), n.{key}$$"
                f") as (id agtype, prop agtype);"
            ),
            {},
            True,
        )
        return {json.loads(record["prop"]): record["id"] for record in records}
    else:
        relation_type_id = await db_structure.get_relation_type_id(
            pool, project_name, type_name
        )
        records = await db_base.fetch(
            pool,
            (
                f"SELECT * FROM cypher("
                f"'{project_id}', "
                f"$$MATCH"
                f"        (n:en_{db_base.dtu(relation_type_id)})"
                f"return id(n), n.id$$"
                f") as (id agtype, prop agtype);"
            ),
            {},
            True,
        )
        return {json.loads(record["prop"]): record["id"] for record in records}


async def create_entity_index(
    pool: asyncpg.pool.Pool,
    project_name: str,
    entity_type_name: str,
) -> None:
    project_id = await db_structure.get_project_id(pool, project_name)
    entity_type_id = await db_structure.get_entity_type_id(
        pool, project_name, entity_type_name
    )

    records = await db_base.fetch(
        pool,
        (
            f"SELECT * FROM cypher("
            f"'{project_id}', "
            f"$$MATCH"
            f"        (n:n_{db_base.dtu(entity_type_id)})"
            f"return n$$"
            f") as (n agtype);"
        ),
        {},
        True,
    )

    index = []
    for raw_record in records:
        record = json.loads(raw_record["n"][:-8])
        index.append(
            {
                "id": record["properties"]["id"],
                "nid": str(record["id"]),
            }
        )

    # Primary key is indexed automatically
    await db_base.execute(
        pool,
        (
            f'CREATE TABLE "{project_id}"._i_n_{db_base.dtu(entity_type_id)} ('
            f"    id INT PRIMARY KEY,"
            f"    nid GRAPHID"
            f");"
        ),
        {},
        True,
    )

    await db_base.executemany(
        pool,
        (
            f'INSERT INTO "{project_id}"._i_n_{db_base.dtu(entity_type_id)} '
            f"(id, nid) "
            f"VALUES (:id, :nid);"
        ),
        index,
        True,
    )

    await db_base.execute(
        pool,
        f"CREATE INDEX n_{db_base.dtu(entity_type_id)}__id "
        f'ON "{project_id}".n_{db_base.dtu(entity_type_id)}(id)',
    )


async def create_relation_entity_index(
    pool: asyncpg.pool.Pool,
    project_name: str,
    relation_type_name: str,
) -> None:
    project_id = await db_structure.get_project_id(pool, project_name)
    relation_type_id = await db_structure.get_relation_type_id(
        pool, project_name, relation_type_name
    )

    records = await db_base.fetch(
        pool,
        (
            f"SELECT * FROM cypher("
            f"'{project_id}', "
            f"$$MATCH"
            f"        (n:en_{db_base.dtu(relation_type_id)})"
            f"return n$$"
            f") as (n agtype);"
        ),
        {},
        True,
    )

    index = []
    for raw_record in records:
        record = json.loads(raw_record["n"][:-8])
        index.append(
            {
                "id": record["properties"]["id"],
                "nid": str(record["id"]),
            }
        )

    # Primary key is indexed automatically
    await db_base.execute(
        pool,
        (
            f'CREATE TABLE IF NOT EXISTS "{project_id}"._i_en_{db_base.dtu(relation_type_id)} ('
            f"    id INT PRIMARY KEY,"
            f"    nid GRAPHID"
            f");"
        ),
        {},
        True,
    )

    await db_base.executemany(
        pool,
        (
            f'INSERT INTO "{project_id}"._i_en_{db_base.dtu(relation_type_id)} '
            f"(id, nid) "
            f"VALUES (:id, :nid) "
            f"ON CONFLICT DO NOTHING;"
        ),
        index,
        True,
    )

    await db_base.execute(
        pool,
        f"CREATE INDEX IF NOT EXISTS en_{db_base.dtu(relation_type_id)}__id "
        f'ON "{project_id}".en_{db_base.dtu(relation_type_id)}(id)',
    )


async def delete_source_relations(
    pool: asyncpg.pool.Pool,
    project_name: str,
) -> None:
    project_id = await db_structure.get_project_id(pool, project_name)

    query = f'DELETE FROM "{project_id}"._source_;'
    try:
        await db_base.execute(
            pool,
            query,
            age=True,
        )
    except asyncpg.exceptions.UndefinedTableError:
        print("No source relations found")


async def create_entity_source_relations(
    pool: asyncpg.pool.Pool,
    project_name: str,
    lookups: typing.Dict,
    batch: typing.List,
) -> None:
    project_id = await db_structure.get_project_id(pool, project_name)

    # group parameters by domain, range and source properties to be added
    props_collection = {}

    id = await db_base.fetchval(
        pool,
        """
            SELECT current_id
            FROM app.relation_count
            INNER JOIN app.relation on relation_count.id = relation.id
            WHERE relation.system_name = :relation_type_name
        """,
        {"relation_type_name": "_source_"},
    )

    for row in batch:

        # Add domain and range to lookups
        for et in [row["entity_type"], row["source_type"]]:
            if et not in lookups:
                lookups[et] = await create_lookup(pool, project_name, et, "id")

        # Check if the entity and source nodes exist
        if row["entity_id"] not in lookups[row["entity_type"]]:
            print(f'{row["entity_id"]} not found in {row["entity_type"]}')
            continue
        if row["source_id"] not in lookups[row["source_type"]]:
            print(f'{row["source_id"]} not found in {row["source_type"]}')
            continue

        source_props_placeholder = "id : $id, properties: $properties"
        key = f"$domain_id|$range_id|{source_props_placeholder}"

        if key not in props_collection:
            props_collection[key] = []

        # Create lookup to convert property system names to property ids
        props_lookup = await get_entity_props_lookup(
            pool, project_name, row["entity_type"]
        )

        id += 1
        uuid_props = []
        for p in row["properties"]:
            m = RE_SOURCE_PROP_INDEX.match(p)
            if m:
                uuid_props.append(
                    f'{props_lookup[m.group("property")]}[{m.group("index")}]'
                )
            else:
                uuid_props.append(props_lookup[p])

        props = {
            "domain_id": lookups[row["entity_type"]][row["entity_id"]],
            "range_id": lookups[row["source_type"]][row["source_id"]],
            "id": id,
            "properties": uuid_props,
        }
        # Only add source_props if not empty
        if row["source_props"]:
            props["source_props"] = row["source_props"]
        props_collection[key].append(props)

    for placeholder in props_collection:
        query = (
            f"INSERT INTO "
            f'"{project_id}"._source_ '
            f"(start_id, end_id, properties) "
            f"VALUES (:domain_id, :range_id, :properties) "
        )
        await db_base.executemany(
            pool,
            query,
            [
                {
                    "domain_id": params["domain_id"],
                    "range_id": params["range_id"],
                    "properties": json.dumps(
                        {
                            k: params[k]
                            for k in params
                            if k not in ["domain_id", "range_id"]
                        }
                    ),
                }
                for params in props_collection[placeholder]
            ],
            True,
        )

    await db_base.execute(
        pool,
        """
            UPDATE app.relation_count
            SET current_id = :id
            WHERE id = (
                SELECT id from app.relation where system_name = :relation_type_name
            )
        """,
        {"id": id, "relation_type_name": "_source_"},
    )


async def create_relation_source_relations(
    pool: asyncpg.pool.Pool,
    project_name: str,
    lookups: typing.Dict,
    batch: typing.List,
) -> None:
    project_id = await db_structure.get_project_id(pool, project_name)

    # group parameters by domain, range and source properties to be added
    props_collection = {}

    id = await db_base.fetchval(
        pool,
        """
            SELECT current_id
            FROM app.relation_count
            INNER JOIN app.relation on relation_count.id = relation.id
            WHERE relation.system_name = :relation_type_name
        """,
        {"relation_type_name": "_source_"},
    )

    for row in batch:
        # Add domain and range to lookups
        rt = row["relation_type"]
        if f"r_{rt}" not in lookups:
            lookups[f"r_{rt}"] = await create_lookup(
                pool, project_name, rt, "id", "relation"
            )

        et = row["source_type"]
        if f"e_{et}" not in lookups:
            lookups[f"e_{et}"] = await create_lookup(pool, project_name, et, "id")

        # Check if the entity and source nodes exist
        if row["relation_id"] not in lookups[f'r_{row["relation_type"]}']:
            print(f'{row["relation_id"]} not found in {row["relation_type"]}')
            continue
        if row["source_id"] not in lookups[f'e_{row["source_type"]}']:
            print(f'{row["source_id"]} not found in {row["source_type"]}')
            continue

        source_props_placeholder = "id : $id, properties: $properties"
        key = f"$domain_id|$range_id|{source_props_placeholder}"

        if key not in props_collection:
            props_collection[key] = []

        # Create lookup to convert property system names to property ids
        props_lookup = await get_relation_props_lookup(
            pool, project_name, row["relation_type"]
        )
        props_lookup["__rel__"] = "__rel__"

        id += 1
        uuid_props = []
        for p in row["properties"]:
            m = RE_SOURCE_PROP_INDEX.match(p)
            if m:
                uuid_props.append(
                    f'{props_lookup[m.group("property")]}[{m.group("index")}]'
                )
            else:
                uuid_props.append(props_lookup[p])
        props = {
            "domain_id": lookups[f'r_{row["relation_type"]}'][row["relation_id"]],
            "range_id": lookups[f'e_{row["source_type"]}'][row["source_id"]],
            "id": id,
            "properties": uuid_props,
        }
        # Only add source_props if not empty
        if row["source_props"]:
            props["source_props"] = row["source_props"]
        props_collection[key].append(props)

    for placeholder in props_collection:
        query = (
            f"INSERT INTO "
            f'"{project_id}"._source_ '
            f"(start_id, end_id, properties) "
            f"VALUES (:domain_id, :range_id, :properties) "
        )
        await db_base.executemany(
            pool,
            query,
            [
                {
                    "domain_id": params["domain_id"],
                    "range_id": params["range_id"],
                    "properties": json.dumps(
                        {
                            k: params[k]
                            for k in params
                            if k not in ["domain_id", "range_id"]
                        }
                    ),
                }
                for params in props_collection[placeholder]
            ],
            True,
        )

    await db_base.execute(
        pool,
        """
            UPDATE app.relation_count
            SET current_id = :id
            WHERE id = (
                SELECT id from app.relation where system_name = :relation_type_name
            )
        """,
        {"id": id, "relation_type_name": "_source_"},
    )
