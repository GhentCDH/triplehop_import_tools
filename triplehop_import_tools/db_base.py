import asyncpg
import buildpg
import typing

RENDERER = buildpg.main.Renderer(regex=r'(?<![a-z\\:]):([a-z][a-z0-9_]*)', sep='__')

def dtu(string: str) -> str:
    '''Replace all dashes in a string with underscores.'''
    return string.replace('-', '_')

def _render(query_template: str, params: typing.Dict[str, typing.Any] = None):
    if params is None:
        query, args = RENDERER(query_template)
    else:
        query, args = RENDERER(query_template, **params)
    query = query.replace('\\:', ':')
    return [query, args]


async def _init_age(conn: asyncpg.connection.Connection):
    await conn.execute(
        '''
            SET search_path = ag_catalog, "$user", public;
        '''
    )
    await conn.execute(
        '''
            LOAD '$libdir/plugins/age';
        '''
    )


async def execute(
    pool: asyncpg.pool.Pool,
    query_template,
    params: typing.Dict[str, typing.Any] = None,
    age: bool = False,
):
    async with pool.acquire() as conn:
        query, args = _render(query_template, params)
        if age:
            async with conn.transaction():
                await _init_age(conn)
                return await conn.execute(query, *args)
        return await conn.execute(query, *args)


async def executemany(
    pool: asyncpg.pool.Pool,
    query_template,
    params: typing.Dict[str, typing.Any] = None,
    age: bool = False,
):
    async with pool.acquire() as conn:
        query, _ = _render(query_template, params[0])
        args = [_render(query_template, p)[1] for p in params]
        if age:
            async with conn.transaction():
                await _init_age(conn)
                return await conn.executemany(query, args)
        return await conn.executemany(query, args)


async def fetch(
    pool: asyncpg.pool.Pool,
    query_template,
    params: typing.Dict[str, typing.Any] = None,
    age: bool = False,
):
    async with pool.acquire() as conn:
        query, args = _render(query_template, params)
        if age:
            async with conn.transaction():
                await _init_age(conn)
                return await conn.fetch(query, *args)
        return await conn.fetch(query, *args)


async def fetchval(
    pool: asyncpg.pool.Pool,
    query_template,
    params: typing.Dict[str, typing.Any] = None,
    age: bool = False,
):
    async with pool.acquire() as conn:
        query, args = _render(query_template, params)
        if age:
            async with conn.transaction():
                await _init_age(conn)
                return await conn.fetchval(query, *args)
        return await conn.fetchval(query, *args)