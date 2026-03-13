FROM python:3.12-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY dashboard.py .
COPY static static/

# Expose port
EXPOSE 3000

# Run the dashboard
CMD ["python", "dashboard.py"]
