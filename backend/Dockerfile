FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including build essentials
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
ENV PATH="/root/.local/bin:$PATH"
RUN curl -sSL https://install.python-poetry.org | python3 -

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Configure poetry and install dependencies
# Add --no-dev if you don't need development dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main
#RUN poetry config virtualenvs.create false \
#    && poetry install --no-interaction --no-ansi \
#    --only main \
#    || poetry install --no-interaction --no-ansi \
#    --only main \
#    --no-cache

COPY . .

# RUN poetry run alembic upgrade head

CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"] 