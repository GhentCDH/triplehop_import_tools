import asyncio
import asyncpg
import sys

import db_base

sys.path.append("../..")
import config


async def create_app_structure():
    pool = await asyncpg.create_pool(**config.DATABASE)

    await db_base.execute(
        pool,
        """
            DROP SCHEMA IF EXISTS app CASCADE;
        """,
    )

    await db_base.execute(
        pool,
        """
            CREATE SCHEMA app;
        """,
    )

    await db_base.execute(
        pool,
        """
            CREATE TABLE app.user (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                username VARCHAR NOT NULL,
                display_name VARCHAR NOT NULL,
                hashed_password VARCHAR NOT NULL,
                disabled BOOLEAN NOT NULL,
                created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                modified TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                UNIQUE (username)
            );
        """,
    )
    # TODO: user revision?

    await db_base.execute(
        pool,
        """
            INSERT INTO app.user (username, display_name, hashed_password, disabled)
            VALUES (:username, :display_name, :hashed_password, :disabled);
        """,
        {
            "username": "system",
            "display_name": "System user",
            "hashed_password": "",
            "disabled": True,
        },
    )

    await db_base.execute(
        pool,
        """
            CREATE TABLE app.token_denylist (
                token VARCHAR PRIMARY KEY,
                expires TIMESTAMP WITH TIME ZONE NOT NULL
            );
        """,
    )

    await db_base.execute(
        pool,
        """
            CREATE TABLE app.project (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                system_name VARCHAR NOT NULL,
                display_name VARCHAR NOT NULL,
                user_id UUID NOT NULL
                    REFERENCES app.user (id)
                    ON UPDATE RESTRICT ON DELETE RESTRICT,
                created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                modified TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                UNIQUE (system_name)
            );
        """,
    )

    await db_base.execute(
        pool,
        """
            INSERT INTO app.project (system_name, display_name, user_id)
            VALUES (
                :system_name,
                :display_name,
                (SELECT "user".id FROM app.user WHERE "user".username = :username)
            );
        """,
        {
            "system_name": "__all__",
            "display_name": "All projects",
            "username": "system",
        },
    )

    # TODO: project revision?
    # CREATE TABLE app.revision_project (
    #   id SERIAL PRIMARY KEY,
    #   project_id INTEGER
    #     REFERENCES app.project
    #     ON UPDATE NO ACTION ON DELETE  NO ACTION,
    #   system_name VARCHAR NOT NULL,
    #   display_name VARCHAR NOT NULL,
    #   user_id INTEGER
    #     REFERENCES app.user
    #     ON UPDATE RESTRICT ON DELETE RESTRICT,
    #   created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    #   modified TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
    # );

    await db_base.execute(
        pool,
        """
            CREATE TABLE app.group (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID NOT NULL
                    REFERENCES app.project
                    ON UPDATE CASCADE ON DELETE CASCADE,
                system_name VARCHAR NOT NULL,
                display_name VARCHAR NOT NULL,
                description TEXT,
                created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                modified TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                UNIQUE (project_id, system_name)
            );
        """,
    )
    # TODO: group revision?

    await db_base.execute(
        pool,
        """
            CREATE TABLE app.permission (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                system_name VARCHAR NOT NULL,
                display_name VARCHAR NOT NULL,
                description TEXT,
                created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                modified TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                UNIQUE (system_name)
            );
        """,
    )
    # TODO: permission revision?

    await db_base.execute(
        pool,
        """
            CREATE TABLE app.users_groups (
                user_id UUID NOT NULL
                    REFERENCES app.user (id)
                    ON UPDATE RESTRICT ON DELETE RESTRICT,
                group_id UUID NOT NULL
                    REFERENCES app.group (id)
                    ON UPDATE RESTRICT ON DELETE RESTRICT,
                created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                modified TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                UNIQUE (user_id, group_id)
            );
        """,
    )
    # TODO: users_groups revision?

    await db_base.execute(
        pool,
        """
            CREATE TABLE app.entity (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID NOT NULL
                    REFERENCES app.project
                    ON UPDATE CASCADE ON DELETE CASCADE,
                system_name VARCHAR NOT NULL,
                display_name VARCHAR NOT NULL,
                config JSON,
                user_id UUID NOT NULL
                    REFERENCES app.user (id)
                    ON UPDATE RESTRICT ON DELETE RESTRICT,
                created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                modified TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                UNIQUE (project_id, system_name)
            );
        """,
    )
    await db_base.execute(
        pool,
        """
            CREATE INDEX ON app.entity (project_id);
        """,
    )

    await db_base.execute(
        pool,
        """
            INSERT INTO app.entity (project_id, system_name, display_name, user_id)
            VALUES (
                (SELECT project.id FROM app.project WHERE project.system_name = :project_name),
                :system_name,
                :display_name,
                (SELECT "user".id FROM app.user WHERE "user".username = :username)
            );
        """,
        {
            "project_name": "__all__",
            "system_name": "__all__",
            "display_name": "All entities",
            "username": "system",
        },
    )

    await db_base.execute(
        pool,
        """
            CREATE TABLE app.entity_count (
                id UUID NOT NULL
                    REFERENCES app.entity (id)
                    ON UPDATE RESTRICT ON DELETE CASCADE,
                current_id INTEGER NOT NULL DEFAULT 0,
                UNIQUE (id)
            );
        """,
    )

    await db_base.execute(
        pool,
        """
            CREATE TABLE app.entity_revision (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                entity_id UUID
                    REFERENCES app.entity
                    ON UPDATE RESTRICT ON DELETE SET NULL,
                project_id UUID
                    REFERENCES app.project (id)
                    ON UPDATE RESTRICT ON DELETE SET NULL,
                system_name VARCHAR NOT NULL,
                display_name VARCHAR NOT NULL,
                config JSON,
                user_id UUID NOT NULL
                    REFERENCES app.user (id)
                    ON UPDATE RESTRICT ON DELETE RESTRICT,
                created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
            );
        """,
    )

    # TODO: cardinality
    # TODO: bidirectional relations

    await db_base.execute(
        pool,
        """
            CREATE TABLE app.relation (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID NOT NULL
                    REFERENCES app.project
                    ON UPDATE CASCADE ON DELETE CASCADE,
                system_name VARCHAR NOT NULL,
                display_name VARCHAR NOT NULL,
                config JSON,
                user_id UUID NOT NULL
                    REFERENCES app.user (id)
                    ON UPDATE RESTRICT ON DELETE RESTRICT,
                created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                modified TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                UNIQUE (project_id, system_name)
            );
        """,
    )
    await db_base.execute(
        pool,
        """
            CREATE INDEX ON app.relation (project_id);
        """,
    )

    await db_base.execute(
        pool,
        """
            CREATE TABLE app.relation_count (
                id UUID NOT NULL
                    REFERENCES app.relation (id)
                    ON UPDATE RESTRICT ON DELETE RESTRICT,
                current_id INTEGER NOT NULL DEFAULT 0,
                UNIQUE (id)
            );
        """,
    )

    await db_base.execute(
        pool,
        """
            INSERT INTO app.relation (project_id, system_name, display_name, user_id)
            VALUES (
                (SELECT project.id FROM app.project WHERE project.system_name = :project_name),
                :system_name,
                :display_name,
                (SELECT "user".id FROM app.user WHERE "user".username = :username)
            );
        """,
        {
            "project_name": "__all__",
            "system_name": "__all__",
            "display_name": "All relations",
            "username": "system",
        },
    )

    await db_base.execute(
        pool,
        """
            CREATE TABLE app.relation_domain (
                relation_id UUID NOT NULL
                    REFERENCES app.relation (id)
                    ON UPDATE CASCADE ON DELETE CASCADE,
                entity_id UUID NOT NULL
                    REFERENCES app.entity (id)
                    ON UPDATE CASCADE ON DELETE CASCADE,
                user_id UUID NOT NULL
                    REFERENCES app.user (id)
                    ON UPDATE RESTRICT ON DELETE RESTRICT,
                created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                modified TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                UNIQUE (relation_id, entity_id)
            );
        """,
    )

    await db_base.execute(
        pool,
        """
            CREATE TABLE app.relation_range (
                relation_id UUID NOT NULL
                    REFERENCES app.relation (id)
                    ON UPDATE CASCADE ON DELETE CASCADE,
                entity_id UUID NOT NULL
                    REFERENCES app.entity (id)
                    ON UPDATE CASCADE ON DELETE CASCADE,
                user_id UUID NOT NULL
                    REFERENCES app.user (id)
                    ON UPDATE RESTRICT ON DELETE RESTRICT,
                created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                modified TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                UNIQUE (relation_id, entity_id)
            );
        """,
    )

    await db_base.execute(
        pool,
        """
            CREATE TABLE app.relation_revision (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                relation_id UUID
                    REFERENCES app.relation
                    ON UPDATE RESTRICT ON DELETE SET NULL,
                project_id UUID
                    REFERENCES app.project (id)
                    ON UPDATE RESTRICT ON DELETE SET NULL,
                system_name VARCHAR NOT NULL,
                display_name VARCHAR NOT NULL,
                config JSON,
                user_id UUID NOT NULL
                    REFERENCES app.user (id)
                    ON UPDATE RESTRICT ON DELETE RESTRICT,
                created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
            );
        """,
    )

    await db_base.execute(
        pool,
        """
            CREATE TABLE app.job (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL
                    REFERENCES app.user (id)
                    ON UPDATE RESTRICT ON DELETE RESTRICT,
                project_id UUID
                    REFERENCES app.project (id)
                    ON UPDATE RESTRICT ON DELETE RESTRICT,
                entity_id UUID
                    REFERENCES app.entity (id)
                    ON UPDATE RESTRICT ON DELETE RESTRICT,
                relation_id UUID
                    REFERENCES app.relation (id)
                    ON UPDATE RESTRICT ON DELETE RESTRICT,
                type VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                counter INTEGER,
                total INTEGER,
                created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                started TIMESTAMP WITH TIME ZONE,
                ended TIMESTAMP WITH TIME ZONE
            );
        """,
    )

    await pool.close()


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(create_app_structure())
    loop.close()


if __name__ == "__main__":
    main()
