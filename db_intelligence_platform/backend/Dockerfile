FROM python:3.12-slim

WORKDIR /app

# Install uv for fast Python package management
RUN pip install uv

# Copy dependencies
COPY pyproject.toml uv.lock ./

# Install dependencies (ignoring virtualenv since we are in docker)
RUN uv pip install --system -r pyproject.toml

# Copy application source
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
