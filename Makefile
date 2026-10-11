.PHONY: up down logs ps restart reset

# Start everything (db, ollama, migrations, api, mcp, frontend) and stream logs. Ctrl-C stops all.
up:
	@test -f .env || cp .env.example .env
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

restart:
	docker compose restart api mcp frontend

# Deletes all volumes: database AND downloaded Ollama models.
reset:
	docker compose down -v
