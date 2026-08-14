import os
from datetime import datetime

import psycopg

DB_TIMEZONE = datetime.now().astimezone().tzinfo


def get_db_connection():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "natural_remedy_assistant"),
        user=os.getenv("POSTGRES_USER", "user"),
        password=os.getenv("POSTGRES_PASSWORD", "password"),
    )


def init_db(drop=False):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if drop:
                cur.execute("DROP TABLE IF EXISTS feedback")
                cur.execute("DROP TABLE IF EXISTS conversations")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id SERIAL PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    model TEXT NOT NULL,
                    instructions TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    response_time FLOAT NOT NULL,
                    cost FLOAT NOT NULL,
                    timestamp TIMESTAMP WITH TIME ZONE NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id SERIAL PRIMARY KEY,
                    conversation_id INTEGER REFERENCES conversations(id),
                    source TEXT NOT NULL,
                    relevance TEXT,
                    explanation TEXT,
                    score INTEGER,
                    timestamp TIMESTAMP WITH TIME ZONE NOT NULL
                )
            """)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    print(f"Using timezone: {DB_TIMEZONE}")
    init_db()
    print("Database initialized")
