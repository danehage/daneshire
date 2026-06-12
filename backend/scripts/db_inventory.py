"""Read-only inventory of row counts per table. Safe to run against any DB."""
import asyncio
import os

import asyncpg
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


async def main():
    url = os.environ["NEON_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    host = url.split("@")[1].split("/")[0]
    print(f"host: {host}\n")
    conn = await asyncpg.connect(url, timeout=20)
    try:
        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        )
        for t in tables:
            name = t["tablename"]
            count = await conn.fetchval(f'SELECT count(*) FROM "{name}"')
            newest = None
            has_created = await conn.fetchval(
                "SELECT 1 FROM information_schema.columns WHERE table_name = $1 AND column_name = 'created_at'",
                name,
            )
            if has_created and count:
                newest = await conn.fetchval(f'SELECT max(created_at) FROM "{name}"')
            print(f"{name:30} {count:>6}   newest: {newest}")
    finally:
        await conn.close()


asyncio.run(main())
