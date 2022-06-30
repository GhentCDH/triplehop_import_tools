import asyncio
import json

import asyncpg
import config

import db_base


async def generate_config():
    pool = await asyncpg.create_pool(**config.DATABASE)
    records = await db_base.fetch(
        pool,
        """
            SELECT relation.id::text, relation.system_name
            FROM app.relation
            INNER JOIN app.project
                ON relation.project_id = project.id
            WHERE project.system_name = :project_name;
        """,
        {
            "project_name": config.PROJECT_NAME,
        },
    )
    relations = {}
    for record in records:
        relations[record["system_name"]] = {
            "id": record["id"],
        }

        for relation in relations:
            id = relations[relation]["id"]
            # todo: relations with multiple domains / ranges?
            records = await db_base.fetch(
                pool,
                """
                    SELECT entity.system_name
                    FROM app.relation_domain
                    INNER JOIN app.entity
                        ON relation_domain.entity_id = entity.id
                    WHERE relation_domain.relation_id = :relation_id;
                """,
                {
                    "relation_id": id,
                },
            )
            if len(records) == 1:
                relations[relation]["domain"] = records[0]["system_name"]
            else:
                relations[relation]["domain"] = None
            records = await db_base.fetch(
                pool,
                """
                    SELECT entity.system_name
                    FROM app.relation_range
                    INNER JOIN app.entity
                        ON relation_range.entity_id = entity.id
                    WHERE relation_range.relation_id = :relation_id;
                """,
                {
                    "relation_id": id,
                },
            )
            if len(records) == 1:
                relations[relation]["range"] = records[0]["system_name"]
            else:
                relations[relation]["range"] = None

    with open(f"human_readable_config/relations.json", "w") as f:
        json.dump(dict(sorted(relations.items())), f, indent=4)

    await pool.close()


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(generate_config())
    loop.close()


if __name__ == "__main__":
    main()
