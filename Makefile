.PHONY: run ingest chat network postgres db-init query dashboard grafana

run:
	uv run python natural_remedy_consultant/assistant.py

ingest:
	cd natural_remedy_consultant && uv run python auto_data_ingestion.py

chat:
	uv run streamlit run natural_remedy_consultant/app.py

network:
	docker network create monitoring 2>/dev/null || true

postgres: network
	docker start -a natural-remedy-assistant-pg 2>/dev/null || docker run -it \
		--name natural-remedy-assistant-pg \
		--network monitoring \
		-e POSTGRES_USER=user \
		-e POSTGRES_PASSWORD=password \
		-e POSTGRES_DB=natural_remedy_assistant \
		-p 5432:5432 \
		-v pgdata:/var/lib/postgresql/data \
		postgres:17

db-init:
	cd natural_remedy_consultant && uv run python db_init.py

query:
	cd natural_remedy_consultant && uv run python db_query.py

dashboard:
	lsof -ti :8502 | xargs -r kill -9 || true
	uv run streamlit run natural_remedy_consultant/dashboard.py --server.port 8502

grafana: network
	docker start grafana 2>/dev/null || docker run -d \
		--name grafana \
		--network monitoring \
		-p 3000:3000 \
		-v grafana_data:/var/lib/grafana \
		grafana/grafana
