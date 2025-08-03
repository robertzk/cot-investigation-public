# Refactoring Plan for Supporting Arbitrary Datasets

Currently, the backend is heavily tied to GSM8K in various sections of the code. This document outlines a step-by-step plan to generalize the logic so that one can import and use any dataset that has at least a “question” and “answer” field. The goal is to avoid rewriting large code sections for each new dataset while keeping or extending the existing features (e.g., CoT generation and secondary evaluations).

---

## Overview of the Problem

1. The GSM8K dataset is tightly integrated: 
   - The ORM models reference “gsm8k” tables directly (e.g. “gsm8k” table, “gsm8k_cot_steps”, “gsm8k_cot_step_evals”).
   - The code that fetches data and returns data to the user is hard-coded with GSM8K table references.
   - APIs and logic for building CoT tries (CotTrie) assume presence of GSM8K records and fields named “question” and “answer.”

2. We want to:
   - Maintain the ability to store and serve GSM8K data.
   - Add new datasets with minimal changes, e.g. “datasetX,” “datasetY,” each with their own table / schema.
   - Support the same chain-of-thought building logic for any dataset that has a “question” and “answer.”

3. Desired approach:
   - Introduce a “Dataset” or “Problem” abstraction layer in the database. 
   - Standardize the minimal fields needed: (id, question, answer, dataset_name).
   - Modify the existing CoT logic so it references the new generalized dataset structure, instead of “gsm8k.”

---

## Steps to Achieve the Refactoring

### 1. Create a “Problem” Table / ORM Model

Currently, GSM8K is a custom table with columns id, question, answer. For generalization:

1. Introduce a “Problem” (or “DatasetProblem”) table with:
   - id: integer primary key.
   - dataset_name: text or string identifying the dataset (e.g., “gsm8k”, “datasetX”).
   - question: text field.
   - answer: text field.
   This could replace or extend the GSM8K table. Alternatively, you can have a “ Problems ” table that includes a dataset column, or else unify everything under a single schema.

2. Migrate existing GSM8K records into this new table (if you want to unify them). Or, keep GSM8K as is but ensure your code can read from a standardized “Problem” interface, so that the queries can happen on different dataset tables in the same way.

3. Update or create relationships (or references) so that each problem belongs to exactly one dataset, or has a “dataset_name” column that identifies it.

### 2. Modify the CotTrie Model to Reference the Generic Table

The “cot_tries” table references “gsm8k.id” as the “problem_id”. We can change this to refer to the new “Problems” table with a foreign key:

• Instead of:
  problem_id = Column(Integer, ForeignKey(“gsm8k.id”), …),
• We do:
  problem_id = Column(Integer, ForeignKey(“problems.id”), …)

Additionally, keep a “dataset” string or a “dataset_id” if you want fine-grained references. The main result is that a single CoT can point to a problem from any dataset.

### 3. Switch All References to “GSM8K” in the Code

Look for the following references to the GSM8K model:

• “app/models/gsm8k.py” → Contains the “GSM8K” class. We can either keep it or rename it “Problem” or “DatasetProblem.”  
• The references in:
  - main.py
  - experiment code
  - get_incorrect_cot_tries
  - get_experiment_cot_tries
  - etc.

Refactor them systematically:
• Where the code does:  
  select(CotTrie, GSM8K) … join(GSM8K, CotTrie.problem_id == GSM8K.id)  
  → Replace:
     select(CotTrie, Problem) … join(Problem, CotTrie.problem_id == Problem.id)
• Where the code references gsm8k.question, gsm8k.answer → refer to problem.question, problem.answer
• Where the code references “GSM8K” as dataset → set problem.dataset_name = "gsm8k"

### 4. Modify Existing Migrations / Models for a Generic Problem Interface

1. Either rename “GSM8K” model to something more general, or create a new “Problem” model.  
2. If we create a new “Problem” model, we must carefully do the database migration to unify or move existing GSM8K data.  
3. Potentially keep GSM8K as a specialized model if desired. But the main code path that fetches question/answer should go through an interface that doesn’t specifically mention “gsm8k.”

### 5. Update or Remove GSM8K-Specific Code (API Endpoints, Queries, etc.)

Some endpoints like /api/gsm8k/responses are specialized. We can do any of these strategies:

• Rename them to /api/dataset/<dataset_name>/responses.  
• Or unify them into a single /api/problem/responses endpoint, which takes an optional dataset parameter.  

