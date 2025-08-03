"""
Script to import math-related problems from the MMLU dataset into the Problem table.
Downloads and processes the dataset using the Hugging Face datasets library.
"""

import asyncio
import os
import sys
from typing import Dict, List, Optional
from datasets import load_dataset
from pathlib import Path
from sqlalchemy import func, select
from tqdm import tqdm

# Add the parent directory to the Python path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import async_session, Problem

# Math-related categories from MMLU
MATH_CATEGORIES = [
    'abstract_algebra',
    'college_mathematics',
    'elementary_mathematics',
    'high_school_mathematics',
    'high_school_statistics',
    'college_physics',  # Including physics as it's heavily math-based
    'high_school_physics',
    'conceptual_physics'
]

def format_statement_answer(choices: List[str], answer_idx: int) -> str:
    """Format the answer for statement-type questions."""
    choice = choices[answer_idx]
    parts = choice.split(', ')
    if len(parts) != 2:
        return choice
    
    statement1 = "true" if parts[0].lower() == "true" else "false"
    statement2 = "true" if parts[1].lower() == "true" else "false"
    
    return f"Statement 1 is {statement1}. Statement 2 is {statement2}."

def process_question(item: Dict) -> Optional[Dict]:
    """Process a single question from the dataset."""
    question = item['question']
    
    # Format the answer based on question type
    if "Statement 1" in question:
        answer = format_statement_answer(item['choices'], item['answer'])
        # Add clarification for statement questions
        question += "\n\nAssess whether each statement is true or false."
    else:
        # For multiple choice, use the answer directly
        answer = item['choices'][item['answer']]
    
    return {
        "question": question,
        "answer": answer,
        "category": item['subject'],
        "choices": item['choices'],
        "dataset": "mmlu",
        "split": None,  # Will be set in the main loop
        "answer_index": item['answer']  # Store original answer index
    }

async def check_mmlu_exists():
    """Check if any MMLU problems already exist in the database."""
    async with async_session() as session:
        result = await session.execute(
            select(Problem).where(Problem.dataset_name == 'MMLU').limit(1)
        )
        return result.scalar() is not None

async def import_mmlu_dataset() -> None:
    """Import math-related problems from MMLU dataset into the database."""
    # Check if MMLU problems already exist
    if await check_mmlu_exists():
        print("MMLU problems already exist in the database. Exiting.")
        return

    async with async_session() as session:
        # Get the current max ID to avoid conflicts
        result = await session.execute(
            select(Problem.id).order_by(Problem.id.desc()).limit(1)
        )
        max_id = result.scalar() or 0
        problem_id = max_id + 1
        
        total_problems = 0
        
        for category in MATH_CATEGORIES:
            print(f"Processing category: {category}")
            try:
                ds = load_dataset("cais/mmlu", category)
                
                # Process each split
                for split in ['dev', 'validation', 'test']:
                    if split not in ds:
                        continue
                    
                    print(f"Processing {split} split...")
                    for item in tqdm(sorted(ds[split])):
                        processed = process_question(item)
                        if processed:
                            # Create problem record
                            problem = Problem(
                                id=problem_id,
                                dataset_name='MMLU',
                                category=processed['category'],
                                question=processed['question'],
                                answer=processed['answer'],
                                problem_metadata={
                                    'split': split,
                                    'choices': processed['choices'],
                                    'original_answer': processed['answer_index']
                                }
                            )
                            session.add(problem)
                            problem_id += 1
                            total_problems += 1
                            
                            # Commit every 100 problems
                            if total_problems % 100 == 0:
                                await session.commit()
            
            except Exception as e:
                print(f"Error processing category {category}: {str(e)}")
                continue
        
        # Final commit for any remaining problems
        await session.commit()
        
        # Print statistics
        print(f"\nSuccessfully imported {total_problems} problems")
        
        # Print category distribution
        result = await session.execute(
            select(Problem.category, Problem.problem_metadata['split'].label('split'))
            .where(Problem.dataset_name == 'MMLU')
            .order_by(func.random())
        )
        
        stats = {}
        for row in result:
            category = row.category
            split = row.split
            if category not in stats:
                stats[category] = {'total': 0}
            if split not in stats[category]:
                stats[category][split] = 0
            stats[category][split] = stats[category].get(split, 0) + 1
            stats[category]['total'] = stats[category].get('total', 0) + 1

        print("\nCategory distribution:")
        for category, counts in stats.items():
            print(f"\n{category}:")
            print(f"  Total: {counts['total']}")
            for split, count in counts.items():
                if split != 'total':
                    print(f"  {split}: {count}")

async def main():
    """Main function to orchestrate the import process."""
    try:
        await import_mmlu_dataset()
    except Exception as e:
        print(f"Error importing MMLU dataset: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 