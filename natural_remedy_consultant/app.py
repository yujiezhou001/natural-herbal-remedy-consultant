from pathlib import Path

import pandas as pd
import streamlit as st

from assistant import create_assistant
from db_save import save_conversation
from db_feedback import save_feedback
from judge import evaluate_relevance

st.set_page_config(page_title="Natural Remedy Consultant", page_icon="🌿")

RELEVANCE_ICON = {"RELEVANT": "🟢", "PARTLY_RELEVANT": "🟡", "NON_RELEVANT": "🔴"}
IMAGES_CSV = Path(__file__).resolve().parents[1] / "data" / "herb_images.csv"
MAX_HERB_IMAGES = 3


@st.cache_resource
def get_assistant():
    return create_assistant()


@st.cache_data
def get_herb_images():
    if not IMAGES_CSV.exists():
        return {}
    df = pd.read_csv(IMAGES_CSV)
    return {
        row.herb_id: {
            "name": row.herb_name_en,
            "image_url": row.image_url,
            "page_url": row.page_url,
        }
        for row in df.itertuples(index=False)
    }


def herbs_for_results(search_results):
    """Pick up to MAX_HERB_IMAGES distinct pictured herbs, in retrieval order."""
    herb_images = get_herb_images()
    herbs = []
    seen = set()
    for doc in search_results:
        herb_id = doc["herb_id"]
        if herb_id in seen or herb_id not in herb_images:
            continue
        seen.add(herb_id)
        herbs.append(herb_images[herb_id])
        if len(herbs) == MAX_HERB_IMAGES:
            break
    return herbs


assistant = get_assistant()

st.title("🌿 Natural Remedy Consultant")
st.caption(
    "Educational information about natural herbal remedies — "
    "not a substitute for professional medical advice."
)

if "messages" not in st.session_state:
    st.session_state.messages = []


def metrics_caption(m):
    return (
        f"⏱ {m['response_time']:.2f}s · "
        f"🔢 {m['prompt_tokens']} prompt + {m['completion_tokens']} completion tokens · "
        f"💲 ${m['cost']:.4f}"
    )


def record_feedback(index):
    """Runs before the rerun when a thumb is clicked."""
    choice = st.session_state[f"fb_{index}"]  # 0 = 👎, 1 = 👍, None = untouched
    if choice is None:
        return
    score = 1 if choice == 1 else -1
    msg = st.session_state.messages[index]
    msg["feedback"] = score
    save_feedback(msg["conversation_id"], "user", score=score)


# replay the conversation (metrics + judge verdict + user thumbs, per answer)
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

        if msg["role"] == "assistant":
            if msg.get("herbs"):
                cols = st.columns(MAX_HERB_IMAGES)
                for col, herb in zip(cols, msg["herbs"]):
                    col.image(herb["image_url"], width=140)
                    col.caption(f"[{herb['name']}]({herb['page_url']})")

            st.caption(metrics_caption(msg["metrics"]))

            ev = msg.get("evaluation")
            if ev:
                dot = RELEVANCE_ICON.get(ev["relevance"], "⚪")
                with st.expander(f"{dot} Judge: {ev['relevance']}"):
                    st.write(ev["explanation"])

            if msg.get("feedback") is None:
                st.feedback("thumbs", key=f"fb_{i}",
                            on_change=record_feedback, args=(i,))
            else:
                st.caption("👍 Thanks for the feedback!" if msg["feedback"] == 1
                           else "👎 Thanks — noted, we'll use it to improve.")

# input pinned to the bottom
if question := st.chat_input("Ask about a herb or a health concern…"):
    st.session_state.messages.append({"role": "user", "content": question})

    with st.spinner("Consulting the knowledge base…"):
        answer = assistant.rag(question)

    record = assistant.last_call
    conversation_id = save_conversation(record, question)

    relevance, explanation = evaluate_relevance(
        question, answer, client=assistant.llm_client
    )
    save_feedback(conversation_id, "judge",
                  relevance=relevance, explanation=explanation)

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "herbs": herbs_for_results(assistant.last_results),
        "conversation_id": conversation_id,
        "metrics": {
            "response_time": record.response_time,
            "prompt_tokens": record.prompt_tokens,
            "completion_tokens": record.completion_tokens,
            "cost": record.cost,
        },
        "evaluation": {"relevance": relevance, "explanation": explanation},
        "feedback": None,
    })
    st.rerun()
