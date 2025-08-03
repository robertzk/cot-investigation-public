import logging
import traceback
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from .services.anthropic_service import AnthropicService
from .models import async_session, Completion, Problem, LanguageModel, CotTrie
from .models.experiment import CotTrieEvalExperiment, CotTrieEvalExperimentRecord
import os
import pydantic
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, Dict, List, Optional
from enum import Enum
import csv

class Prompt(pydantic.BaseModel):
    prompt: str

class TrieNodeResponse(pydantic.BaseModel):
    content: dict
    children: List['TrieNodeResponse']
    terminal: bool
    prefix: str

# Needed for recursive Pydantic model
TrieNodeResponse.update_forward_refs()

class CotTrieResponse(pydantic.BaseModel):
    id: int
    dataset: str
    problem_id: int
    model: str
    question: str  # from Problem
    answer: str  # from Problem
    trie: dict
    incorrect_step_count: int
    total_nodes: int

def has_incorrect_non_leaf(node: dict) -> bool:
    """Check if a node has any incorrect steps that aren't leaves."""
    if (
        node["content"]["correct"] == "incorrect" 
        and len(node["children"]) > 0
    ):
        return True
    return any(
        has_incorrect_non_leaf(child) 
        for child in node["children"]
    )

def count_incorrect_non_leaves(node: dict) -> int:
    """Count the number of incorrect non-leaf nodes."""
    count = 0
    if (
        node["content"]["correct"] == "incorrect" 
        and len(node["children"]) > 0
    ):
        count += 1
    return count + sum(
        count_incorrect_non_leaves(child) 
        for child in node["children"]
    )

def count_total_nodes(node: dict) -> int:
    """Count the total number of nodes in the trie."""
    return 1 + sum(count_total_nodes(child) for child in node["children"])

app = FastAPI(title="Chain of Thought API", port=int(os.getenv("COT_BACKEND_PORT", 8001)))
# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://localhost:3002", "http://localhost:8001", "http://localhost:8002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get database session
async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session

# Initialize Anthropic service
anthropic_service = AnthropicService(api_key=os.getenv("ANTHROPIC_API_KEY"))

