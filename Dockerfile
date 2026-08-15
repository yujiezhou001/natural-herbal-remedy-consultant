FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

# install dependencies from the lockfile (exact pinned versions)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY natural_remedy_consultant/ natural_remedy_consultant/
COPY data/ data/
COPY .streamlit/ .streamlit/

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8501

# the embedding model is downloaded on first startup if not present
CMD ["streamlit", "run", "natural_remedy_consultant/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
