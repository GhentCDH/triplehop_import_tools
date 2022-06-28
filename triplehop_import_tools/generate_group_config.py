import asyncio
import asyncpg
import json

import config
import db_base


async def generate_config():
    pool = await asyncpg.create_pool(**config.DATABASE)
    records = await db_base.fetch(
        pool,
        """
            SELECT "group".id::text, project.system_name as project_name, "group".system_name as group_name
            FROM app.group
            INNER JOIN app.project
                ON "group".project_id = project.id
            WHERE project.system_name = :project_name
            OR project.system_name = '__all__';
        """,
        {
            "project_name": config.PROJECT_NAME,
        },
    )
    groups = {}
    for record in records:
        groups[record["group_name"]] = {
            "id": record["id"],
        }

    with open(f"human_readable_config/groups.json", "w") as f:
        json.dump(dict(sorted(groups.items())), f, indent=4)

    await pool.close()


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(generate_config())
    loop.close()


if __name__ == "__main__":
    main()
