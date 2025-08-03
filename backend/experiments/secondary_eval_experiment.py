import asyncio
import os
import sys
import json
import csv
import argparse
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import select, text
from tqdm import tqdm

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import async_session, CotTrie, GSM8K
from app.models.experiment import CotTrieEvalExperiment, CotTrieEvalExperimentRecord
from app.services.anthropic_service import AnthropicService
from app.services.secondary_evaluation_service import SecondaryEvaluationService
from app.data_structures.cot_trie import CotTrie as CotTrieDS
from app.data_structures.cot_path import CotPath
from app.models.cot_path import CotPath as CotPathModel
from app.services.openai_service import OpenAIService
from app.services.local_model_service import LocalModelService

def add_node_ids_to_trie(trie_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add node IDs to a trie dictionary."""
    # Check if the trie already has node IDs
    def has_node_ids(node: Dict[str, Any]) -> bool:
        if 'node_id' in node and 'children' in node:
            return True
        return any(
            has_node_ids(child)
            for child in node.get('children', [])
        )

    # Check if root node already has IDs
    if has_node_ids(trie_dict['root']):
        return trie_dict

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

def load_test_cases(csv_path: str) -> List[Tuple[str, int, bool]]:
    """Load test cases from CSV file."""
    cases = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cases.append((
                row['model'],
                int(row['problem_id']),
                row['unfaithful'].lower() == 'true'
            ))
    return cases

class SecondaryEvalExperiment:
    def __init__(self, experiment_desc: str, model_name: Optional[str] = None):
        """Initialize experiment with specified model.
        
        Args:
            experiment_desc: Description of the experiment
            model_name: Name of model to use (e.g. 'claude-3-sonnet', 'o1-preview', etc)
        """
        self.experiment_desc = experiment_desc
        
        if model_name is None:
            model_name = "claude-3-5-sonnet-20240620"
        
        # Initialize appropriate model service based on model name
        if model_name in AnthropicService.AVAILABLE_MODELS:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")
            self.model_service = AnthropicService(api_key=api_key, model=model_name)
        elif model_name in OpenAIService.AVAILABLE_MODELS:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            self.model_service = OpenAIService(api_key=api_key, model=model_name)
        else:
            # Default to local model service
            self.model_service = LocalModelService(model_name)
            
        self.secondary_service = SecondaryEvaluationService(self.model_service)

    @classmethod
    async def create(cls, experiment_desc: str, model_name: str) -> 'SecondaryEvalExperiment':
        """Create a new experiment instance after checking if description exists.
        
        Args:
            experiment_desc: Description of the experiment
            model_name: Name of model to use
            
        Returns:
            New SecondaryEvalExperiment instance
            
        Raises:
            ValueError: If experiment with description already exists
        """
        # Check if experiment already exists
        async with async_session() as session:
            query = select(CotTrieEvalExperiment).where(
                CotTrieEvalExperiment.experiment_desc == experiment_desc
            )
            result = await session.execute(query)
            existing = result.scalar_one_or_none()
            
            if existing:
                raise ValueError(
                    f"Experiment with description '{experiment_desc}' already exists"
                )
        
        return cls(experiment_desc, model_name)

    async def fetch_tries(self, problem_ids: List[int]) -> List[Dict[str, Any]]:
        """Fetch tries for given problem IDs."""
        async with async_session() as session:
            query = select(CotTrie, GSM8K).join(
                GSM8K,
                CotTrie.problem_id == GSM8K.id
            ).where(GSM8K.id.in_(problem_ids))
            
            result = await session.execute(query)
            tries = result.unique().all()
            
            return [{
                'id': trie.id,
                'problem_id': trie.problem_id,
                'model': trie.model,
                'question': gsm8k.question,
                'answer': gsm8k.answer,
                'trie': trie.trie
            } for trie, gsm8k in tries]

    async def run_experiment(self, test_cases: List[Tuple[str, int, bool]]) -> Dict:
        """Run the experiment and return results."""
        experiment = None
        try:
            async with async_session() as session:
                # Create experiment record
                experiment = CotTrieEvalExperiment(
                    experiment_desc=self.experiment_desc
                )
                session.add(experiment)
                await session.commit()

                # Fetch and process tries
                problem_ids = [pid for _, pid, _ in test_cases]
                tries = await self.fetch_tries(problem_ids)

                # Filter tries to only those matching test cases
                test_case_pairs = {(model, pid) for model, pid, _ in test_cases}
                tries = [
                    trie for trie in tries 
                    if (trie['model'], trie['problem_id']) in test_case_pairs
                ]

                # Add node IDs to tries
                for trie in tries:
                    trie['trie'] = add_node_ids_to_trie(trie['trie'])

                # Track results
                correct_classifications = 0
                total_cases = len(test_cases)
                
                for trie_data in tqdm(tries, desc="Processing tries"):
                    try:
                        # Get secondary evaluations
                        trie_obj, node_evaluations, cot_paths_with_evaluations = await self.secondary_service.evaluate_trie(
                            trie_data['trie'],
                            trie_data['question'],
                            trie_data['answer']
                        )
                        
                        # Create experiment record
                        record = CotTrieEvalExperimentRecord(
                            experiment_id=experiment.id,
                            problem_id=trie_data['problem_id'],
                            cot_trie_id=trie_data['id'],
                            trie_evaled=trie_obj.serialize()
                        )
                        session.add(record)
                        await session.commit()
                        
                        # Create CotPath records
                        for path, path_evaluations in cot_paths_with_evaluations:
                            # For the path specific nodes, we substitute the secondary evaluation
                            # along that path.
                            for i, path_eval in enumerate(path_evaluations):
                                path.nodes[i].content.secondary_eval = path_eval

                            path_record = CotPathModel.from_cot_path(
                                path,
                                experiment_record_id=record.id,
                                unfaithfulness_condition=trie_obj.unfaithfulness_condition
                            )
                            session.add(path_record)
                        
                        # Check if classification matches ground truth
                        trie = CotTrieDS(trie_data['trie'])
                        is_unfaithful = trie.has_unfaithful_correct_path()
                        ground_truth = next(
                            unfaithful for model, pid, unfaithful in test_cases 
                            if pid == trie_data['problem_id'] and model == trie_data['model']
                        )
                        
                        if is_unfaithful == ground_truth:
                            correct_classifications += 1

                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        import pdb; pdb.set_trace()
                        print(f"Error processing trie {trie_data['id']}: {str(e)}")
                        continue
                
                # Calculate and store results
                accuracy = correct_classifications / total_cases if total_cases > 0 else 0
                results = {
                    'accuracy': accuracy,
                    'correct_classifications': correct_classifications,
                    'total_cases': total_cases
                }
                
                experiment.results = results
                await session.commit()
                
                return results

        except Exception as e:
            if experiment:
                async with async_session() as session:
                    await session.delete(experiment)
                    await session.commit()
            raise e
            
    @classmethod
    async def examine_experiment(cls, experiment_desc: str) -> Dict:
        """Examine results of an existing experiment.
        
        Args:
            experiment_desc: Description of experiment to examine
            
        Returns:
            Dictionary containing experiment results and classifications
        """
        async with async_session() as session:
            # Find experiment by description
            query = select(CotTrieEvalExperiment).where(
                CotTrieEvalExperiment.experiment_desc == experiment_desc
            )
            result = await session.execute(query)
            experiment = result.scalar_one_or_none()

            if not experiment:
                raise ValueError(f"No experiment found with description: {experiment_desc}")

            # Get all records for this experiment
            query = select(CotTrieEvalExperimentRecord, CotTrie, GSM8K).join(
                CotTrie,
                CotTrieEvalExperimentRecord.cot_trie_id == CotTrie.id
            ).join(
                GSM8K,
                CotTrie.problem_id == GSM8K.id
            ).where(
                CotTrieEvalExperimentRecord.experiment_id == experiment.id
            )
            result = await session.execute(query)
            records = result.all()

            # Process records into classifications
            classifications = []
            processed_tries = []
            
            for record, trie, gsm8k in records:
                try:
                    # Create trie from evaluated data
                    trie_ds = CotTrieDS(record.trie_evaled)
                    is_unfaithful = trie_ds.has_unfaithful_correct_path()
                    
                    classifications.append((
                        trie.model,
                        trie.problem_id,
                        is_unfaithful
                    ))
                    processed_tries.append(trie_ds)
                except Exception as e:
                    print(f"Error processing record for trie {trie.id}: {str(e)}")
                    continue

            return experiment.results, classifications, processed_tries

async def examine_experiment_results(experiment_desc: str, test_cases: List[Tuple[str, int, bool]]):
    """Print results of an experiment."""
    try:
        results, classifications, tries = await SecondaryEvalExperiment.examine_experiment(experiment_desc)
        
        # Calculate accuracy from classifications
        correct_count = 0
        total_count = 0
        current_model = None
        
        print("\nClassifications:")
        print("===============")
        for model, problem_id, is_unfaithful in sorted(classifications, key=lambda x: (x[0], x[1])):
            # Check if classification matches ground truth
            ground_truth = next((unfaithful for m, pid, unfaithful in test_cases if m == model and pid == problem_id), None)
            matches_truth = ground_truth == is_unfaithful if ground_truth is not None else None
            
            if matches_truth is not None:
                total_count += 1
                if matches_truth:
                    correct_count += 1
            
            # Add * if classification doesn't match ground truth
            mismatch_marker = "*" if matches_truth is False else " "
            
            # Print model header if it changed
            if current_model != model:
                print(f"\n--- {model} ---")
                current_model = model
                
            print(
                f"Problem {problem_id:4d}: "
                f"{mismatch_marker}{'Unfaithful' if is_unfaithful else 'Not unfaithful'}"
            )

        # Print accuracy stats
        print("\nExperiment Results:")
        print("==================")
        accuracy = correct_count / total_count if total_count > 0 else 0
        print(f"Accuracy: {accuracy:.2%}")
        print(f"Correct Classifications: {correct_count}")
        print(f"Total Cases: {total_count}")

    except ValueError as e:
        print(f"Error: {str(e)}")
        return 1
async def main():
    parser = argparse.ArgumentParser(description='Run or examine secondary evaluation experiments')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Run experiment command
    run_parser = subparsers.add_parser('run', help='Run a new experiment')
    run_parser.add_argument('--desc', type=str, required=True,
                           help='Description of the experiment')
    run_parser.add_argument('--model', type=str, required=False,
                           help='Model to use for secondary evaluation (e.g. claude-3-5-sonnet-20241022, o1-preview)')
    
    # Examine experiment command
    examine_parser = subparsers.add_parser('examine', help='Examine existing experiment')
    examine_parser.add_argument('--desc', type=str, required=True,
                              help='Description of experiment to examine')
    
    args = parser.parse_args()

    # Load test cases from CSV
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'unfaithful_secondary_evals.csv')
    test_cases = load_test_cases(csv_path)

    if args.command == 'run':
       
        try:
            # Create experiment with validation and specified model
            experiment = await SecondaryEvalExperiment.create(args.desc, args.model)
            results = await experiment.run_experiment(test_cases)
            
            # Print results
            await examine_experiment_results(args.desc, test_cases)
            
        except ValueError as e:
            print(f"Error: {str(e)}")
            return 1
        
    elif args.command == 'examine':
        await examine_experiment_results(args.desc, test_cases)
    else:
        parser.print_help()

if __name__ == "__main__":
    asyncio.run(main())