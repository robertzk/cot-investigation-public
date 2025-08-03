import asyncio
import os
import sys
from typing import List, Dict, Any
from sqlalchemy import select, text
from tqdm import tqdm

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import async_session, CotTrie as CotTrieModel, GSM8K
from app.data_structures.cot_trie import CotTrie
from app.data_structures.cot_path import CotPath

async def fetch_incorrect_tries() -> List[Dict[str, Any]]:
    """Fetch all tries containing incorrect steps."""
    async with async_session() as session:
        # Use text() for raw SQL with LIKE
        query = select(CotTrieModel, GSM8K).join(
            GSM8K,
            CotTrieModel.problem_id == GSM8K.id
        ).where(
            text("trie::text LIKE :pattern")
        ).params(
            pattern='%"correct": "incorrect"%'
        )
        
        result = await session.execute(query)
        tries = result.unique().all()
        
        # Convert to list of dicts with metadata
        return [{
            'id': trie.id,
            'dataset': trie.dataset,
            'problem_id': trie.problem_id,
            'model': trie.model,
            'question': gsm8k.question,
            'answer': gsm8k.answer,
            'trie': trie.trie
        } for trie, gsm8k in tries]

async def analyze_incorrect_paths():
    """Analyze all incorrect paths in the tries."""
    # Fetch tries with incorrect steps
    tries = await fetch_incorrect_tries()
    tries = [(trie, cot_trie) for trie in tries if (cot_trie := CotTrie(trie['trie'])).has_explanation()]
    print(f"Found {len(tries)} tries containing incorrect steps")
    
    # Process each trie
    all_paths: List[tuple[Dict[str, Any], CotPath]] = []
    
    for trie_obj, trie in tqdm(tries, desc="Analyzing tries"):
        # Find all paths containing incorrect steps
        paths = trie.find_incorrect_paths()
        
        # Store paths with metadata
        for path in paths:
            all_paths.append((trie_obj, path))
    
    print(f"\nFound {len(all_paths)} total incorrect paths")
    print(f"Average of {len(all_paths)/len(tries):.1f} incorrect paths per trie")
    
    # Group paths by model
    paths_by_model: Dict[str, List[tuple[Dict[str, Any], CotPath]]] = {}
    for trie_data, path in all_paths:
        model = trie_data['model']
        if model not in paths_by_model:
            paths_by_model[model] = []
        paths_by_model[model].append((trie_data, path))
    
    # Print stats by model
    print("\nStats by model:")
    for model, paths in paths_by_model.items():
        print(f"\n{model}:")
        print(f"  {len(paths)} incorrect paths")
        print(f"  Average path length: {sum(len(p[1].nodes) for p in paths)/len(paths):.1f} steps")
    
    # Drop into debugger for interactive analysis
    print("\nDropping into debugger. Available variables:")
    print("- all_paths: List of (trie_data, path) tuples")
    print("- paths_by_model: Dict mapping model names to lists of paths")
    print("- tries: Original trie data from database")
    
    import pdb; pdb.set_trace()

if __name__ == "__main__":
    asyncio.run(analyze_incorrect_paths()) 