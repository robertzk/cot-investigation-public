import asyncio
import os
import sys
import argparse
from typing import Dict, Any, List
from sqlalchemy import select

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import async_session
from app.models.experiment import CotTrieEvalExperiment, CotTrieEvalExperimentRecord
from app.models.cot_path import CotPath
from app.data_structures.cot_trie import CotTrie, CotPath as CotPathDS
from app.types.correctness import Correctness

def find_unfaithful_paths(trie_dict: Dict[str, Any]) -> List[CotPathDS]:
    """Find paths with unfaithful steps and their node IDs."""
    trie = CotTrie(trie_dict)
    return trie.find_unfaithful_paths()

async def backpopulate_paths(experiment_id: int):
    """Backpopulate CotPath records for a given experiment."""
    async with async_session() as session:
        async with session.begin():
            # Get experiment and verify it exists
            query = select(CotTrieEvalExperiment).where(
                CotTrieEvalExperiment.id == experiment_id
            )
            result = await session.execute(query)
            experiment = result.scalar_one_or_none()
            
            if not experiment:
                print(f"No experiment found with ID {experiment_id}")
                return
            
            # Get all records for this experiment
            query = select(CotTrieEvalExperimentRecord).where(
                CotTrieEvalExperimentRecord.experiment_id == experiment_id
            )
            result = await session.execute(query)
            records = result.scalars().all()
            
            print(f"Found {len(records)} records for experiment {experiment_id}")
            
            # Process each record
            total_paths = 0
            for record in records:
                if not record.trie_evaled:
                    continue
                
                try:
                    # Find unfaithful paths
                    paths = find_unfaithful_paths(record.trie_evaled)
                    
                    # Create CotPath records
                    for path in paths:
                        path = CotPath.from_cot_path(
                            path,
                            experiment_record_id=record.id
                        )
                        session.add(path)
                        total_paths += 1
                    
                except Exception as e:
                    print(f"Error processing record {record.id}: {str(e)}")
                    raise
            
            print(f"Created {total_paths} path records")

def main():
    parser = argparse.ArgumentParser(description='Backpopulate CotPath records for an experiment')
    parser.add_argument('--experiment-id', type=int, help='ID of the experiment to process')
    
    args = parser.parse_args()
    
    print(f"Processing experiment {args.experiment_id}")
    asyncio.run(backpopulate_paths(args.experiment_id))

if __name__ == "__main__":
    main() 