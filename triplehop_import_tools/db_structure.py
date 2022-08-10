import typing

import aiocache
import asyncpg

from triplehop_import_tools import db_base


def read_config_from_file(type: str, system_name: str):
    with open(f"config/{type}/{system_name}.json") as config_file:
        return config_file.read()


@aiocache.cached()
async def get_project_id(pool: asyncpg.pool.Pool, project_name: str) -> str:
    return await db_base.fetchval(
        pool,
        """
            SELECT project.id::text
            FROM app.project
            WHERE project.system_name = :project_name;
        """,
        {
            "project_name": project_name,
        },
    )


@aiocache.cached()
async def get_entity_type_id(
    pool: asyncpg.pool.Pool, project_name: str, entity_type_name: str
) -> str:
    return await db_base.fetchval(
        pool,
        """
            SELECT entity.id::text
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


@aiocache.cached()
async def get_relation_type_id(
    pool: asyncpg.pool.Pool, project_name: str, relation_type_name: str
) -> str:
    return await db_base.fetchval(
        pool,
        """
            SELECT relation.id::text
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


@aiocache.cached()
async def get_user_id(pool: asyncpg.pool.Pool, username: str) -> str:
    return await db_base.fetchval(
        pool,
        """
            SELECT "user".id
            FROM app.user
            WHERE "user".username = :username;
        """,
        {
            "username": username,
        },
    )


async def create_project_config(
    pool: asyncpg.pool.Pool,
    system_name: str,
    display_name: str,
    username: str,
):
    await db_base.execute(
        pool,
        """
            INSERT INTO app.project (system_name, display_name, user_id)
            VALUES (
                :system_name,
                :display_name,
                (SELECT "user".id FROM app.user WHERE "user".username = :username)
            )
            ON CONFLICT DO NOTHING;
        """,
        {
            "system_name": system_name,
            "display_name": display_name,
            "username": username,
        },
    )


async def create_entity_config(
    pool: asyncpg.pool.Pool,
    project_name: str,
    username: str,
    system_name: str,
    display_name: str,
    config: typing.Dict,
):
    await db_base.execute(
        pool,
        """
            INSERT INTO app.entity (project_id, system_name, display_name, config, user_id)
            VALUES (
                (SELECT project.id FROM app.project WHERE system_name = :project_name),
                :system_name,
                :display_name,
                :config,
                (SELECT "user".id FROM app.user WHERE "user".username = :username)
            )
            ON CONFLICT (project_id, system_name) DO UPDATE
            SET config = EXCLUDED.config;
        """,
        {
            "project_name": project_name,
            "system_name": system_name,
            "display_name": display_name,
            "config": config,
            "username": username,
        },
    )
    await db_base.execute(
        pool,
        """
            INSERT INTO app.entity_revision (entity_id, project_id, system_name, display_name, config, user_id)
            SELECT id, project_id, system_name, display_name, config, user_id
            FROM app.entity
            WHERE system_name = :system_name;
        """,
        {
            "system_name": system_name,
        },
    )
    await db_base.execute(
        pool,
        """
            INSERT INTO app.entity_count (id)
            VALUES (
                (SELECT entity.id FROM app.entity WHERE system_name = :system_name)
            )
            ON CONFLICT (id) DO UPDATE
            SET current_id = 0;
        """,
        {
            "system_name": system_name,
        },
    )


async def create_relation_config(
    pool: asyncpg.pool.Pool,
    project_name: str,
    username: str,
    system_name: str,
    display_name: str,
    config: typing.Dict,
    domains: typing.List,
    ranges: typing.List,
):
    await db_base.execute(
        pool,
        """
            INSERT INTO app.relation (project_id, system_name, display_name, config, user_id)
            VALUES (
                (SELECT project.id FROM app.project WHERE system_name = :project_name),
                :system_name,
                :display_name,
                :config,
                (SELECT "user".id FROM app.user WHERE "user".username = :username)
            )
            ON CONFLICT (project_id, system_name) DO UPDATE
            SET config = EXCLUDED.config;
        """,
        {
            "project_name": project_name,
            "system_name": system_name,
            "display_name": display_name,
            "config": config,
            "username": username,
        },
    )
    # TODO: revisions
    # Remove all previously configured domains
    await db_base.execute(
        pool,
        """
            DELETE FROM app.relation_domain
            WHERE relation_id = (
                SELECT relation.id
                FROM app.relation
                WHERE project_id = (
                    SELECT project.id
                    FROM app.project
                    WHERE system_name = :project_name
                )
                AND system_name = :relation_name
            );
        """,
        {
            "project_name": project_name,
            "relation_name": system_name,
        },
    )
    for entity_type_name in domains:
        await db_base.execute(
            pool,
            """
                INSERT INTO app.relation_domain (relation_id, entity_id, user_id)
                VALUES (
                    (
                        SELECT relation.id
                        FROM app.relation
                        WHERE project_id = (
                            SELECT project.id
                            FROM app.project
                            WHERE system_name = :project_name
                        )
                        AND system_name = :relation_name
                    ),
                    (SELECT entity.id FROM app.entity WHERE system_name = :entity_type_name),
                    (SELECT "user".id FROM app.user WHERE "user".username = :username)
                )
                ON CONFLICT DO NOTHING;
            """,
            {
                "project_name": project_name,
                "relation_name": system_name,
                "entity_type_name": entity_type_name,
                "username": username,
            },
        )
    # Remove all previously configured ranges
    await db_base.execute(
        pool,
        """
            DELETE FROM app.relation_range
            WHERE relation_id = (
                SELECT relation.id
                FROM app.relation
                WHERE project_id = (
                    SELECT project.id
                    FROM app.project
                    WHERE system_name = :project_name
                )
                AND system_name = :relation_name
            );
        """,
        {
            "project_name": project_name,
            "relation_name": system_name,
        },
    )
    for entity_type_name in ranges:
        await db_base.execute(
            pool,
            """
                INSERT INTO app.relation_range (relation_id, entity_id, user_id)
                VALUES (
                    (
                        SELECT relation.id
                        FROM app.relation
                        WHERE project_id = (
                            SELECT project.id
                            FROM app.project
                            WHERE system_name = :project_name
                        )
                        AND system_name = :relation_name
                    ),
                    (SELECT entity.id FROM app.entity WHERE system_name = :entity_type_name),
                    (SELECT "user".id FROM app.user WHERE "user".username = :username)
                )
                ON CONFLICT DO NOTHING;
            """,
            {
                "project_name": project_name,
                "relation_name": system_name,
                "entity_type_name": entity_type_name,
                "username": username,
            },
        )
    await db_base.execute(
        pool,
        """
            INSERT INTO app.relation_revision (relation_id, project_id, system_name, display_name, config, user_id)
            SELECT id, project_id, system_name, display_name, config, user_id
            FROM app.relation
            WHERE project_id = (
                SELECT project.id
                FROM app.project
                WHERE system_name = :project_name
            )
            AND system_name = :relation_name
        """,
        {
            "project_name": project_name,
            "relation_name": system_name,
        },
    )
    await db_base.execute(
        pool,
        """
            INSERT INTO app.relation_count (id)
            VALUES (
                (
                    SELECT relation.id
                    FROM app.relation
                        WHERE project_id = (
                        SELECT project.id
                        FROM app.project
                        WHERE system_name = :project_name
                    )
                    AND system_name = :relation_name
                )
            )
            ON CONFLICT (id) DO UPDATE
            SET current_id = 0;
        """,
        {
            "project_name": project_name,
            "relation_name": system_name,
        },
    )


async def drop_project_graph(pool: asyncpg.pool.Pool, project_name: str):
    project_id = await get_project_id(pool, project_name)
    try:
        await db_base.execute(
            pool,
            """
                SELECT drop_graph(
                    (SELECT project.id FROM app.project WHERE project.system_name = :project_name)::text,
                    true
                );
            """,
            {
                "project_name": project_name,
            },
            True,
        )
        await db_base.execute(
            pool,
            f"""
                DROP TABLE revision."{project_id}_entities"
            """,
            {
                "project_name": project_name,
            },
        )
        await db_base.execute(
            pool,
            f"""
                DROP TABLE revision."{project_id}_relations"
            """,
            {
                "project_name": project_name,
            },
        )
    except asyncpg.exceptions.InvalidSchemaNameError:
        pass
    except asyncpg.exceptions.UndefinedTableError:
        pass


async def create_project_graph(pool: asyncpg.pool.Pool, project_name: str):
    project_id = await get_project_id(pool, project_name)
    await db_base.execute(
        pool,
        """
            SELECT create_graph(:project_id);
        """,
        {
            "project_id": project_id,
        },
        True,
    )

    # Make sure vlabels and elabels exist
    # Entity types
    records = await db_base.fetch(
        pool,
        """
            SELECT id
            FROM app.entity
            WHERE project_id = :project_id
        """,
        {
            "project_id": project_id,
        },
        True,
    )
    for record in records:
        await db_base.execute(
            pool,
            """
                SELECT create_vlabel(:project_id, :label);
            """,
            {
                "project_id": project_id,
                "label": f'n_{db_base.dtu(str(record["id"]))}',
            },
            True,
        )
    # Relation types
    records = await db_base.fetch(
        pool,
        """
            SELECT id
            FROM app.relation
            WHERE project_id = :project_id
        """,
        {
            "project_id": project_id,
        },
        True,
    )
    for record in records:
        await db_base.execute(
            pool,
            """
                SELECT create_elabel(:project_id, :label);
            """,
            {
                "project_id": project_id,
                "label": f'e_{db_base.dtu(str(record["id"]))}',
            },
            True,
        )
        # Relation nodes used to add sources
        await db_base.execute(
            pool,
            """
                SELECT create_vlabel(:project_id, :label);
            """,
            {
                "project_id": project_id,
                "label": f'en_{db_base.dtu(str(record["id"]))}',
            },
            True,
        )
    # Sources
    await db_base.execute(
        pool,
        """
            SELECT create_elabel(:project_id, :label);
        """,
        {
            "project_id": project_id,
            "label": "_source_",
        },
        True,
    )

    # Revisions
    await db_base.execute(
        pool,
        """
            INSERT INTO revision.count
            (project_id)
            VALUES (:project_id)
            ON CONFLICT (project_id)
                DO UPDATE SET current_id = 0;
        """,
        {
            "project_id": project_id,
        },
        True,
    )
    await db_base.execute(
        pool,
        f"""
            CREATE TABLE IF NOT EXISTS revision."{project_id}_entities" (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                revision_id INTEGER NOT NULL,
                user_id UUID NOT NULL
                    REFERENCES app.user (id)
                    ON UPDATE RESTRICT ON DELETE RESTRICT,
                entity_type_revision_id UUID NOT NULL
                    REFERENCES app.entity_revision (id)
                    ON UPDATE RESTRICT ON DELETE RESTRICT,
                entity_type_id UUID NOT NULL
                    REFERENCES app.entity (id)
                    ON UPDATE RESTRICT ON DELETE SET NULL,
                entity_id INT NOT NULL,
                old_value JSON,
                new_value JSON,
                created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
            );
        """,
    )
    await db_base.execute(
        pool,
        f"""
            CREATE INDEX IF NOT EXISTS "revision_{project_id}_entities__entity_id" ON revision."{project_id}_entities" (entity_id);
        """,
    )
    await db_base.execute(
        pool,
        f"""
            CREATE TABLE IF NOT EXISTS revision."{project_id}_relations" (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                revision_id INTEGER NOT NULL,
                user_id UUID NOT NULL
                    REFERENCES app.user (id)
                    ON UPDATE RESTRICT ON DELETE RESTRICT,
                relation_type_revision_id UUID NOT NULL
                    REFERENCES app.relation_revision (id)
                    ON UPDATE RESTRICT ON DELETE RESTRICT,
                relation_type_id UUID NOT NULL
                    REFERENCES app.relation (id)
                    ON UPDATE RESTRICT ON DELETE SET NULL,
                relation_id INT NOT NULL,
                start_entity_type_revision_id UUID NOT NULL
                    REFERENCES app.entity_revision (id)
                    ON UPDATE RESTRICT ON DELETE RESTRICT,
                start_entity_type_id UUID NOT NULL
                    REFERENCES app.entity (id)
                    ON UPDATE RESTRICT ON DELETE SET NULL,
                start_entity_id INT NOT NULL,
                end_entity_type_revision_id UUID NOT NULL
                    REFERENCES app.entity_revision (id)
                    ON UPDATE RESTRICT ON DELETE RESTRICT,
                end_entity_type_id UUID NOT NULL
                    REFERENCES app.entity (id)
                    ON UPDATE RESTRICT ON DELETE SET NULL,
                end_entity_id INT NOT NULL,
                old_value JSON,
                new_value JSON,
                created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
            );
        """,
    )
    await db_base.execute(
        pool,
        f"""
            CREATE INDEX IF NOT EXISTS "revision_{project_id}_relations__relation_id" ON revision."{project_id}_relations" (relation_id);
            CREATE INDEX IF NOT EXISTS "revision_{project_id}_relations__start_entity_id" ON revision."{project_id}_relations" (start_entity_id);
            CREATE INDEX IF NOT EXISTS "revision_{project_id}_relations__end_entity_id" ON revision."{project_id}_relations" (end_entity_id);
        """,
    )
