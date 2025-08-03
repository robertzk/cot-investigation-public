# %%
import asyncio
import os
import sys
from typing import List, Dict
import matplotlib.pyplot as plt
import numpy as np
from dataclasses import dataclass
from enum import Enum

os.environ["DATABASE_URL"] = "postgresql://chainofthought:chainofthought@localhost:5433/chainofthought"

# Add the backend directory to the Python path
backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
sys.path.insert(0, backend_dir)

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.models import CotTrie
from app.data_structures.cot_trie import CotTrieNode, CotContent, Correctness

# %%

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to False to reduce output noise
)

Session = sessionmaker(
    engine,
   expire_on_commit=False,
)

def deserialize_trie(trie_dict: Dict) -> CotTrieNode:
    """Deserialize a trie dictionary back into a CotTrieNode structure."""
    def deserialize_node(node_dict: Dict) -> CotTrieNode:
        content = CotContent(
            steps=node_dict["content"]["steps"],
            correct=Correctness(node_dict["content"]["correct"])
        )
        children = [deserialize_node(child) for child in node_dict["children"]]
        return CotTrieNode(
            content=content,
            children=children,
            prefix=node_dict["prefix"],
            terminal=node_dict["terminal"]
        )
    
    return deserialize_node(trie_dict["root"])

def has_incorrect_child(node: CotTrieNode) -> bool:
    """Check if a node has any incorrect children."""
    if node.content.correct == Correctness.INCORRECT:
        return True
    return any(has_incorrect_child(child) for child in node.children)

def compute_fill_rate(node: CotTrieNode, max_branching: int = 3) -> float:
    """
    Compute the fill rate of a trie node.
    Fill rate is (avg_branching - 1) / (max_branching - 1)
    """
    if not node.children:
        return 0.0
    
    # Count number of children at each level
    def count_children(n: CotTrieNode) -> List[int]:
        if not n.children:
            return []
        return [len(n.children)] + sum((count_children(child) for child in n.children), [])
    
    child_counts = count_children(node)
    if not child_counts:
        return 0.0
    
    avg_branching = sum(child_counts) / len(child_counts)
    fill_rate = (avg_branching - 1) / (max_branching - 1)
    return min(max(fill_rate, 0.0), 1.0)  # Clamp between 0 and 1

def analyze_tries():
    """Analyze all tries in the database."""
    with Session() as session:
        # Fetch all tries
        result = session.execute(select(CotTrie))
        tries = result.scalars().all()
        
        print(f"Found {len(tries)} tries")
        
        # Analysis metrics
        incorrect_count = 0
        fill_rates = []
        
        # Process each trie
        for trie in tries:
            try:
                # Deserialize trie
                root = deserialize_trie(trie.trie)
                
                # Check for incorrect children
                if has_incorrect_child(root):
                    incorrect_count += 1
                
                # Compute fill rate
                fill_rate = compute_fill_rate(root)
                fill_rates.append(fill_rate)
                
            except Exception as e:
                print(f"Error processing trie {trie.id}: {str(e)}")
                continue
        
        # Calculate statistics
        incorrect_proportion = incorrect_count / len(tries)
        avg_fill_rate = np.mean(fill_rates)
        
        print(f"\nAnalysis Results:")
        print(f"Total tries analyzed: {len(tries)}")
        print(f"Proportion with incorrect children: {incorrect_proportion:.2%}")
        print(f"Average fill rate: {avg_fill_rate:.2%}")
        
        # Plot fill rate histogram
        plt.figure(figsize=(10, 6))
        plt.hist(fill_rates, bins=20, edgecolor='black')
        plt.title('Distribution of CoT Trie Fill Rates')
        plt.xlabel('Fill Rate')
        plt.ylabel('Count')
        plt.grid(True, alpha=0.3)
        plt.show()

        return {
            'total_tries': len(tries),
            'incorrect_proportion': incorrect_proportion,
            'avg_fill_rate': avg_fill_rate,
            'fill_rates': fill_rates
        }

# %%
# Run the analysis
results = analyze_tries()

# %%
# Find tries with incorrect non-leaf steps
def has_incorrect_non_leaf(node: CotTrieNode) -> bool:
    """Check if a node has any incorrect steps that aren't leaves."""
    if node.content.correct == Correctness.INCORRECT and len(node.children) > 0:
        return True
    return any(has_incorrect_non_leaf(child) for child in node.children)

with Session() as session:
    result = session.execute(select(CotTrie))
    tries = result.scalars().all()
    
    incorrect_non_leaf_tries = []
    for trie in tries:
        try:
            root = deserialize_trie(trie.trie)
            if has_incorrect_non_leaf(root):
                incorrect_non_leaf_tries.append({
                    'id': trie.id,
                    'problem_id': trie.problem_id,
                    'model': trie.model,
                    'trie': trie.trie,
                    'incorrect_step_count': sum(1 for node in root.children if node.content.correct == Correctness.INCORRECT and len(node.children) > 0)
                })
        except Exception as e:
            print(f"Error processing trie {trie.id}: {str(e)}")
            continue

print(f"\nAnalysis of incorrect non-leaf steps:")
print(f"Total tries: {len(tries)}")
print(f"Tries with incorrect non-leaf steps: {len(incorrect_non_leaf_tries)}")
print(f"Proportion: {len(incorrect_non_leaf_tries) / len(tries):.2%}")

# Sort by number of incorrect non-leaf steps
incorrect_non_leaf_tries.sort(key=lambda x: x['incorrect_step_count'], reverse=True)

# Show a few examples of the worst offenders
if incorrect_non_leaf_tries:
    print("\nTop 3 tries with most incorrect non-leaf steps:")
    for trie in incorrect_non_leaf_tries[:3]:
        print(f"Trie ID: {trie['id']}, Problem ID: {trie['problem_id']}, Incorrect non-leaf steps: {trie['incorrect_step_count']}")

# Save to file for further analysis
import json
with open('incorrect_non_leaf_tries.json', 'w') as f:
    json.dump(incorrect_non_leaf_tries, f, indent=2)
print(f"\nSaved {len(incorrect_non_leaf_tries)} tries with incorrect non-leaf steps to incorrect_non_leaf_tries.json")

# %% 

# Create histogram of trie sizes
def count_nodes(node: CotTrieNode) -> int:
    """Count total number of nodes in a trie including the root."""
    return 1 + sum(count_nodes(child) for child in node.children)

trie_sizes = []
with Session() as session:
    result = session.execute(select(CotTrie))
    tries = result.scalars().all()
    
    for trie in tries:
        try:
            root = deserialize_trie(trie.trie)
            size = count_nodes(root)
            trie_sizes.append(size)
        except Exception as e:
            print(f"Error processing trie {trie.id}: {str(e)}")
            continue

import matplotlib.pyplot as plt

plt.figure(figsize=(10, 6))
plt.hist(trie_sizes, bins=50, edgecolor='black')
plt.title('Distribution of CoT Trie Sizes')
plt.xlabel('Number of Nodes')
plt.ylabel('Frequency')
plt.grid(True, alpha=0.3)

# Add summary statistics
plt.text(0.95, 0.95, 
         f'n = {len(trie_sizes)}\n'
         f'mean = {np.mean(trie_sizes):.1f}\n'
         f'median = {np.median(trie_sizes):.1f}\n'
         f'std = {np.std(trie_sizes):.1f}',
         transform=plt.gca().transAxes,
         verticalalignment='top',
         horizontalalignment='right',
         bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

plt.show()

# %%
