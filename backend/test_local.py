import torch
from transformer_lens.HookedTransformerConfig import HookedTransformerConfig
from transformer_lens import HookedTransformer

import psycopg2
import json

#trie = {"root": {"content": {"steps": ["Here's how to solve the problem:\n\n1. "], "step_indices": [1], "args": [{"seed": 967475, "temperature": 0.62}], "correct": "correct", "answer_correct": None}, "children": [{"content": {"steps": [" **Calculate the total number of slices of bread:** Jimmy uses 8 sandwiches * 2 slices/sandwich = 16 slices of bread.\n\n2. ", " **Calculate the total number of slices of bread needed:** Jimmy needs 8 sandwiches * 2 slices/sandwich = 16 slices of bread.\n\n2. ", " **Calculate the total number of bread slices:** Jimmy uses 8 sandwiches * 2 slices/sandwich = 16 slices of bread.\n\n2. "], "step_indices": [1, 2, 3], "args": [{"seed": 121209, "temperature": 0.63}, {"seed": 110311, "temperature": 0.7}, {"seed": 130015, "temperature": 0.76}], "correct": "correct", "answer_correct": None, "explanation": "Continuations 1, 2, and 3 are all equivalent because they:\n1. All calculate the total number of bread slices needed using the same multiplication (8 sandwiches \u00d7 2 slices)\n2. All arrive at the same result (16 slices)\n3. Use slightly different wording but convey exactly the same logical step\n4. All properly set up for a second step (indicated by \"2.\")\n\nThe continuations are all correct as they accurately calculate the total number of bread slices needed for 8 sandwiches using 2 slices each. This is not the final step because determining the number of packs needed hasn't been calculated yet (which would require dividing 16 by 4).\n", "meta": {"inputs": ["<bos><start_of_turn>user\nJimmy decides to make sandwiches for a picnic.  He makes 8 sandwiches in total, using two slices of bread each.  How many packs of bread does he need to buy to make these sandwiches, assuming he starts with no bread and each pack has 4 slices of bread in it?\n\nWrite down your answer step by step, and number each step (\"1.\", \"2.\", etc.).<end_of_turn>\n<start_of_turn>model\nHere's how to solve the problem:\n\n1.", "<bos><start_of_turn>user\nJimmy decides to make sandwiches for a picnic.  He makes 8 sandwiches in total, using two slices of bread each.  How many packs of bread does he need to buy to make these sandwiches, assuming he starts with no bread and each pack has 4 slices of bread in it?\n\nWrite down your answer step by step, and number each step (\"1.\", \"2.\", etc.).<end_of_turn>\n<start_of_turn>model\nHere's how to solve the problem:\n\n1.", "<bos><start_of_turn>user\nJimmy decides to make sandwiches for a picnic.  He makes 8 sandwiches in total, using two slices of bread each.  How many packs of bread does he need to buy to make these sandwiches, assuming he starts with no bread and each pack has 4 slices of bread in it?\n\nWrite down your answer step by step, and number each step (\"1.\", \"2.\", etc.).<end_of_turn>\n<start_of_turn>model\nHere's how to solve the problem:\n\n1."]}}, "children": [{"content": {"steps": ["  **Calculate the number of packs of bread needed:** Jimmy needs 16 slices / 4 slices/pack = 4 packs of bread.\n\n**Answer:** Jimmy needs to buy 4 packs of bread. \n<end_of_turn><eos>", "  **Determine the number of packs needed:** Jimmy needs 16 slices / 4 slices/pack = 4 packs of bread. \n\n**Answer:** Jimmy needs to buy 4 packs of bread. \n<end_of_turn><eos>", " **Divide the total slices by the number of slices per pack:** Jimmy needs 16 slices / 4 slices/pack = 4 packs of bread.\n\n**Answer:** Jimmy needs to buy 4 packs of bread. \n<end_of_turn><eos>"], "step_indices": [1, 2, 3], "args": [{"seed": 658726, "temperature": 0.62}, {"seed": 686310, "temperature": 0.78}, {"seed": 436191, "temperature": 0.73}], "correct": "correct", "answer_correct": {"correct": "correct", "explanation": "Both the step and correct answer arrive at 4 packs of bread. The step divides 16 slices by 4 slices/pack to get 4 packs, while the correct answer first calculates the 16 slices needed (8 sandwiches \u00d7 2 slices) and then divides by 4 slices/pack to also get 4 packs of bread."}, "explanation": "Continuations 1, 2, and 3 are all equivalent because they:\n1. All perform the same mathematical operation (16 slices \u00f7 4 slices/pack)\n2. All arrive at the same answer (4 packs)\n3. All present the answer in the same format\n4. Only differ in the wording of the step description (\"Calculate\", \"Determine\", \"Divide\")\n", "meta": {"inputs": ["<bos><start_of_turn>user\nJimmy decides to make sandwiches for a picnic.  He makes 8 sandwiches in total, using two slices of bread each.  How many packs of bread does he need to buy to make these sandwiches, assuming he starts with no bread and each pack has 4 slices of bread in it?\n\nWrite down your answer step by step, and number each step (\"1.\", \"2.\", etc.).<end_of_turn>\n<start_of_turn>model\nHere's how to solve the problem:\n\n1.  **Calculate the total number of slices of bread:** Jimmy uses 8 sandwiches * 2 slices/sandwich = 16 slices of bread.\n\n2.", "<bos><start_of_turn>user\nJimmy decides to make sandwiches for a picnic.  He makes 8 sandwiches in total, using two slices of bread each.  How many packs of bread does he need to buy to make these sandwiches, assuming he starts with no bread and each pack has 4 slices of bread in it?\n\nWrite down your answer step by step, and number each step (\"1.\", \"2.\", etc.).<end_of_turn>\n<start_of_turn>model\nHere's how to solve the problem:\n\n1.  **Calculate the total number of slices of bread:** Jimmy uses 8 sandwiches * 2 slices/sandwich = 16 slices of bread.\n\n2.", "<bos><start_of_turn>user\nJimmy decides to make sandwiches for a picnic.  He makes 8 sandwiches in total, using two slices of bread each.  How many packs of bread does he need to buy to make these sandwiches, assuming he starts with no bread and each pack has 4 slices of bread in it?\n\nWrite down your answer step by step, and number each step (\"1.\", \"2.\", etc.).<end_of_turn>\n<start_of_turn>model\nHere's how to solve the problem:\n\n1.  **Calculate the total number of slices of bread:** Jimmy uses 8 sandwiches * 2 slices/sandwich = 16 slices of bread.\n\n2."]}}, "children": [], "terminal": True, "prefix": "Here's how to solve the problem:\n\n1.  **Calculate the total number of slices of bread:** Jimmy uses 8 sandwiches * 2 slices/sandwich = 16 slices of bread.\n\n2.   **Calculate the number of packs of bread needed:** Jimmy needs 16 slices / 4 slices/pack = 4 packs of bread.\n\n**Answer:** Jimmy needs to buy 4 packs of bread. \n<end_of_turn><eos>", "node_id": 2}], "terminal": False, "prefix": "Here's how to solve the problem:\n\n1.  **Calculate the total number of slices of bread:** Jimmy uses 8 sandwiches * 2 slices/sandwich = 16 slices of bread.\n\n2. ", "node_id": 1}], "terminal": False, "prefix": "Here's how to solve the problem:\n\n1. ", "node_id": 1}}

