"""
Script to import the MATH dataset into the Problem table.
Downloads and processes the dataset from Berkeley's website.
The MATH dataset is available at: https://github.com/hendrycks/math
"""

import asyncio
import os
import sys
import json
import tarfile
import tempfile
import requests
from pathlib import Path
from sqlalchemy import select
from tqdm import tqdm

# Add the parent directory to the Python path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import async_session, Problem

MATH_URL = "https://people.eecs.berkeley.edu/~hendrycks/MATH.tar"

async def check_math_exists():
    """Check if any MATH problems already exist in the database."""
    async with async_session() as session:
        result = await session.execute(
            select(Problem).where(Problem.dataset_name == 'MATH').limit(1)
        )
        return result.scalar() is not None

def download_and_extract():
    """Download and extract the MATH dataset."""
    print("Downloading MATH dataset...")
    with tempfile.NamedTemporaryFile() as tmp_file:
        # Download with progress bar
        response = requests.get(MATH_URL, stream=True)
        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192
        
        with tqdm(total=total_size, unit='iB', unit_scale=True) as pbar:
            for data in response.iter_content(block_size):
                tmp_file.write(data)
                pbar.update(len(data))
        
        tmp_file.flush()
        
        print("Extracting archive...")
        with tarfile.open(tmp_file.name) as tar:
            tar.extractall()
    
    return Path("MATH")

async def import_problems(math_dir: Path):
    """Import problems from the extracted MATH directory."""
    async with async_session() as session:
        # Get the current max ID to avoid conflicts
        result = await session.execute(
            select(Problem.id).order_by(Problem.id.desc()).limit(1)
        )
        max_id = result.scalar() or 0
        problem_id = max_id + 1
        
        # Process train and test directories
        for split in ['train', 'test']:
            split_dir = math_dir / split
            for category_dir in split_dir.iterdir():
                if not category_dir.is_dir():
                    continue
                
                category = category_dir.name
                print(f"Processing {split}/{category}...")
                
                # Process each problem JSON file
                for problem_file in tqdm(list(category_dir.glob('*.json'))):
                    with open(problem_file) as f:
                        data = json.load(f)
                
                    # Get relative path from MATH root directory
                    rel_path = str(problem_file.relative_to(math_dir))
                    
                    # Create problem record
                    problem = Problem(
                        id=problem_id,
                        dataset_name='MATH',
                        category=category,
                        question=data['problem'],
                        answer=data['solution'],
                        problem_metadata={
                            'split': split,
                            'level': data['level'],
                            'file_path': rel_path  # Add relative file path to metadata
                        },
                    )
                    session.add(problem)
                    problem_id += 1
                    
                    # Commit every 100 problems
                    if problem_id % 100 == 0:
                        await session.commit()
        
        # Final commit for any remaining problems
        await session.commit()
        print(f"Successfully imported {problem_id - max_id - 1} problems")

async def main():
    """Main function to orchestrate the import process."""
    # Check if MATH problems already exist
    if await check_math_exists():
        print("MATH problems already exist in the database. Exiting.")
        return
    
    try:
        # Download and extract the dataset
        math_dir = download_and_extract()
        
        # Import all problems
        await import_problems(math_dir)
        
        # Clean up
        if math_dir.exists():
            import shutil
            shutil.rmtree(math_dir)
            
    except Exception as e:
        print(f"Error importing MATH dataset: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 