import asyncio
import os
import sys
import argparse
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tqdm import tqdm

# Add the parent directory to the Python path so we can import our models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import async_session, GSM8K, LanguageModel, GSM8KCoT
from app.services.anthropic_service import AnthropicService

# Limit concurrent tasks
MAX_CONCURRENT_TASKS = 10

async def get_language_models(session: AsyncSession) -> list[tuple[int, str]]:
    """Get all language models from the database."""
    result = await session.execute(select(LanguageModel.id, LanguageModel.model_name))
    return result.all()

async def get_gsm8k_records(session: AsyncSession, limit: Optional[int] = None) -> list[GSM8K]:
    """Get GSM8K records up to the specified limit."""
    query = select(GSM8K)
    if limit:
        query = query.limit(limit)
    result = await session.execute(query)
    return result.scalars().all()

async def process_batch(
    anthropic: AnthropicService,
    tasks: List[tuple[GSM8K, int, str]],
    semaphore: asyncio.Semaphore
) -> List[Exception]:
    """Process a batch of questions with connection pooling."""
    async def process_single(gsm8k: GSM8K, model_id: int, model_name: str) -> None:
        async with semaphore:
            async with async_session() as session:
                async with session.begin():
                    # Check if we already have this combination
                    existing = await session.execute(
                        select(GSM8KCoT)
                        .where(GSM8KCoT.gsm8k_id == gsm8k.id)
                        .where(GSM8KCoT.language_model_id == model_id)
                    )
                    if existing.first():
                        print(f"Skipping existing response for question {gsm8k.id} with model {model_name}")
                        return

                    try:
                        # Construct the prompt
                        prompt = f"""{gsm8k.question}\n\nWrite down your answer step by step, and number each step ("1.", "2.", etc.)."""
                        
                        # Get model response
                        response = await anthropic.get_completion(
                            prompt=prompt,
                            model=model_name,
                            temperature=0.0
                        )
                        
                        # Save to database
                        cot_entry = GSM8KCoT(
                            gsm8k_id=gsm8k.id,
                            language_model_id=model_id,
                            params={"temperature": 0.0},
                            raw_response=response.content[0].text
                        )
                        session.add(cot_entry)
                        
                        print(f"Saved response for question {gsm8k.id} with model {model_name}")
                        
                    except Exception as e:
                        print(f"Error processing question {gsm8k.id} with model {model_name}: {str(e)}")
                        raise

    # Process tasks with bounded concurrency
    errors = []
    tasks_iter = tqdm(tasks, desc="Processing questions")
    
    # Create and gather all tasks
    async_tasks = [
        process_single(gsm8k, model_id, model_name) 
        for gsm8k, model_id, model_name in tasks_iter
    ]
    
    # Run tasks concurrently and collect results
    results = await asyncio.gather(*async_tasks, return_exceptions=True)
    
    # Collect any errors
    errors = [r for r in results if isinstance(r, Exception)]
    return errors

async def main(limit: Optional[int] = None):
    # Initialize Anthropic client
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    
    anthropic = AnthropicService(api_key=api_key)
    
    async with async_session() as session:
        # Get all language models
        models = await get_language_models(session)
        if not models:
            raise ValueError("No language models found in database")
        
        # Get GSM8K records
        gsm8k_records = await get_gsm8k_records(session, limit=limit)
        if not gsm8k_records:
            raise ValueError("No GSM8K records found in database")
        
        print(f"Processing {len(gsm8k_records)} GSM8K records with {len(models)} models...")
        
        # Create task list
        tasks = [
            (gsm8k, model_id, model_name)
            for gsm8k in gsm8k_records
            for model_id, model_name in models
        ]

        # Create semaphore for connection pooling
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
        
        # Process all tasks
        failed_tasks = await process_batch(anthropic, tasks, semaphore)
        
        if failed_tasks:
            print(f"\nFailed tasks: {len(failed_tasks)}")
            for e in failed_tasks:
                print(f"- {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Collect chain-of-thought responses for GSM8K questions')
    parser.add_argument('--limit', type=int, help='Limit the number of GSM8K questions to process')
    
    args = parser.parse_args()
    asyncio.run(main(limit=args.limit)) 