# SimpleMas Agent Dockerfile
# Generated with simplemas deploy generate-dockerfile

FROM python:3.10-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AGENT_PORT=8000

# Run the application
CMD ["python", "-m simple_mas.cli run hello_agent"]
