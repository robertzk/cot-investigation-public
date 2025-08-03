import asyncio
import os
import sys
from sqlalchemy import select

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import async_session
from app.models.cot_path import CotPath
from app.models.experiment import CotTrieEvalExperimentRecord
from app.data_structures.cot_trie import CotTrie
from app.types.cot_trie import CotTrieNode

async def fix_path_unfaithfulness(experiment_id: int):
    """Fix unfaithfulness flags for all paths in an experiment."""
    try:
        async with async_session() as session:
            # Get all records and paths in one query
            query = select(CotTrieEvalExperimentRecord, CotPath).where(
                CotTrieEvalExperimentRecord.experiment_id == experiment_id
            ).join(
                CotPath, 
                CotPath.cot_trie_eval_experiment_record_id == CotTrieEvalExperimentRecord.id
            )
            result = await session.execute(query)
            records_and_paths = result.unique().all()

            if not records_and_paths:
                print(f"No records found for experiment {experiment_id}")
                return

            # Create a default trie to get the unfaithfulness condition
            default_trie = CotTrie({})
            unfaithfulness_condition = default_trie.unfaithfulness_condition

            # Process paths
            total_paths = 0
            updated_paths = 0

            for record, path in records_and_paths:
                total_paths += 1
                
                # Reconstruct nodes from path data
                nodes = []
                for node_data in path.cot_path:
                    node = CotTrieNode.deserialize(node_data)
                    nodes.append(node)

                # Check for unfaithful steps using the standard condition
                has_unfaithful = any(
                    unfaithfulness_condition(node)
                    for node in nodes
                )

                # Update if the flag is different
                if path.is_unfaithful != has_unfaithful:
                    path.is_unfaithful = has_unfaithful
                    updated_paths += 1

            # Commit all changes
            await session.commit()

            print(f"Processed {total_paths} paths")
            print(f"Updated {updated_paths} paths")

    except Exception as e:
        print(f"Error fixing path unfaithfulness: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

async def main():
    if len(sys.argv) != 2:
        print("Usage: python fix_path_unfaithfulness.py <experiment_id>")
        return 1

    try:
        experiment_id = int(sys.argv[1])
    except ValueError:
        print("Error: experiment_id must be an integer")
        return 1

    await fix_path_unfaithfulness(experiment_id)

if __name__ == "__main__":
    asyncio.run(main()) 