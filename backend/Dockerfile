# Instructions for building and running MIDAS backend inside Docker

# Use Python 3.12 as base image
FROM python:3.12-slim
# Set working folder inside the container
WORKDIR /app
# Copy Python package list into the container
COPY requirements.txt .
# Install required Python packages
RUN pip install --no-cache-dir -r requirements.txt
# Copy backend files into the container
COPY . .
# Start FastAPI server on port 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
