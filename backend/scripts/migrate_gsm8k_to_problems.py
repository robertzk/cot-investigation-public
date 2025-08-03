"""
Script to migrate GSM8K data to the new Problem table.
This script should be run after applying the database migration that creates the problems table.
"""

import asyncio
import os
import sys
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Add the parent directory to the Python path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import async_session
from app.models.gsm8k import GSM8K
from app.models.problem import Problem

async def migrate_gsm8k_data():
    """Migrate GSM8K data to the new Problem table."""
    async with async_session() as session:
        # Get all GSM8K records
        result = await session.execute(select(GSM8K))
        gsm8k_records = result.scalars().all()
        
        print(f"Found {len(gsm8k_records)} GSM8K records to migrate")
        
        # Create Problem records
        for gsm8k in gsm8k_records:
            problem = Problem(
                id=gsm8k.id,  # Keep the same ID for reference
                dataset_name='gsm8k',
                question=gsm8k.question,
                answer=gsm8k.answer
            )
            session.add(problem)
        
        # Commit the changes
        await session.commit()
        print("Migration completed successfully")

if __name__ == "__main__":
    asyncio.run(migrate_gsm8k_data()) 