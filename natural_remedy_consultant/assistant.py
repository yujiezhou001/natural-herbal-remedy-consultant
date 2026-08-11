import sys

from dotenv import load_dotenv
from openai import OpenAI

from ingest import build_index, load_data
from metrics import RAGWithMetrics


def create_assistant():
    load_dotenv()

    documents = load_data()
    index = build_index(documents)

    return RAGWithMetrics(
        index=index,
        llm_client=OpenAI(),
    )


if __name__ == "__main__":
    assistant = create_assistant()

    query = "What natural remedies may help with losing weight?"

    if len(sys.argv) > 1:
        query = sys.argv[1]

    answer = assistant.rag(query)

    print(answer)