FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY alembic.ini ./
COPY backend ./backend

RUN uv pip install --system .

EXPOSE 8000

CMD ["sh", "-c", "alembic -c alembic.ini upgrade head && fastapi run backend/src/openpdm/main.py --host 0.0.0.0 --port 8000"]
