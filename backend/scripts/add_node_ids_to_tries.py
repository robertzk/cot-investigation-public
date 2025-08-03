import asyncio
import os
import sys
from typing import Dict, Any
from sqlalchemy import select, inspect
from sqlalchemy.orm.attributes import flag_modified

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import async_session
from app.models.experiment import CotTrieEvalExperimentRecord

def add_node_ids_to_trie(trie_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add node IDs to a trie dictionary."""
    next_id = 1
    
    def process_node(node: Dict[str, Any]) -> Dict[str, Any]:
        nonlocal next_id
        
        # Add node_id to current node
        node['node_id'] = next_id
        next_id += 1
        
        # Process children recursively
        if 'children' in node:
            node['children'] = [
                process_node(child)
                for child in node['children']
            ]
        
        return node
    
    # Create a copy to avoid modifying original
    new_trie = dict(trie_dict)
    new_trie['root'] = process_node(new_trie['root'])
    return new_trie

def has_node_ids(node: Dict[str, Any]) -> bool:
    if 'node_id' in node:
        return True
    return any(
        has_node_ids(child) 
        for child in node.get('children', [])
    )

async def add_node_ids_to_experiment_tries():
    """Add node IDs to all tries in experiment records."""
    async with async_session() as session:
        async with session.begin():
            # Get all experiment records
            query = select(CotTrieEvalExperimentRecord)
            result = await session.execute(query)
            records = result.scalars().all()
            
            print(f"Found {len(records)} experiment records")
            
            # Process each record
            for record in records:
                # Skip if trie already has node IDs
                if record.trie_evaled and has_node_ids(record.trie_evaled['root']):
                    continue

                if record.trie_evaled:
                    try:
                        # Add node IDs to trie
                        updated_trie = add_node_ids_to_trie(record.trie_evaled)
                        
                        # Update record
                        record.trie_evaled = updated_trie
                        flag_modified(record, "trie_evaled")
                        
                    except Exception as e:
                        print(f"Error processing record {record.id}: {str(e)}")
                        raise  # Let the session.begin() context manager handle the rollback
            
            print("Finished processing all records")

if __name__ == "__main__":
    asyncio.run(add_node_ids_to_experiment_tries()) 