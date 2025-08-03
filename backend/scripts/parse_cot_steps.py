import asyncio
import os
import sys
import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tqdm import tqdm

# Add the parent directory to the Python path so we can import our models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import async_session, GSM8KCoT, GSM8KCoTStep

async def get_cot_entries(session: AsyncSession) -> list[GSM8KCoT]:
    """Get all CoT entries that haven't been parsed into steps yet."""
    result = await session.execute(
        select(GSM8KCoT)
        .outerjoin(GSM8KCoTStep)
        .filter(GSM8KCoTStep.id == None)
    )
    return result.scalars().all()

def parse_steps(raw_response: str) -> list[str]:
    """
    Parse a raw response into individual steps.
    Looks for patterns like "\n1. ", "\n2. ", etc.
    """
    # First try to find numbered steps with period
    steps = re.split(r'\n\d+\.\s+', raw_response)
    
    # If that didn't work (no steps found), try without period
    if len(steps) <= 1:
        steps = re.split(r'\n\d+\s+', raw_response)
    
    # Remove empty steps and the text before the first step
    steps = [s.strip() for s in steps if s.strip()]
    
    # If we found steps, remove any trailing "Therefore..." or "Thus..." text from the last step
    if steps:
        last_step = steps[-1]
        conclusion_markers = ["Therefore,", "Thus,", "So,", "Hence,", "In conclusion,"]
        for marker in conclusion_markers:
            if marker.lower() in last_step.lower():
                conclusion_part = last_step.lower().find(marker.lower())
                steps[-1] = last_step[:conclusion_part].strip()
                # Add the conclusion as a separate step if it's substantial
                conclusion = last_step[conclusion_part:].strip()
                if len(conclusion) > 20:  # Only add if it's a substantial conclusion
                    steps.append(conclusion)
                break
    
    return steps

async def process_cot_entries(session: AsyncSession, entries: list[GSM8KCoT]) -> tuple[int, int]:
    """Process CoT entries and create step entries."""
    successful = 0
    failed = 0
    
    for cot in tqdm(entries, desc="Processing CoT entries"):
        try:
            # Parse steps from the raw response
            steps = parse_steps(cot.raw_response)
            
            if not steps:
                print(f"No steps found in CoT entry {cot.id}")
                failed += 1
                continue
            
            # Create step entries
            for i, step_text in enumerate(steps, 1):
                step = GSM8KCoTStep(
                    gsm8k_cot_id=cot.id,
                    step_number=i,
                    step_text=step_text
                )
                session.add(step)
            
            await session.commit()
            successful += 1
            
        except Exception as e:
            print(f"Error processing CoT entry {cot.id}: {str(e)}")
            await session.rollback()
            failed += 1
    
    return successful, failed

async def main():
    async with async_session() as session:
        # Get all CoT entries that haven't been parsed yet
        entries = await get_cot_entries(session)
        if not entries:
            print("No unparsed CoT entries found")
            return
        
        print(f"Found {len(entries)} CoT entries to process")
        
        # Process entries and create steps
        successful, failed = await process_cot_entries(session, entries)
        
        print(f"\nProcessing complete:")
        print(f"Successfully processed: {successful}")
        print(f"Failed to process: {failed}")

if __name__ == "__main__":
    asyncio.run(main()) 