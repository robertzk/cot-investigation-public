"""
Compare TransformerLens generation vs. Ollama generation for a random path
in a CoT trie. This script:
    1. Loads CotTrie objects from the database for ollama/gemma2:2b model
    2. For each trie, picks a random path and reconstructs the exact prompts
    3. Attempts to replicate Ollama's generations using TransformerLens
       with matching seeds and temperatures
"""
import argparse
import asyncio
import random
import torch
from typing import List, Optional, Tuple
from sqlalchemy import func, select
import json

from app.models import async_session, Problem, CotTrie
from transformer_lens import HookedTransformer
from transformer_lens.HookedTransformerConfig import HookedTransformerConfig
from app.data_structures.cot_trie import CotTrie as CotTrieDS
from app.types.cot_trie import CotTrieNode

MODEL_NAME = "ollama/gemma2:2b"
NUM_SAMPLES = 3  # Number of different tries to examine


async def load_cot_tries_from_db() -> List[Tuple[CotTrieNode, str]]:
    """Load tries directly from database."""
    async with async_session() as session:
        query = (
            select(CotTrie, Problem.question)
            .join(Problem, CotTrie.problem_id == Problem.id)
            .where(CotTrie.model == MODEL_NAME)
            .order_by(func.random())
            .limit(NUM_SAMPLES)
        )
        
        result = await session.execute(query)
        tries_and_questions = []
        
        for trie_record, question in result:
            trie_node = CotTrieDS(trie_record.trie).root
            tries_and_questions.append((trie_node, question))
            
        return tries_and_questions

def load_cot_tries_from_json(json_path: str) -> List[Tuple[CotTrieNode, str]]:
    """Load tries from JSON file."""
    with open(json_path) as f:
        data = json.load(f)
    
    tries_and_questions = []
    for item in data:
        trie_node = CotTrieDS(item['trie']).root
        tries_and_questions.append((trie_node, item['question']))
    
    return tries_and_questions

async def load_cot_tries() -> List[Tuple[CotTrie, str]]:
    """
    Load a few CotTrie records from the database where model='ollama/gemma2:2b'.
    Returns list of (trie_node, question) tuples.
    """
    async with async_session() as session:
        # Get tries for the Ollama model
        query = (
            select(CotTrie, Problem.question)
            .join(Problem, CotTrie.problem_id == Problem.id)
            .where(CotTrie.model == MODEL_NAME)
            .order_by(func.random())
            .limit(NUM_SAMPLES)
        )
        
        result = await session.execute(query)
        tries_and_questions = []
        
        for trie_record, question in result:
            # Deserialize the trie JSON into a CotTrieNode
            trie_node = CotTrieDS(trie_record.trie).root
            tries_and_questions.append((trie_node, question))
            
        return tries_and_questions

def format_ollama_prompt(question: str, previous_steps: List[str] = None) -> str:
    """
    Format the prompt exactly as Ollama would see it, including chat template.
    
    Args:
        question: The original problem question
        previous_steps: Optional list of previous reasoning steps to include
    """
    base_prompt = f"{question}\n\nWrite down your answer step by step, and number each step (\"1.\", \"2.\", etc.)."
    
    # Format as Ollama chat message
    if previous_steps:
        steps_text = "".join(previous_steps)
        return [{"role": "user", "content": base_prompt}, {"role": "assistant", "content": steps_text}]
    else:
        return [{"role": "user", "content": base_prompt}]

def pick_random_path(node: CotTrieNode, max_depth: int = 3) -> List[Tuple[CotTrieNode, str]]:
    """Pick a random path through the trie up to max_depth."""
    path = []
    current = node
    while current.children and len(path) < max_depth:
        path.append((current, current.content.steps[0]))
        current = random.choice(current.children)
    # Add the final node's steps
    path.append((current, current.content.steps[0]))
    return path

def format_gemma_chat(messages):
    # As per the gemma instruct template: https://github.com/ollama/ollama/blob/3919f4ba3d0c40f50b4b89474e3306a900a15eed/template/gemma-instruct.gotmpl#L8
    """Format messages exactly as Ollama does for Gemma models."""
    formatted = ""
    for msg in messages:
        if msg["role"] == "user":
            formatted += f"<start_of_turn>user\n{msg['content']}<end_of_turn>\n"
        elif msg["role"] == "assistant":
            formatted += f"<start_of_turn>model\n{msg['content']}<end_of_turn>\n"
    formatted += "<start_of_turn>model\n"  # Add the final model turn
    return formatted

async def replicate_ollama_in_transformer_lens(
    trie_node: CotTrieNode,
    question: str,
    model_path: str = "google/gemma-2b-it"
) -> None:
    """
    For each step in a random path through the trie:
    1. Reconstruct the exact Ollama prompt
    2. Use matching seed/temperature in TransformerLens
    3. Compare outputs
    """
    # Get a random path through the trie
    path = pick_random_path(trie_node)
    
    # Load the model (you'll need the actual Gemma checkpoint)
    model = HookedTransformer.from_pretrained(model_path, device="cuda")
    
    current_messages = []

    # For each step in the path:
    for step_idx, (node, step_text) in enumerate(path[:-1]):
        current_messages.append(step_text)

        # Get the generation parameters used by Ollama
        next_seed = path[step_idx + 1][0].content.args[0].get("seed")
        next_temperature = path[step_idx + 1][0].content.args[0].get("temperature")
            
        # Format prompt exactly as Ollama would
        prompt_messages = format_ollama_prompt(question, current_messages)
        prompt_text = format_gemma_chat(prompt_messages)
        import pdb; pdb.set_trace()
        
        print(f"\n=== Step {step_idx + 1} | seed={next_seed}, temperature={next_temperature} ===")
        print("Original Ollama output:\n", step_text)
        
        # Set random seeds
        if next_seed is not None:
            HookedTransformerConfig.set_seed_everywhere(None, next_seed)
            # torch.manual_seed(step_seed)
            # random.seed(step_seed)
            
        # Generate with TransformerLens
        output = model.generate(
            prompt_text,  # You may need to adjust tokenization/formatting
            max_new_tokens=100,  # Adjust based on typical response length
            temperature=next_temperature
        )
        print("\nTransformerLens output:\n", output)


async def main():
    parser = argparse.ArgumentParser(description='Compare Ollama vs TransformerLens generations')
    parser.add_argument('--json-file', type=str, help='Path to JSON file containing CoT tries')
    args = parser.parse_args()
    
    # Load tries either from JSON or database
    if args.json_file:
        tries_and_questions = load_cot_tries_from_json(args.json_file)
    else:
        tries_and_questions = await load_cot_tries_from_db()
    
    # Process each trie
    for trie_node, question in tries_and_questions:
        print(f"\n{'='*80}\nProcessing new trie\n{'='*80}")
        await replicate_ollama_in_transformer_lens(trie_node, question)

if __name__ == "__main__":
    asyncio.run(main())