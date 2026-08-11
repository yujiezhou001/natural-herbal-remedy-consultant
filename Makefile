.PHONY: run ingest

run:
	uv run python natural_remedy_consultant/assistant.py

ingest:
	cd natural_remedy_consultant && uv run python auto_data_ingestion.py

chat:
	uv run streamlit run app.py

network:
	docker network create monitoring

postgres: network
	docker run -it \
		--name course-assistant-pg \
		--network monitoring \
		-e POSTGRES_USER=user \
		-e POSTGRES_PASSWORD=password \
		-e POSTGRES_DB=course_assistant \
		-p 5432:5432 \
		-v pgdata:/var/lib/postgresql/data \
		postgres:17

query:
	uv run python db_query.py

dashboard:
	lsof -ti :8502 | xargs -r kill -9 || true
	uv run streamlit run dashboard.py --server.port 8502

grafana:
	docker run -d \
		--name grafana \
		--network monitoring \
		-p 3000:3000 \
		-v grafana_data:/var/lib/grafana \
		grafana/grafana