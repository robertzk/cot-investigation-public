import asyncio
import os
import sys
from typing import List, Dict, Any, Set
from sqlalchemy import select, text
from tqdm import tqdm
import json

from app.types.correctness import Correctness, CorrectnessEvaluation

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import async_session, CotTrie as CotTrieModel, GSM8K
from app.data_structures.cot_trie import CotTrie
from app.data_structures.cot_path import CotPath

async def fetch_evaluated_tries() -> List[Dict[str, Any]]:
    """Fetch tries that have been secondarily evaluated."""
    async with async_session() as session:
        query = select(CotTrieModel, GSM8K).join(
            GSM8K,
            CotTrieModel.problem_id == GSM8K.id
        ).where(
            CotTrieModel.trie_evaled.isnot(None)
        )
        
        result = await session.execute(query)
        tries = result.unique().all()
        
        return [{
            'id': trie.id,
            'dataset': trie.dataset,
            'problem_id': trie.problem_id,
            'model': trie.model,
            'question': gsm8k.question,
            'answer': gsm8k.answer,
            'trie': trie.trie_evaled or trie.trie
        } for trie, gsm8k in tries]

def has_unfaithful_correct_path(trie: CotTrie) -> bool:
    """
    Check if trie has a path that:
    1. Ends in a correct terminal node
    2. Has exactly one unfaithful node before it
    """
    def check_path(path: CotPath) -> bool:
        # Check if path ends in correct node
        if path.nodes[-1].content.answer_correct.correct != Correctness.CORRECT:
            return False
        
        incorrect_count = sum(
            1 for node in path.nodes[:-1]
            if node.content.correct != Correctness.CORRECT or (node.content.secondary_eval and
            any(eval_.status == 'incorrect' 
                for eval_ in node.content.secondary_eval.evaluations))
        )
        
        return incorrect_count >= 1

    # Get all paths and check each one
    #all_paths = trie.find_unfaithful_paths()
    all_paths = trie.find_incorrect_paths()
    
    return any(check_path(path) for path in all_paths)

async def find_interesting_tries():
    """Find tries with unfaithful-to-correct paths."""
    tries = await fetch_evaluated_tries()
    print(f"Found {len(tries)} evaluated tries")
    
    interesting_cases = []
    
    for trie_data in tqdm(tries, desc="Analyzing tries"):
        try:
            trie = CotTrie(trie_data['trie'])
            if has_unfaithful_correct_path(trie):
                interesting_cases.append({
                    'id': trie_data['problem_id'],
                    'model': trie_data['model'],
                    'question': trie_data['question'],
                    'answer': trie_data['answer']
                })
        except Exception as e:
            print(f"Error processing trie {trie_data['id']}: {str(e)}")
            continue
    
    # Group by model
    cases_by_model: Dict[str, List[Dict[str, Any]]] = {}
    for case in interesting_cases:
        model = case['model']
        if model not in cases_by_model:
            cases_by_model[model] = []
        cases_by_model[model].append(case)
    
    # Print stats and save results
    print(f"\nFound {len(interesting_cases)} interesting cases:")
    for model, cases in cases_by_model.items():
        print(f"\n{model}: {len(cases)} cases")
    
    # Save detailed results
    output = {
        'total_count': len(interesting_cases),
        'by_model': {
            model: {
                'count': len(cases),
                'cases': cases
            }
            for model, cases in cases_by_model.items()
        },
        'trie_ids': [case['id'] for case in interesting_cases]
    }
    
    with open('scripts/unfaithful_correct_paths.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print("\nDropping into debugger for analysis.")
    print("Available variables:")
    print("- interesting_cases: List of all cases")
    print("- cases_by_model: Cases grouped by model")
    print("- tries: Original trie data")
    
    import pdb; pdb.set_trace()

if __name__ == "__main__":
    asyncio.run(find_interesting_tries()) 