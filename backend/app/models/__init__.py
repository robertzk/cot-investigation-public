from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Import all models here to avoid circular imports
from .base import Base
from .problem import Problem
from .completion import Completion
from .cot_trie import CotTrie
from .cot_path import CotPath
from .experiment import CotTrieEvalExperiment, CotTrieEvalExperimentRecord
from .language_model import LanguageModel

# Create async engine and session
engine = create_async_engine(
    DATABASE_URL,
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

