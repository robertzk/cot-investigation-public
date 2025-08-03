# Chain of Thought Investigation

This project investigates chain-of-thought reasoning in language models by building and analyzing trees of reasoning steps.

## Features

- Support for multiple datasets with question-answer pairs
- Chain-of-thought tree building and analysis
- Secondary evaluation of reasoning steps
- API endpoints for accessing and analyzing the data

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/database"
export ANTHROPIC_API_KEY="your-api-key"
```

3. Run database migrations:
```bash
cd backend
alembic upgrade head
```

## Working with Datasets

### Supported Datasets

The system now supports any dataset that has at least a "question" and "answer" field. Each dataset is identified by a unique name (e.g., "gsm8k", "math23k", etc.).

### Importing a New Dataset

To import a new dataset:

1. Prepare your dataset as a CSV file with at least these columns:
   - `question`: The problem/question text
   - `answer`: The correct answer

2. Use the import script:
```bash
python backend/scripts/import_dataset.py dataset_name path/to/dataset.csv
```

Example:
```bash
python backend/scripts/import_dataset.py math23k data/math23k.csv
```

### API Endpoints

- `GET /api/dataset/{dataset_name}/responses`: Get problems from a specific dataset
- `GET /api/cot-tries/incorrect`: Get chain-of-thought tries with incorrect steps

## Development

### Database Schema

The main tables are:

- `problems`: Stores all dataset problems
  - `id`: Primary key
  - `dataset_name`: Name of the dataset (e.g., "gsm8k")
  - `question`: The problem text
  - `answer`: The correct answer

- `cot_tries`: Stores chain-of-thought reasoning trees
  - References problems through `problem_id`
  - Includes the reasoning tree structure and evaluations

### Adding Support for a New Dataset

1. Prepare your dataset CSV file with required columns
2. Import using the `import_dataset.py` script
3. The system will automatically handle the dataset in the same way as others

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

[Add your license information here]



```