import asyncio
import os
import sys
import json
import argparse
from typing import List, Dict, Any, Optional
from sqlalchemy import select, text, func
from tqdm import tqdm

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import async_session, CotTrie as CotTrieModel, CotPath as CotPathModel, Problem
from app.services.anthropic_service import AnthropicService
from app.services.secondary_evaluation_service import SecondaryEvaluationService
from app.types.cot_trie import CotTrieNode

async def fetch_unevaluated_tries(
    override_ids: Optional[List[int]] = None, 
    model: Optional[str] = None,
    dataset: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Fetch tries that have explanations but haven't been secondarily evaluated."""
    async with async_session() as session:
        # Use raw SQL to find tries with explanations and incorrect steps
        query = select(CotTrieModel, Problem).join(
            Problem,
            CotTrieModel.problem_id == Problem.id
        )
        
        if model is not None:
            query = query.where(CotTrieModel.model == model)
            
        if dataset is not None:
            query = query.where(CotTrieModel.dataset == dataset)
        
        if override_ids:
            query = query.where(Problem.id.in_(override_ids))
        else:
            query = query.where(
                text("trie::text LIKE :pattern AND trie_evaled IS NULL")
            ).params(
                pattern='%"explanation":%'
            )

        result = await session.execute(query)
        tries = result.unique().all()
        
        return [{
            'id': trie.id,
            'dataset': trie.dataset,
            'problem_id': trie.problem_id,
            'model': trie.model,
            'question': problem.question,
            'answer': problem.answer,
            'trie': trie.trie
        } for trie, problem in tries]

def add_secondary_evals_to_trie(
    trie_dict: Dict[str, Any], 
    node_evaluations: Dict[CotTrieNode, Dict[str, Any]]
) -> Dict[str, Any]:
    """Add secondary evaluations to trie nodes."""
    def process_node(node_dict: Dict[str, Any]) -> Dict[str, Any]:
        # Find matching node in evaluations
        node = next(
            (n for n in node_evaluations.keys() 
             if n.content.steps[0] == node_dict["content"]["steps"][0]),
            None
        )
        
        # Add secondary eval if found
        if node and node in node_evaluations:
            node_dict["content"]["secondary_eval"] = node_evaluations[node]
        
        # Process children recursively
        node_dict["children"] = [
            process_node(child) 
            for child in node_dict["children"]
        ]
        
        return node_dict
    
    # Create a copy to avoid modifying original
    new_trie = dict(trie_dict)
    new_trie["root"] = process_node(new_trie["root"])
    return new_trie

async def process_tries(
    problem_ids: Optional[List[int]] = None, 
    filter_model: Optional[str] = None,
    dataset: Optional[str] = None
):
    """Process tries with secondary evaluation."""
    # Initialize services
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    
    model = "claude-3-5-sonnet-20241022"
    model_service = AnthropicService(api_key=api_key, model=model)
    secondary_service = SecondaryEvaluationService(model_service)
    
    # Fetch tries to process
    tries = await fetch_unevaluated_tries(problem_ids, filter_model, dataset)
    print(f"Found {len(tries)} tries to evaluate")
    
    # Track processed IDs
    processed_ids = []
    
    async with async_session() as session:
        for trie_data in tqdm(tries, desc="Processing tries"):
            try:
                # Get secondary evaluations
                trie_obj, node_evaluations, paths_with_evaluations = await secondary_service.evaluate_trie(
                    trie_data['trie'],
                    trie_data['question'],
                    trie_data['answer']
                )

                if not paths_with_evaluations:
                    continue

                # Update database
                stmt = select(CotTrieModel).where(CotTrieModel.id == trie_data['id'])
                result = await session.execute(stmt)
                db_trie = result.scalar_one()
                
                # Update trie with evaluations
                db_trie.trie_evaled = trie_obj.serialize()
                session.add(db_trie)
                
                # Create CotPath records for each path
                for path, path_evaluations in paths_with_evaluations:
                    # For the path specific nodes, we substitute the secondary evaluation
                    # along that path.
                    for i, path_eval in enumerate(path_evaluations):
                        path.nodes[i].content.secondary_eval = path_eval

                    # Create CotPath record
                    path_record = CotPathModel.from_cot_path(
                        path,
                        cot_trie_id=db_trie.id,
                        unfaithfulness_condition=trie_obj.unfaithfulness_condition
                    )
                    session.add(path_record)

                await session.commit()
                processed_ids.append(trie_data['id'])
                
            except Exception as e:
                print(f"Error processing trie {trie_data['id']}: {str(e)}")
                await session.rollback()
    
    # Save processed IDs
    with open('scripts/updated_cot_tries.json', 'w') as f:
        json.dump({
            'processed_ids': processed_ids,
            'count': len(processed_ids),
            'dataset': dataset,
            'model': filter_model
        }, f, indent=2)
    
    print(f"\nProcessed {len(processed_ids)} tries successfully")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process secondary evaluations for COT tries')
    parser.add_argument('--problem-ids', type=int, nargs='+',
                       help='Specific problem IDs to process. If not provided, processes all unevaluated tries.')
    parser.add_argument('--model', type=str, required=False,
                       help='Model that was used to evaluate the tries.')
    parser.add_argument('--dataset', type=str, required=False,
                       help='Dataset to process (e.g., "gsm8k", "MATH", "MMLU")')
    
    args = parser.parse_args()
    
    # Convert to list if provided
    problem_ids = args.problem_ids if args.problem_ids else None
    
    if problem_ids:
        print(f"Processing specific problem IDs: {problem_ids}")
    else:
        print("Processing all unevaluated tries")
        
    if args.dataset:
        print(f"Filtering for dataset: {args.dataset}")
    if args.model:
        print(f"Filtering for model: {args.model}")
    
    asyncio.run(process_tries(problem_ids, args.model, args.dataset)) 