import asyncio
import os
import sys
from app.models.problem import Problem
from datasets import load_dataset
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

# Add the parent directory to the Python path so we can import our models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def main():
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Create async engine
    engine = create_async_engine(database_url)
    async_session = sessionmaker(
        engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )

    # Load GSM8K dataset
    print("Loading GSM8K dataset from HuggingFace...")
    dataset = load_dataset("gsm8k", "main")
    
    # Process both train and test splits
    splits = ['train', 'test']
    
    async with async_session() as session:
        for split in splits:
            print(f"\nProcessing {split} split...")
            data = dataset[split]
            
            # Use tqdm for a progress bar
            for item in tqdm(data, desc=f"Inserting {split} data"):
                # Create GSM8K entry
                gsm8k_entry = Problem(
                    dataset_name="gsm8k",
                    question=item['question'],
                    answer=item['answer']
                )
                session.add(gsm8k_entry)
            
            # Commit after each split
            print(f"Committing {split} split to database...")
            await session.commit()

    print("\nDone! GSM8K dataset has been loaded into the database.")

if __name__ == "__main__":
    asyncio.run(main()) 