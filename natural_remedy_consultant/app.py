import time
from pathlib import Path

import pandas as pd
import streamlit as st

from assistant import create_assistant
from db_init import init_db
from db_save import save_conversation
from db_feedback import save_feedback
from judge import evaluate_relevance

st.set_page_config(
    page_title="Natural Remedy Consultant",
    page_icon="🌿",
    initial_sidebar_state="expanded",
)

JUDGE_BADGE = {
    "RELEVANT": ("Relevant", "judge-relevant"),
    "PARTLY_RELEVANT": ("Partly relevant", "judge-partly"),
    "NON_RELEVANT": ("Not relevant", "judge-non"),
}
AVATARS = {"user": "👤", "assistant": "🌿"}
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
IMAGES_CSV = DATA_DIR / "herb_images.csv"
KB_CSV = DATA_DIR / "knowledge_base.csv"
MAX_HERB_IMAGES = 3

APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600;700&display=swap');

.hero { text-align: center; padding: 0.8rem 0 0.2rem; }
.hero .leaf { font-size: 2rem; }
.hero h1 {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 2.7rem; font-weight: 700; color: #2E5941;
    margin: 0.1rem 0 0.3rem; letter-spacing: 0.02em;
}
.hero p { color: #6B705C; font-size: 1.02rem; margin: 0 auto; max-width: 34rem; }
.hero-rule { width: 130px; height: 2px; background: #C9B77E; margin: 0.9rem auto 0.4rem; }

[data-testid="stSidebar"] h3 {
    font-family: 'Cormorant Garamond', Georgia, serif;
    color: #2E5941; letter-spacing: 0.02em;
}

[data-testid="stChatMessage"] {
    background: #FFFDF6;
    border: 1px solid #E6DEC9;
    border-radius: 14px;
    padding: 1rem 1.1rem;
    margin-bottom: 0.65rem;
    box-shadow: 0 1px 3px rgba(62, 78, 59, 0.07);
}

[data-testid="stImage"] img {
    border-radius: 10px;
    border: 1px solid #E0D7BF;
}

[data-testid="stCaptionContainer"] { color: #7C8064; }

.judge-badge {
    display: inline-block;
    padding: 0.18rem 0.75rem;
    border-radius: 999px;
    font-size: 0.72rem;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    font-weight: 600;
    border: 1px solid;
}
.judge-relevant { color: #2E5941; border-color: #A9C4AC; background: #E7EFE3; }
.judge-partly { color: #8A6D1D; border-color: #D8C384; background: #F6EDD3; }
.judge-non { color: #8C3B2E; border-color: #D89E8D; background: #F7E2D9; }

.stat-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-size: 0.85rem;
    color: #3E4637;
    padding: 0.22rem 0;
    border-bottom: 1px dashed #E0D7BF;
}
.stat-row:last-of-type { border-bottom: none; }
.stat-row .label { color: #7C8064; }

[data-testid="stFeedback"] > div { display: flex; gap: 1.1rem; }
</style>
"""


@st.cache_resource
def get_assistant():
    # create the tables if they don't exist yet, retrying while
    # the database container finishes starting up
    for attempt in range(5):
        try:
            init_db()
            break
        except Exception:
            if attempt == 4:
                raise
            time.sleep(2)

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


@st.cache_data
def kb_stats():
    df = pd.read_csv(KB_CSV)
    return df["herb_id"].nunique(), len(df)


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
        herbs.append({
            **herb_images[herb_id],
            "name_zh": doc.get("herb_name_zh", ""),
        })
        if len(herbs) == MAX_HERB_IMAGES:
            break
    return herbs


def record_feedback(index):
    """Runs before the rerun when a thumb is clicked."""
    choice = st.session_state[f"fb_{index}"]  # 0 = 👎, 1 = 👍, None = untouched
    if choice is None:
        return
    score = 1 if choice == 1 else -1
    msg = st.session_state.messages[index]
    msg["feedback"] = score
    save_feedback(msg["conversation_id"], "user", score=score)


assistant = get_assistant()

if "messages" not in st.session_state:
    st.session_state.messages = []

st.markdown(APP_CSS, unsafe_allow_html=True)
st.markdown(
    """
    <div class="hero">
      <div class="leaf">🌿</div>
      <h1>Natural Remedy Consultant</h1>
      <p>Traditional Chinese herbal wisdom meets modern evidence —
      grounded answers, safety first.</p>
      <div class="hero-rule"></div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### About")
    st.write(
        "Ask questions about herbs and everyday health concerns. Answers are "
        "grounded in a curated knowledge base covering traditional use, modern "
        "evidence, preparation, and safety."
    )
    n_herbs, n_records = kb_stats()
    st.markdown(f"**{n_herbs} herbs · {n_records} records**")

    st.divider()

    st.markdown("### This session")
    answered = [m for m in st.session_state.messages if m["role"] == "assistant"]
    session_cost = sum(m["metrics"]["cost"] for m in answered)
    col1, col2 = st.columns(2)
    col1.metric("Questions", len(answered))
    col2.metric("Cost", f"${session_cost:.3f}")

    st.divider()

    st.markdown("### Latest answer")
    if answered:
        last = answered[-1]
        m = last["metrics"]
        st.markdown(
            f"""
            <div class="stat-row"><span class="label">Response time</span><span>{m['response_time']:.2f}s</span></div>
            <div class="stat-row"><span class="label">Prompt tokens</span><span>{m['prompt_tokens']:,}</span></div>
            <div class="stat-row"><span class="label">Completion tokens</span><span>{m['completion_tokens']:,}</span></div>
            <div class="stat-row"><span class="label">Cost</span><span>${m['cost']:.4f}</span></div>
            """,
            unsafe_allow_html=True,
        )

        ev = last["evaluation"]
        label, css_class = JUDGE_BADGE.get(
            ev["relevance"], (ev["relevance"], "judge-partly")
        )
        st.markdown(
            f'<div style="margin-top:0.7rem"><span class="judge-badge {css_class}">{label}</span></div>',
            unsafe_allow_html=True,
        )
        st.caption(ev["explanation"])
    else:
        st.caption(
            "Response time, token usage, cost, and an automatic quality "
            "verdict for the most recent answer appear here."
        )

    st.divider()

    st.caption(
        "Educational information only — not a substitute for professional "
        "medical advice, diagnosis, or treatment."
    )
    st.caption("Herb photos from [Wikipedia](https://en.wikipedia.org).")

# replay the conversation (metrics + judge verdict + user thumbs, per answer)
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"], avatar=AVATARS[msg["role"]]):
        st.write(msg["content"])

        if msg["role"] == "assistant":
            if msg.get("herbs"):
                cols = st.columns(MAX_HERB_IMAGES)
                for col, herb in zip(cols, msg["herbs"]):
                    col.image(herb["image_url"], width=140)
                    label = f"[{herb['name']}]({herb['page_url']})"
                    if herb.get("name_zh"):
                        label += f" · {herb['name_zh']}"
                    col.caption(label)

            if msg.get("feedback") is None:
                st.feedback("thumbs", key=f"fb_{i}",
                            on_change=record_feedback, args=(i,))
            else:
                st.caption("👍 Thanks for the feedback!" if msg["feedback"] == 1
                           else "👎 Thanks — noted, we'll use it to improve.")

# input pinned to the bottom
if question := st.chat_input("Ask about a herb or a health concern…"):
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
    ]
    st.session_state.messages.append({"role": "user", "content": question})

    # render the new exchange immediately so the waiting state
    # looks like the finished conversation
    with st.chat_message("user", avatar=AVATARS["user"]):
        st.write(question)

    with st.chat_message("assistant", avatar=AVATARS["assistant"]):
        with st.spinner("Consulting the knowledge base…"):
            answer = assistant.rag(question, history=history)

        with st.spinner("Reviewing the answer…"):
            record = assistant.last_call
            conversation_id = save_conversation(record, question)

            relevance, explanation = evaluate_relevance(
                assistant.last_search_query or question,
                answer,
                client=assistant.llm_client,
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
