import asyncio
import os
import sys
import argparse
from typing import Optional, List
from sqlalchemy import func, select
import json
from tqdm import tqdm
import numpy as np

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import async_session, Problem, CotTrie
from app.services.anthropic_service import AnthropicService
from app.services.local_model_service import LocalModelService
from app.services.model_service import ModelService
from app.services.step_evaluation_service import BasicStepEvaluationService
from app.data_structures.cot_trie import CotTrie as CotTrieStructure
from app.data_structures.cot_trie_builder import CotTrieBuilder
from app.types.chat_message import ChatMessage
from app.services.ollama_service import OllamaModelService

EVALUATOR_MODEL = "claude-3-5-sonnet-20241022"
LIMIT = 10000
MAX_CONCURRENT = 20

async def get_model_service(model_name: str) -> ModelService:
    """Get the appropriate model service based on model name."""
    if model_name.startswith("ollama/"):
        # Strip the "ollama/" prefix to get the actual model name
        ollama_model = model_name[len("ollama/"):]
        return await OllamaModelService.create(model_name=ollama_model)
    elif 'claude' in model_name.lower():
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        return AnthropicService(api_key=api_key, model=model_name)
    else:
        return LocalModelService(model_name=model_name)

async def get_problems(session, dataset_name: str, model_name: str, limit: Optional[int] = None, problem_ids: Optional[List[int]] = None) -> List[Problem]:
    """Get problems that don't have tries yet for the specified dataset."""
    query = (
        select(Problem)
        .outerjoin(CotTrie, (CotTrie.problem_id == Problem.id) & (CotTrie.model == model_name))
        .where(CotTrie.id == None)  # Only get problems without tries
    )

    if dataset_name:
        query = query.where(Problem.dataset_name == dataset_name)
    
    if problem_ids:
        query = query.where(Problem.id.in_(problem_ids))
    else:
        query = query.order_by(func.random())

    if limit:
        query = query.limit(limit)
    
    result = await session.execute(query)
    return result.scalars().all()

async def process_problem(
    problem: Problem,
    model_service: ModelService,
    evaluation_service: BasicStepEvaluationService,
    semaphore: asyncio.Semaphore
) -> Optional[tuple[dict, int]]:
    """Process a single problem and return its trie structure."""
    async with semaphore:
        try:
            # Create the prompt
            cot_instruction = """Write down your answer step by step, and number each step ("1.", "2.", etc.)."""
            prompt = f"""{problem.question}\n\n{cot_instruction}"""
            model_service.set_cot_instruction(cot_instruction)
            messages = [ChatMessage(role="user", content=prompt)]

            if isinstance(model_service, OllamaModelService):
                additional_kwargs = {"step_rollout_kwarg_sampler": lambda: {
                    "seed": np.random.randint(0, 1000000),
                    "temperature": np.round(np.random.uniform(0.6, 0.8), 2).item()
                    }}
            elif isinstance(model_service, LocalModelService):
                additional_kwargs = {
                    "step_rollout_kwarg_sampler": lambda: {
                        "seed": np.random.randint(0, 1000000),
                        "temperature": 0.0,
                        "cot_instruction_seed": np.random.randint(0, 1000000),
                    }
                }
            else:
                additional_kwargs = {}

            # Create and build the trie
            cot_trie = CotTrieBuilder(
                model_service=model_service,
                evaluation_service=evaluation_service,
                messages=messages,
                answer=problem.answer,
                branching_factor=3,
                **additional_kwargs
            )
            
            await cot_trie.build()
            
            cot_trie_obj = CotTrieStructure.from_root_node(cot_trie.root)
            trie_dict = cot_trie_obj.serialize()
            return trie_dict, problem.id
            
        except Exception as e:
            print(f"Error processing problem {problem.id}: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

async def main(dataset_name: str, model_name: str, limit: Optional[int] = None, problem_ids: Optional[List[int]] = None):
    # Initialize services
    model_service = await get_model_service(model_name)
    max_problems_at_a_time = 10
    
    # Always use Claude for evaluation
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    
    evaluator_service = BasicStepEvaluationService(
        AnthropicService(api_key=api_key, model=EVALUATOR_MODEL)
    )
    
    # Create semaphore for concurrency control
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    
    async with async_session() as session:
        # Get problems without tries
        problems = await get_problems(session, dataset_name, model_name, limit, problem_ids)
        print(f"Found {len(problems)} problems without tries for dataset {dataset_name}")
        
        # Process problems concurrently with progress bar
        await process_problem(problems[0], model_service, evaluator_service, semaphore)

        with tqdm(total=len(problems), desc="Processing problems") as pbar:
            # Process problems in groups of max_problems_at_a_time
            for i in range(0, len(problems), max_problems_at_a_time):
                group = problems[i:i+max_problems_at_a_time]
                tasks = [
                    process_problem(problem, model_service, evaluator_service, semaphore)
                    for problem in group
                ]
            
                for task in asyncio.as_completed(tasks):
                    try:
                        result = await task
                        if result:
                            trie_dict, problem_id = result
                            # Store the trie in the database
                            cot_trie = CotTrie(
                                dataset=dataset_name,
                                problem_id=problem_id,
                                model=model_name,
                                trie=trie_dict
                            )
                            session.add(cot_trie)
                            await session.commit()

                            print(f"Saved trie for problem {problem_id}")
                    except Exception as e:
                        print(f"Error saving trie: {str(e)}")
                        await session.rollback()
                    finally:
                        pbar.update(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Collect chain-of-thought tries for problems')
    parser.add_argument('--dataset', type=str, required=False,
                       help='Dataset to process (e.g., "gsm8k", "MATH")')
    parser.add_argument('--model', type=str, default="claude-3-haiku-20240307",
                       help='Model to use (e.g., claude-3-haiku-20240307, google/gemma-2b, or ollama/gemma2:2b)')
    parser.add_argument('--limit', type=int, help='Limit the number of problems to process', default=LIMIT)
    parser.add_argument('--problem-ids', type=str, help='Comma-separated list of problem IDs to process', default=None)
    
    args = parser.parse_args()
    
    # Parse problem_ids if provided
    problem_ids = None
    if args.problem_ids:
        problem_ids = [int(pid.strip()) for pid in args.problem_ids.split(',')]
    
    asyncio.run(main(
        dataset_name=args.dataset,
        model_name=args.model,
        limit=args.limit,
        problem_ids=problem_ids
    )) 