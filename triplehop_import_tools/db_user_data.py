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
            INSERT INTO app.users_groups (user_id, group_id)
            VALUES (
                (SELECT "user".id FROM app.user WHERE "user".username = :username),
                (SELECT "group".id FROM app.group WHERE "group".system_name = :group_system_name AND "group".project_id = (SELECT project.id FROM app.project WHERE project.system_name = :group_project_name))
            )
            ON CONFLICT (user_id, group_id) DO NOTHING;
        """,
        [
            {
                "username": "anonymous",
                "group_system_name": "anonymous",
                "group_project_name": "__all__",
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
