* [X] Double check a few examples to ensure that trie structuring is correct
* [ ] Check Turpin et al paper
* [ ] Bullet point draft of write-up
  * Emphasize definition of unfaithfulness:
    1. Model is correct in the final step
    2. Makes makes at least one mistake
    3. Evaluator model says the model never contracted or corrected itself.
* [X] Add local model generation
* [X] Add Ollama model generation
* [X] Apply final evaluation model to check against correct answer
* [ ] Secondary evaluation to correct tries:
    * [ ] Apply final evaluation model to check for self-correction on *incorrect* paths.
    * [ ] Double check spurious incorrect markings using additional instructions. (Make a dataset of all and look for common mistakes.)
* [ ] Build tokenized dataset of all paths (hitting terminal node) with correct answer, and intermediate checkpoints on tokens.
  * [ ] Upload to HF

Bugs:
* [ ] Error in stream_response: Sizes of tensors must match except in dimension 1. Expected size 1 but got size 0 for tensor number 1 in the list.
        Saved trie for problem 39
        Processing problems:  59%|█████████████████████████████████████▊                          | 59/100 [3:16:41<1:54:04, 166.94s/it]Error in stream_response: Sizes of tensors must match except in dimension 1. Expected size 1 but got size 0 for tensor number 1 in the list.
        Error processing problem 72: Sizes of tensors must match except in dimension 1. Expected size 1 but got size 0 for tensor number 1 in the list.
* [ ] Fix bug with incomplete steps in the trie if an earlier step completes. Example: 589 for claude-3-haiku-20240307.
        This probably has to do with the <final> list being wrong.

Bugs:
* [ ] Figure out why secondary evaluation steps are not getting matched up correctly, or go back to the previous approach
   and start over with a new prompt.
    * Add ids to each step and annotate CoT nodes with ids. (apply the old alt1 cot first to annotate them).
    * Create an evaluation script against the known faithful / unfaithful steps to see if we can get a better match.s

## Todo's 01-01-25

Goal: Improve the secondary evaluation of unfaithfulness to be at least 90% accurate.

* [x] Add a "node_id" to each node in the trie. Write a script to add this to the tries in cot_tries and cot_trie_eval_experiment_record. Also modify the CotTrieBuilder to add this
and update backend and frontend types accordingly.
* [x] Create a migration to add a CotPath model. Include a join table to the cot_trie_eval_experiment_record table and the cot_tries table. Also include a column for answer_correct and is_unfaithful. You can assume
that only one of cot_trie_id or cot_trie_eval_experiment_record_id will be present in the table. The CotPath table should include the node_id corresponding to the
step in the CoT trie node. Also update the CotTrie and CotTrieEvalExperimentRecord types to include backreferences to the new CotPath table.
* [x] Alter the cotpath model to remove node_id and add a node_ids as a json type (it will contain an ordered list of integers). Also add a cot_path column that is a json type (it will contain the actual list of cot nodes).
* [x] Write a script that can be run as a CLI to backpopulate the CotPath table for a given experiment. It should step over unfaithful paths and add a new CotPath record for each path.
* [x] Update the SecondaryEvalExperiment to create CotPath records for each unfaithful path.
* [x] Add a frontend router to display just the unfaithful paths for a given experiment. Use a compact flat structure to display the paths instead of the current tree structure.
* [x] Create a OAIService similar to the AnthropicService. Run the CotTrieBuilder to double check for any issues.
* [x] Run a new secondary evaluation experiment with O1. Double check the secondary evaluation prompt.
* [x] Fix is_faithful column in CotPath table setting (e.g. `update cot_path set is_unfaithful = (cot_path::varchar like '%"unfaithful"%');`)`)
* [x] Check whether secondary evals were applied correctly to gemma9b tries.
* [ ] Load a few more datasets.
  * [x] MATH
  * [x] MMLU
  * [ ] MathQA
  * [ ] TAL-SCQ5K-EN
  * [ ] MAWPS
* [ ] Check for reproducibility with ollama and local models.
  * [ ] Create TL snippet export from the UI and CLI.
* [ ] Collect all problem/model pairs that are possibly unfaithful. Run them through local model generation.
* [ ] (Timebox) Figure out how to speed up the TL local generation.
* [ ] Clean up final unfaithful CoT dataset. Remove some manually if necessary.
  * [ ] Consider using o1 as a second pass on some.  
* [ ] Fix bug with cut off branches in the trie (one branch concludes, other keeps going). Identify a way to find the tries with this issue and re-run them.

## Other ideas

* [ ] Write out the remaining todo's for dynamic experiments: one separate alt type
for each experiment as well as a variation of the SecondaryEvaluationExperiment (
  or possibly make this subclassable). An idea here is to use a custom Python path loader: if an
  experiment is currently mounted, we can use the path loader to load the paths for that experiment
  whenever modules require overrides.
* [ ] Try out several variations of the secondary evaluation prompt. Also ask models
  for ideas on how to improve the secondary evaluation. For example, we could separate
  the determination of correctness from the determination of faithfulness completely.
  * [x] Do a re-check of the unfaithful steps.


## Cleanups

* [ ] Remove the limit on id in main.py
* [ ] Clean up duplication of anthropic model names.

## Errors

Figure out how to fix this Anthropic service error:
Error streaming response: Error code: 429 - {'type': 'error', 'error': {'type': 'rate_limit_error', 'message': 'This request would exceed your organization’s rate limit of 20,000,000 prompt bytes per hour. For details, refer to: https://docs.anthropic.com/en/api/rate-limits; see the response headers for current usage. Please reduce the prompt length or the maximum tokens requested, or try again later. You may also contact sales at https://www.anthropic.com/contact-sales to discuss your options for a rate limit increase.'}}

## Interesting examples

### MMLU - Haiku

Problem 21924 - Model gets the correct answer by chance through a rounding error.
Problem 22222 - Model ignores the second derivative calc when determining the critical point (it states local min but then ignores that and uses it as the max). It might know internally what the second derivative is but incorrectly writes it out.
