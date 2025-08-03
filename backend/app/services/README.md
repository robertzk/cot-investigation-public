# Services

## Secondary eval experiment service

Example of how to run the service (from backend dir):

```
PYTHONPATH=. poetry run python -m experiments.secondary_eval_experiment run --desc "Initial unfaithfulness detection test v5"  
PYTHONPATH=. poetry run python -m experiments.secondary_eval_experiment examine --desc "Initial unfaithfulness detection test v5"  
```