# Connect to the database
conn = psycopg2.connect(
    dbname="chainofthought",
    user="chainofthought", 
    password="chainofthought",
    host="localhost",
    port="5434"
)

# Create a cursor
cur = conn.cursor()

# Execute query to get latest trie
#cur.execute("SELECT trie FROM cot_tries ORDER BY id DESC LIMIT 1 OFFSET 0")
cur.execute("SELECT id, trie FROM cot_tries where id>=40")

# Import CotTrie class
from app.data_structures.cot_trie import CotTrie

# Fetch and process all tries
tries = []
while True:
    row = cur.fetchone()
    if row is None:
        break
    trie_dict = row[1]
    trie_id = row[0]
    trie_obj = CotTrie(trie_dict)
    tries.append((trie_id, trie_obj))

# Print depth of each trie
print("\nTrie depths:")
for i, (trie_id, trie_obj) in enumerate(tries):
    print(f"Trie {trie_id}: depth = {trie_obj.size() - trie_obj.depth()}")

# Get the first trie for the rest of the script

cur.execute("SELECT trie FROM cot_tries where id=154")
trie = cur.fetchone()[0]

# Close database connection
cur.close()
conn.close()

model = HookedTransformer.from_pretrained('google/gemma-2-2b-it')

i = 1
target_node = trie["root"]["children"][0]["children"][0]
step = target_node["content"]["steps"][i]
x = target_node["content"]["args"][i]
seed = x["seed"]; temperature = x["temperature"]

print(f"Seed: {seed}, Temperature: {temperature}")

input = target_node["content"]["meta"]["inputs"][i]

input = model.to_tokens(input, prepend_bos=False)

HookedTransformerConfig.set_seed_everywhere(None, seed)
with torch.inference_mode():
    next_tokens = model.generate(input, verbose=True, temperature=temperature, max_new_tokens=100)

print(f"||Expected ||:  {step}")
print(f"||Generated||: {''.join(model.to_str_tokens(next_tokens))}")

import pdb; pdb.set_trace()

