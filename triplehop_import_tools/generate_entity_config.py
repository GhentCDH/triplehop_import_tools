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
            SELECT entity.id::text, entity.system_name
            FROM app.entity
            INNER JOIN app.project
                ON entity.project_id = project.id
            WHERE project.system_name = :project_name;
        """,
        {
            "project_name": config.PROJECT_NAME,
        },
    )
    entities = {}
    for record in records:
        entities[record["system_name"]] = {
            "id": record["id"],
        }

    with open(f"human_readable_config/entities.json", "w") as f:
        json.dump(dict(sorted(entities.items())), f, indent=4)

    await pool.close()


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(generate_config())
    loop.close()


if __name__ == "__main__":
    main()