Wherever we do queries for GSM8K, either do a join with “Problem” + “dataset_name = ‘gsm8k’” or for other dataset_name = “some_other_dataset.”

### 6. Provide a Standard for Importing / Storing any New Dataset

We want the user to be able to do something like:

1. Insert new data into “Problem” (with question, answer, dataset_name).
2. Possibly create a “/api/dataset/import” endpoint that ingests CSV or JSON specifying question and answer columns for a new dataset.
3. Then run the same chain-of-thought building logic for that data.

Hence, the backend code that runs a CoT or does a “build tries” function can simply look up:

• problem = session.query(Problem).filter(Problem.id == some_id).one()  
• question, answer = problem.question, problem.answer  

No need to distinguish if it’s GSM8K or not.

### 7. Update the CoT Building and Secondary Evaluation Paths

Throughout:
- “CotTrieBuilder” references the problem’s question and answer. Make sure it references problem.question and problem.answer from the new “Problem” entity.
- The code that references “GSM8K” or “problem_id” or “CotTrie.problem_id” might rely on a direct join. We can do a general join with “Problem”:
  select(CotTrie, Problem) … join(Problem, CotTrie.problem_id == Problem.id)
- Double-check that we do not rely on GSM8K-specific columns or logic (like certain text formatting or special columns) anywhere else in the chain-of-thought building or evaluation logic.

### 8. Ensure Migrations and Database are Synchronized

Once the code references “Problem” not GSM8K, we can:

1. Migrate existing gsm8k data into Problem.  
2. (Optional) Mark the old gsm8k table as deprecated or remove it if fully replaced.  
3. Possibly rename local references to “problem_id” or “problem_table” for clarity.

### 9. Confirm That the Frontend / Using Code Still Works

Check any references in the UI or queries to GSM8K endpoints. They must align with the new structure. Possibly we keep backward compatibility by:
• Creating a “/api/gsm8k/…” route that merges with or proxies to “/api/problem/…?dataset_name=gsm8k”  

### 10. Optional: Keep or Remove GSM8K-Specific Tables

If the team wants to preserve the old table for historical data, we can store references in the new “Problem” table to the old GSM8K entry or keep a read-only approach. Another approach is to do a full data migration and no longer rely on the old table.  

---

## Detailed Checklist

1. In “app/models/gsm8k.py,” rename or remove GSM8K class:
   - Option 1: Rename to “Problem.” Add a “dataset_name” column (default “gsm8k”) for existing rows.  
   - Option 2: Create a new “Problem” class in “models/problem.py” and unify data there, or store parallel data for new datasets.
2. Change references in “cot_tries” foreign key to Problem.id, or keep gsm8k for existing references if we want to keep that table intact, but then store for new datasets in Problem. A single approach is simpler: unify behind Problem.
3. Update “backend/app/main.py,” “/api/gsm8k/*” endpoints:
   - Create a new route “/api/problem/*” that does the same logic but references the generic “Problem.”  
   - Decide if we keep old endpoints with a note that it’s for backward compatibility or remove them and replace with new ones.
4. Scan the code for “GSM8K,” referencing it in queries:
   - For example, “select(CotTrie, GSM8K)” → “select(CotTrie, Problem).join(Problem, …).”  
   - Same for references to “gsm8k.question” → “problem.question” and “gsm8k.answer” → “problem.answer.”
5. For the plan to import new datasets:
   - Possibly create a new table for each dataset if the user wants. Alternatively, store all in the single “Problem” table with a dataset name.  
   - Expose an endpoint that can import a CSV or JSON with columns “question,” “answer,” and “dataset_name” or something else. Insert them as new rows in “Problem.”
6. Double-check references to “GSM8KCoT,” “GSM8KCoTStep,” “GSM8KCoTStepEval.” If these are no longer needed, we can remove them. Or if we still want to keep them as optional expansions for multi-step storing, rename them to “ProblemCoT,” “ProblemCoTStep,” “ProblemCoTStepEval,” or unify them with the existing “CotTrie” approach.  
7. Ensure that the final approach still supports loading the old GSM8K data if desired. This might require a data migration or leaving the old structures in place until fully phased out.

---

## Conclusion

By following these steps, we’ll generalize the existing code so that any new dataset (with minimal fields question/answer) can slot into the same chain-of-thought pipeline. The key changes revolve around introducing a single “Problem” abstraction with “dataset_name,” updating references in “cot_tries,” and modifying the endpoints to query against the new structure instead of the GSM8K table.
