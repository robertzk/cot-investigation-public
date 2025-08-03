# %%
import sys
sys.path.append('/Users/robertk/dev/cot-investigation/backend')
# %%

import os
os.environ['DATABASE_URL'] = 'postgresql+asyncpg://chainofthought:chainofthought@localhost:5434/chainofthought'

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import joinedload, sessionmaker
from app.models import CotTrie, engine

engine = create_async_engine(
    os.getenv('DATABASE_URL'),
    echo=True,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=30,
    pool_timeout=60,
    pool_recycle=3600,
)

async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def load_trie():
    async with async_session() as session:
        query = (
            select(CotTrie)
            .where(CotTrie.problem_id == 332)
            .where(CotTrie.model == 'ollama/gemma2:9b')
        ).options(joinedload(CotTrie.cot_paths))
        result = await session.execute(query)
        result = result.unique().all()
        return result[0][0]

# %%

async def load_stuff():
    async with async_session() as session:
        query = (
            select(CotTrie, GSM8K)
            .join(GSM8K, CotTrie.problem_id == GSM8K.id)
            .where(
                CotTrie.trie_evaled.is_not(None)
            )
            #.where(CotTrie.problem_id < 1500)
            .where(CotTrie.model == "ollama/gemma2:9b")
            #.limit(limit)
        )
        query = query.options(joinedload(CotTrie.cot_paths))  # Eager load paths

        result = await session.execute(query)
        tries = result.unique().all()
        return tries

# %%
import asyncio
loop = asyncio.get_running_loop()
trie = await loop.create_task(load_trie())


# %%
async def get_cot_paths(trie_id):
    async with async_session() as session:
        query = (
            select(CotTrie)
            .where(CotTrie.id == trie_id)
            .options(joinedload(CotTrie.cot_paths))
        )
        result = await session.execute(query)
        trie = result.scalar_one_or_none()
        return trie.cot_paths if trie else []

paths = await loop.create_task(get_cot_paths(trie.id))
paths
# %%

from app.models import CotPath

async def load_paths(trie_id):
    async with async_session() as session:
        query = (
            select(CotPath)
            .where(CotPath.cot_trie_id == trie_id)
        )
        result = await session.execute(query)
        paths = result.scalars().all()
        return paths

paths = await loop.create_task(load_paths(trie.id))

# %%

from datasets import load_dataset
ds = load_dataset("cais/mmlu", "abstract_algebra")