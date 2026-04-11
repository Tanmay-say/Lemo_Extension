"""
Shared Prisma singleton.
Import `prisma` from here instead of creating new Prisma() in each controller.
This prevents connection pool exhaustion from multiple client instances.
"""
from prisma import Prisma

prisma = Prisma()


async def get_prisma() -> Prisma:
    """Return the shared Prisma client, connecting if not already connected."""
    if not prisma.is_connected():
        await prisma.connect()
    return prisma
