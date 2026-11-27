FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default DB path points to the persistent volume mount (/data_vol/murmurations.db)
ENV DB_PATH=/data_vol/murmurations.db

EXPOSE 8080

# On container boot, ensure the SQLite schema & seed data exist on the persistent volume, then start Uvicorn
CMD ["sh", "-c", "python -c 'from pathlib import Path; import os; p=Path(os.getenv(\"DB_PATH\", \"/data_vol/murmurations.db\")); p.parent.mkdir(parents=True, exist_ok=True)' && python backend/init_db.py && python backend/seed_db.py && uvicorn backend.app:app --host 0.0.0.0 --port 8080"]