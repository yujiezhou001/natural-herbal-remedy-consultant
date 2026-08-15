"""Set up Grafana monitoring for the Natural Remedy Consultant.

Creates (or updates) the Postgres datasource and the monitoring dashboard
through the Grafana HTTP API. Idempotent — safe to run repeatedly.

Prerequisites: `make postgres` and `make grafana` are running.

Usage:
    python grafana/init_grafana.py
"""

import os

import requests

GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
GRAFANA_USER = os.getenv("GRAFANA_USER", "admin")
GRAFANA_PASSWORD = os.getenv("GRAFANA_PASSWORD", "admin")

AUTH = (GRAFANA_USER, GRAFANA_PASSWORD)
DATASOURCE_NAME = "RemedyPostgres"
DASHBOARD_UID = "remedy-monitoring"

# How Grafana reaches Postgres from inside docker. Default matches the
# docker-compose service name; the Makefile's standalone containers
# override this with the container name.
PG_HOST = os.getenv("GRAFANA_PG_HOST", "postgres:5432")


def ensure_datasource():
    payload = {
        "name": DATASOURCE_NAME,
        "type": "postgres",
        "access": "proxy",
        "url": PG_HOST,
        "user": "user",
        "jsonData": {
            "database": "natural_remedy_assistant",
            "sslmode": "disable",
            "maxOpenConns": 5,
        },
        "secureJsonData": {"password": "password"},
    }

    response = requests.post(f"{GRAFANA_URL}/api/datasources", auth=AUTH, json=payload)
    if response.status_code == 200:
        uid = response.json()["datasource"]["uid"]
        print(f"datasource created: {DATASOURCE_NAME} ({uid})")
        return uid
    if response.status_code == 409:
        existing = requests.get(
            f"{GRAFANA_URL}/api/datasources/name/{DATASOURCE_NAME}", auth=AUTH
        ).json()
        print(f"datasource already exists: {DATASOURCE_NAME} ({existing['uid']})")
        return existing["uid"]
    raise RuntimeError(f"datasource creation failed: {response.text}")


def sql_target(ds, sql, fmt="time_series"):
    return {
        "refId": "A",
        "datasource": ds,
        "rawQuery": True,
        "rawSql": sql.strip(),
        "format": fmt,
        "editorMode": "code",
    }


def stat_panel(ds, panel_id, title, sql, unit, x, decimals=2, color="green"):
    return {
        "id": panel_id,
        "type": "stat",
        "title": title,
        "gridPos": {"h": 4, "w": 6, "x": x, "y": 0},
        "datasource": ds,
        "targets": [sql_target(ds, sql, "table")],
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "decimals": decimals,
                "color": {"mode": "fixed", "fixedColor": color},
            },
            "overrides": [],
        },
        "options": {"colorMode": "value", "graphMode": "none"},
    }


def timeseries_panel(ds, panel_id, title, sql, unit, x, y, bars=False):
    return {
        "id": panel_id,
        "type": "timeseries",
        "title": title,
        "gridPos": {"h": 8, "w": 12, "x": x, "y": y},
        "datasource": ds,
        "targets": [sql_target(ds, sql)],
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "custom": {
                    "drawStyle": "bars" if bars else "line",
                    "fillOpacity": 35 if bars else 12,
                    "lineWidth": 2,
                    "pointSize": 5,
                    "showPoints": "auto",
                },
            },
            "overrides": [],
        },
        "options": {"legend": {"displayMode": "list", "placement": "bottom"}},
    }


def pie_panel(ds, panel_id, title, sql, x, y, color_by_name=None):
    overrides = []
    for name, color in (color_by_name or {}).items():
        overrides.append({
            "matcher": {"id": "byName", "options": name},
            "properties": [
                {"id": "color", "value": {"mode": "fixed", "fixedColor": color}}
            ],
        })
    return {
        "id": panel_id,
        "type": "piechart",
        "title": title,
        "gridPos": {"h": 8, "w": 12, "x": x, "y": y},
        "datasource": ds,
        "targets": [sql_target(ds, sql, "table")],
        "fieldConfig": {"defaults": {}, "overrides": overrides},
        "options": {
            "pieType": "donut",
            "legend": {"displayMode": "table", "placement": "right",
                       "values": ["value", "percent"]},
            "reduceOptions": {"values": True, "fields": ""},
        },
    }


