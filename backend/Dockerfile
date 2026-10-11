FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Source is bind-mounted by docker-compose for live reload; this copy makes the image usable standalone.
COPY alembic.ini .
COPY backend ./backend