@app.post("/api/complete")
async def get_completion(prompt: Prompt):
    try:
        response = await anthropic_service.get_completion(prompt.prompt)
        return {"response": response.content[0].text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/complete-batch")
async def get_batch_completion(prompts: list[str]):
    try:
        responses = await anthropic_service.get_completions(prompts)
        return {"responses": [r.content[0].text for r in responses]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dataset/{dataset_name}/responses")
async def get_dataset_responses(
    dataset_name: str,
    session: AsyncSession = Depends(get_session),
    limit: int = 1000
):
    """Get dataset responses with their questions, model information, steps and evaluations."""
    try:
        # Create a query that joins all necessary tables
        query = (
            select(Problem)
            .where(Problem.dataset_name == dataset_name)
            .limit(limit)
        )
        
        result = await session.execute(query)
        rows = result.unique().all()
        
        # Format the response
        responses = [
            {
                "id": problem.id,
                "question": problem.question,
                "answer": problem.answer,
                "dataset": problem.dataset_name
            }
            for problem, in rows
        ]
        
        return responses
    except Exception as e:
        logging.error(f"Error fetching {dataset_name} responses: {e}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/cot-tries/incorrect", response_model=List[CotTrieResponse])
async def get_incorrect_cot_tries(
    session: AsyncSession = Depends(get_session),
    limit: Optional[int] = 10_000
):
    """Get CoT tries that have at least one incorrect step that isn't a leaf."""
    try:
        # Get tries and join with Problem for question text
        query = (
            select(CotTrie, Problem)
            .join(Problem, CotTrie.problem_id == Problem.id)
            #.where(
            #    CotTrie.trie_evaled.is_not(None)
            #)
            # .where(CotTrie.model == "ollama/gemma2:9b")
            .where(Problem.dataset_name == "MMLU")
            .limit(limit)
        )
        query = query.options(joinedload(CotTrie.cot_paths))  # Eager load paths

        result = await session.execute(query)
        tries = result.unique().all()

        incorrect_tries = []
        for trie, problem in tries:
            trie_dict = trie.trie_evaled or trie.trie
            # Add cot_paths to the trie dictionary
            trie_dict["cot_paths"] = [
                path.to_dict()
                for path in trie.cot_paths
            ]

            try:
                # Check if this trie has any incorrect non-leaf steps
                if has_incorrect_non_leaf(trie.trie["root"]) or True:
                    incorrect_tries.append({
                        "id": trie.id,
                        "dataset": trie.dataset,
                        "problem_id": trie.problem_id,
                        "model": trie.model,
                        "question": problem.question,
                        "answer": problem.answer,
                        "trie": trie_dict,
                        "incorrect_step_count": count_incorrect_non_leaves(trie_dict["root"]),
                        "total_nodes": count_total_nodes(trie_dict["root"]),
                    })

            except Exception as e:
                logging.error(f"Error processing trie {trie.id}: {str(e)}")
                continue

        return incorrect_tries
    except Exception as e:
        logging.error(f"Error fetching incorrect CoT tries: {e}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/api/cot-tries/experiment", response_model=Dict[str, Any])
async def get_experiment_cot_tries(
    experiment_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get all CoT tries for a given experiment."""
    try:
        # Get experiment and verify it exists
        query = select(CotTrieEvalExperiment).where(
            CotTrieEvalExperiment.id == experiment_id
        )
        result = await session.execute(query)
        experiment = result.scalar_one_or_none()
        
        if not experiment:
            raise HTTPException(status_code=404, detail=f"Experiment {experiment_id} not found")

        # Get all records and associated tries for this experiment
        # Include paths with joinedload
        query = (
            select(CotTrieEvalExperimentRecord, CotTrie, Problem)
            .join(CotTrie, CotTrieEvalExperimentRecord.cot_trie_id == CotTrie.id)
            .join(Problem, CotTrieEvalExperimentRecord.problem_id == Problem.id)
            .where(CotTrieEvalExperimentRecord.experiment_id == experiment_id)
            .options(joinedload(CotTrieEvalExperimentRecord.paths))  # Eager load paths
        )
        result = await session.execute(query)
        records = result.unique().all()

        tries = []
        for record, trie, problem in records:
            try:
                # Get the evaluated trie
                trie_dict = record.trie_evaled
                
                # Add cot_paths to the trie dictionary
                trie_dict["cot_paths"] = [
                    path.to_dict()
                    for path in record.paths
                ]

                tries.append({
                    "id": record.cot_trie_id,
                    "dataset": problem.dataset_name,
                    "problem_id": record.problem_id,
                    "model": trie.model,  # Get model from the original trie
                    "question": problem.question,
                    "answer": problem.answer,
                    "trie": trie_dict,  # Now includes cot_paths
                    "incorrect_step_count": count_incorrect_non_leaves(trie_dict["root"]),
                    "total_nodes": count_total_nodes(trie_dict["root"])
                })

            except Exception as e:
                logging.error(f"Error processing record {record.id}: {str(e)}")
                continue

        # Sort by number of incorrect steps
        tries.sort(
            key=lambda x: x["incorrect_step_count"], 
            reverse=True
        )

        return {
            "tries": tries,
            "experiment": {
                "experiment_desc": experiment.experiment_desc
            }
        }

    except Exception as e:
        logging.error(f"Error fetching experiment tries: {e}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

# Add new model for test cases
class TestCase(pydantic.BaseModel):
    model: str
    problem_id: int
    unfaithful: bool
    comments: str

@app.get("/api/test-cases", response_model=List[TestCase])
async def get_test_cases():
    """Get test cases from unfaithful_secondary_evals.csv."""
    try:
        csv_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'unfaithful_secondary_evals.csv')
        test_cases = []
        
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                test_cases.append({
                    "model": row['model'],
                    "problem_id": int(row['problem_id']),
                    "unfaithful": row['unfaithful'].lower() == 'true',
                    "comments": row['comments']
                })
        
        return test_cases
        
    except Exception as e:
        logging.error(f"Error fetching test cases: {e}")
        logging.error(f"Stack trace: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

