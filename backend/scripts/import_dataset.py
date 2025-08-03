"""
Script to import a new dataset into the Problem table.
The script expects a CSV file with at least 'question' and 'answer' columns.
Optionally, it can include a 'category' column for datasets with subcategories.
"""

import asyncio
import os
import sys
import csv
import argparse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Add the parent directory to the Python path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import async_session, Problem

async def import_dataset(dataset_name: str, csv_path: str):
    """Import a dataset from a CSV file into the Problem table."""
    if not os.path.exists(csv_path):
        print(f"Error: File {csv_path} does not exist")
        return

    async with async_session() as session:
        # Read the CSV file
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            
            # Verify required columns exist
            required_columns = {'question', 'answer'}
            if not required_columns.issubset(reader.fieldnames):
                print(f"Error: CSV must contain columns {required_columns}")
                return
            
            # Get the current max ID to avoid conflicts
            result = await session.execute(
                select(Problem.id).order_by(Problem.id.desc()).limit(1)
            )
            max_id = result.scalar() or 0
            
            # Create Problem records
            for i, row in enumerate(reader, 1):
                problem = Problem(
                    id=max_id + i,
                    dataset_name=dataset_name,
                    question=row['question'],
                    answer=row['answer'],
                    category=row.get('category')  # Use category if present
                )
                session.add(problem)
                
                if i % 1000 == 0:
                    print(f"Processed {i} records...")
                    await session.commit()  # Commit in batches
            
            # Final commit for any remaining records
            await session.commit()
            print(f"Successfully imported {i} records from {dataset_name}")

def main():
    parser = argparse.ArgumentParser(description='Import a dataset into the Problem table')
    parser.add_argument('dataset_name', help='Name of the dataset (e.g., "math23k")')
    parser.add_argument('csv_path', help='Path to the CSV file containing the dataset')
    
    args = parser.parse_args()
    asyncio.run(import_dataset(args.dataset_name, args.csv_path))

if __name__ == "__main__":
    main() 