def build_dashboard(ds_uid):
    ds = {"type": "postgres", "uid": ds_uid}

    panels = [
        stat_panel(ds, 1, "Questions", '''
            SELECT COUNT(*) AS "Questions"
            FROM conversations WHERE $__timeFilter("timestamp")
        ''', "none", x=0, decimals=0),
        stat_panel(ds, 2, "Total cost", '''
            SELECT COALESCE(SUM(cost), 0) AS "Cost"
            FROM conversations WHERE $__timeFilter("timestamp")
        ''', "currencyUSD", x=6, decimals=3, color="yellow"),
        stat_panel(ds, 3, "Avg response time", '''
            SELECT AVG(response_time) AS "Response time"
            FROM conversations WHERE $__timeFilter("timestamp")
        ''', "s", x=12, color="blue"),
        stat_panel(ds, 4, "Judged relevant", '''
            SELECT 100.0 * SUM(CASE WHEN relevance = 'RELEVANT' THEN 1 ELSE 0 END)
                   / NULLIF(COUNT(*), 0) AS "Relevant"
            FROM feedback WHERE source = 'judge' AND $__timeFilter("timestamp")
        ''', "percent", x=18, decimals=1),

        timeseries_panel(ds, 5, "Questions over time", '''
            SELECT $__timeGroup("timestamp", '1h') AS time, COUNT(*) AS questions
            FROM conversations WHERE $__timeFilter("timestamp")
            GROUP BY 1 ORDER BY 1
        ''', "none", x=0, y=4, bars=True),
        timeseries_panel(ds, 6, "Response time", '''
            SELECT $__timeGroup("timestamp", '1h') AS time,
                   AVG(response_time) AS "avg",
                   MAX(response_time) AS "max"
            FROM conversations WHERE $__timeFilter("timestamp")
            GROUP BY 1 ORDER BY 1
        ''', "s", x=12, y=4),

        timeseries_panel(ds, 7, "Cost over time", '''
            SELECT $__timeGroup("timestamp", '1h') AS time, SUM(cost) AS cost
            FROM conversations WHERE $__timeFilter("timestamp")
            GROUP BY 1 ORDER BY 1
        ''', "currencyUSD", x=0, y=12, bars=True),
        timeseries_panel(ds, 8, "Token usage", '''
            SELECT $__timeGroup("timestamp", '1h') AS time,
                   SUM(prompt_tokens) AS "prompt",
                   SUM(completion_tokens) AS "completion"
            FROM conversations WHERE $__timeFilter("timestamp")
            GROUP BY 1 ORDER BY 1
        ''', "none", x=12, y=12),

        pie_panel(ds, 9, "LLM judge verdicts", '''
            SELECT relevance AS metric, COUNT(*) AS value
            FROM feedback
            WHERE source = 'judge' AND $__timeFilter("timestamp")
            GROUP BY relevance
        ''', x=0, y=20, color_by_name={
            "RELEVANT": "green",
            "PARTLY_RELEVANT": "yellow",
            "NON_RELEVANT": "red",
        }),
        pie_panel(ds, 10, "User feedback", '''
            SELECT CASE WHEN score = 1 THEN 'Thumbs up' ELSE 'Thumbs down' END AS metric,
                   COUNT(*) AS value
            FROM feedback
            WHERE source = 'user' AND $__timeFilter("timestamp")
            GROUP BY 1
        ''', x=12, y=20, color_by_name={
            "Thumbs up": "green",
            "Thumbs down": "red",
        }),

        {
            "id": 11,
            "type": "table",
            "title": "Recent conversations",
            "gridPos": {"h": 9, "w": 24, "x": 0, "y": 28},
            "datasource": ds,
            "targets": [sql_target(ds, '''
                SELECT c."timestamp" AS "Time",
                       c.question AS "Question",
                       f.relevance AS "Judge",
                       c.response_time AS "Response (s)",
                       c.cost AS "Cost ($)"
                FROM conversations c
                LEFT JOIN feedback f ON f.conversation_id = c.id AND f.source = 'judge'
                WHERE $__timeFilter(c."timestamp")
                ORDER BY c."timestamp" DESC
                LIMIT 20
            ''', "table")],
            "fieldConfig": {"defaults": {}, "overrides": []},
            "options": {},
        },
    ]

    return {
        "dashboard": {
            "uid": DASHBOARD_UID,
            "title": "Natural Remedy Consultant — Monitoring",
            "timezone": "browser",
            "schemaVersion": 39,
            "refresh": "1m",
            "time": {"from": "now-7d", "to": "now"},
            "panels": panels,
        },
        "overwrite": True,
    }


def main():
    uid = ensure_datasource()

    response = requests.post(
        f"{GRAFANA_URL}/api/dashboards/db", auth=AUTH, json=build_dashboard(uid)
    )
    if response.status_code != 200:
        raise RuntimeError(f"dashboard creation failed: {response.text}")

    print(f"dashboard ready: {GRAFANA_URL}{response.json()['url']}")


if __name__ == "__main__":
    main()
