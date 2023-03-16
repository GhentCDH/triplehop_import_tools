import asyncio

import asyncpg
import config

import db_base


async def create_user_data():
    pool = await asyncpg.create_pool(**config.DATABASE)

    await db_base.executemany(
        pool,
        """
            INSERT INTO app.user (username, display_name, hashed_password, disabled)
            VALUES (:username, :display_name, :hashed_password, :disabled)
            ON CONFLICT DO NOTHING;
        """,
        [
            {
                "username": "anonymous",
                "display_name": "Not authenticated user",
                "hashed_password": "",
                "disabled": False,
            },
            *config.USERS,
        ],
    )

    await db_base.executemany(
        pool,
        """
            INSERT INTO app.group (project_id, system_name, display_name, description)
            VALUES (
                (SELECT project.id FROM app.project WHERE project.system_name = :project_name),
                :system_name,
                :display_name,
                :description
            )
            ON CONFLICT (project_id, system_name) DO UPDATE
            SET description = EXCLUDED.description;
        """,
        [
            {
                "project_name": "__all__",
                "system_name": "global_admin",
                "display_name": "Global administrator",
                "description": "Users in this group have all permissions",
            },
            {
                "project_name": "__all__",
                "system_name": "anonymous",
                "display_name": "Not authenticated",
                "description": "Users in this group are not authenticated",
            },
            *config.GROUPS,
        ],
    )

    await db_base.executemany(
        pool,
        """
            INSERT INTO app.permission (system_name, display_name, description)
            VALUES (:system_name, :display_name, :description)
            ON CONFLICT (system_name) DO UPDATE
            SET display_name = EXCLUDED.display_name, description = EXCLUDED.description;
        """,
        [
            {
                "system_name": "__all__",
                "display_name": "All permissions",
                "description": "Users in with this permission have all permissions",
            },
            {
                "system_name": "es_index",
                "display_name": "Index data in Elasticsearch",
                "description": "Users in with this permission can run batch jobs to index in elasticsearch",
            },
            {
                "system_name": "get",
                "display_name": "View data",
                "description": "Users with this permission can view data",
            },
            {
                "system_name": "post",
                "display_name": "Create data",
                "description": "Users with this permission can create data",
            },
            {
                "system_name": "put",
                "display_name": "Update data",
                "description": "Users with this permission can update data",
            },
            {
                "system_name": "delete",
                "display_name": "Delete data",
                "description": "Users with this permission can delete data",
            },
            {
                "system_name": "view",
                "display_name": "View fields and groups of fields",
                "description": "Users with this permission can view fields and groups of fields",
            },
            {
                "system_name": "edit",
                "display_name": "Edit fields",
                "description": "Users with this permission can edit fields",
            },
        ],
    )

    await db_base.executemany(
        pool,
        """
            INSERT INTO app.users_groups (user_id, group_id)
            VALUES (
                (SELECT "user".id FROM app.user WHERE "user".username = :username),
                (SELECT "group".id FROM app.group WHERE "group".system_name = :group_name)
            )
            ON CONFLICT (user_id, group_id) DO NOTHING;
        """,
        [
            {
                "username": "anonymous",
                "group_name": "anonymous",
            },
            *config.USERS_GROUPS,
        ],
    )

    await pool.close()


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(create_user_data())
    loop.close()


if __name__ == "__main__":
    main()
