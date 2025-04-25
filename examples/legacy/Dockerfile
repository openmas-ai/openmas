FROM python:3.10-slim

WORKDIR /app

# Install Poetry
RUN pip install poetry && \
    poetry config virtualenvs.create false

# Copy pyproject.toml and poetry.lock* files
COPY pyproject.toml ./
# If a poetry.lock file exists, copy it too
COPY poetry.lock* ./

# Install dependencies
RUN poetry install --no-dev

# Copy the package
COPY src/ ./src/
COPY examples/ ./examples/

# Set Python path
ENV PYTHONPATH=/app

# Default command (can be overridden)
CMD ["python", "-m", "examples.simple_agent"]
