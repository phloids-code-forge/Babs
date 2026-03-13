FROM python:3.12-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy supervisor code
COPY supervisor.py .
COPY tools.py .
COPY tool_searxng.py .

# Run the supervisor
CMD ["python", "supervisor.py"]
