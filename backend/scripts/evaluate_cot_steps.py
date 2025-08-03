import asyncio
import os
import sys
import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tqdm import tqdm

# Add the parent directory to the Python path so we can import our models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import async_session, GSM8K, GSM8KCoT, GSM8KCoTStep, GSM8KCoTStepEval
from app.services.anthropic_service import AnthropicService

EVALUATOR_MODEL = "claude-3-5-sonnet-20240620"

async def get_unevaluated_steps(session: AsyncSession) -> list[tuple[GSM8KCoTStep, GSM8K, list[GSM8KCoTStep]]]:
    """Get all steps that haven't been evaluated yet, along with their context."""
    # Get steps without evaluations
    result = await session.execute(
        select(GSM8KCoTStep, GSM8K)
        .join(GSM8KCoT, GSM8KCoTStep.gsm8k_cot_id == GSM8KCoT.id)
        .join(GSM8K, GSM8KCoT.gsm8k_id == GSM8K.id)
        .outerjoin(GSM8KCoTStepEval)
        .filter(GSM8KCoTStepEval.id == None)
        .order_by(GSM8KCoTStep.gsm8k_cot_id, GSM8KCoTStep.step_number)
        .limit(100)
    )
    steps_with_context = []
    
    # Group steps by CoT ID to get previous steps
    current_cot_id = None
    current_steps = []
    
    for step, gsm8k in result:
        if current_cot_id != step.gsm8k_cot_id:
            current_cot_id = step.gsm8k_cot_id
            current_steps = []
            
        current_steps.append(step)
        steps_with_context.append((step, gsm8k, current_steps[:-1]))  # All steps up to current
    
    return steps_with_context

def create_evaluation_prompt(question: str, previous_steps: list[GSM8KCoTStep], current_step: GSM8KCoTStep) -> str:
    """Create a prompt to evaluate a step's correctness."""
    prompt = f"Question: {question}\n\n"
    
    if previous_steps:
        prompt += "Previous steps:\n"
        for prev_step in previous_steps:
            prompt += f"Step {prev_step.step_number}. {prev_step.step_text}\n"
    
    prompt += f"\nStep to evaluate:\nStep {current_step.step_number}. {current_step.step_text}\n\n"
    prompt += "Is this last step correct or not? Answer with <correct>yes</correct> or <correct>no</correct> or <correct>unknown</correct>. Use the last answer if you do not have information to assess correctness.\n\nExplain your reasoning after the tag."
    
    return prompt

def parse_evaluation(response: str) -> tuple[str, str]:
    """Parse the model's response into correctness and explanation."""
    correct_match = re.search(r'<correct>(yes|no|unknown)</correct>', response.lower())
    if not correct_match:
        return "unknown", response
    
    correctness = correct_match.group(1)
    explanation = response[correct_match.end():].strip()
    
    return correctness, explanation

async def evaluate_steps(
    anthropic: AnthropicService,
    session: AsyncSession,
    steps_with_context: list[tuple[GSM8KCoTStep, GSM8K, list[GSM8KCoTStep]]]
) -> tuple[int, int]:
    """Evaluate steps and save results."""
    successful = 0
    failed = 0
    
    for step, gsm8k, previous_steps in tqdm(steps_with_context, desc="Evaluating steps"):
        try:
            # Create and send prompt
            prompt = create_evaluation_prompt(gsm8k.question, previous_steps, step)
            response = await anthropic.get_completion(
                prompt=prompt,
                model=EVALUATOR_MODEL,
                temperature=0.0
            )
            
            # Parse response
            correctness, explanation = parse_evaluation(response.content[0].text)
            
            # Save evaluation
            eval_entry = GSM8KCoTStepEval(
                step_id=step.id,
                correct=correctness,
                model=EVALUATOR_MODEL,
                explanation=explanation
            )
            session.add(eval_entry)
            await session.commit()
            
            successful += 1
            
        except Exception as e:
            print(f"Error evaluating step {step.id}: {str(e)}")
            await session.rollback()
            failed += 1
    
    return successful, failed

async def main():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    
    anthropic = AnthropicService(api_key=api_key)
    
    async with async_session() as session:
        # Get unevaluated steps
        steps = await get_unevaluated_steps(session)
        if not steps:
            print("No unevaluated steps found")
            return
        
        print(f"Found {len(steps)} steps to evaluate")
        
        # Process evaluations
        successful, failed = await evaluate_steps(anthropic, session, steps)
        
        print(f"\nEvaluation complete:")
        print(f"Successfully evaluated: {successful}")
        print(f"Failed to evaluate: {failed}")

if __name__ == "__main__":
    asyncio.run(main()) 