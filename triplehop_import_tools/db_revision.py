import asyncio
import asyncpg

import config
import db_base


async def create_revision_structure():
    pool = await asyncpg.create_pool(**config.DATABASE)

    await db_base.execute(
        pool,
        """
            DROP SCHEMA IF EXISTS revision CASCADE;
        """,
    )

    await db_base.execute(
        pool,
        """
            CREATE SCHEMA revision;
        """,
    )

    await db_base.execute(
        pool,
        """
            CREATE TABLE revision.count (
                project_id UUID NOT NULL
                    REFERENCES app.project (id)
                    ON UPDATE RESTRICT ON DELETE CASCADE,
                current_id INTEGER NOT NULL DEFAULT 0,
                UNIQUE (project_id)
            );
        """,
    )

    await pool.close()


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(create_revision_structure())
    loop.close()


if __name__ == "__main__":
    main()
