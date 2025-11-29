import random
import streamlit as st
import pandas as pd


# ---------- Data loading ----------

@st.cache_data
def load_questions(path: str = "better quiz.csv") -> pd.DataFrame:
    """
    Load the simple quiz CSV with columns: Topic, Question, Answer.
    Normalize into: id, topic, question, answer.
    """
    df = pd.read_csv(path, encoding="utf-8-sig")

    # Normalise column names (robust to minor header differences)
    rename_map = {}
    for col in df.columns:
        cl = col.lower().strip()
        if cl == "topic":
            rename_map[col] = "topic"
        elif cl == "question":
            rename_map[col] = "question"
        elif cl == "answer":
            rename_map[col] = "answer"
    df = df.rename(columns=rename_map)

    # Ensure required columns exist
    for col in ["topic", "question", "answer"]:
        if col not in df.columns:
            df[col] = ""

    # Clean text
    for col in ["topic", "question", "answer"]:
        df[col] = df[col].fillna("").astype(str).str.strip()

    # Drop completely empty rows
    df = df[(df["question"] != "") & (df["answer"] != "")].reset_index(drop=True)

    # Auto-generate ids
    df["id"] = [f"Q-{i+1}" for i in range(len(df))]

    return df


df_all = load_questions()

if df_all.empty:
    st.error("No questions found in the CSV file.")
    st.stop()


# ---------- Sidebar: topic filters ----------

st.sidebar.title("Filters")

topics = sorted([t for t in df_all["topic"].unique() if t])
topic_choice = st.sidebar.multiselect(
    "Topics",
    options=topics,
    default=topics,  # default: all topics
)

if topic_choice:
    df_pool = df_all[df_all["topic"].isin(topic_choice)].copy()
else:
    df_pool = df_all.copy()

if df_pool.empty:
    st.error("No questions match the current filters.")
    st.stop()

st.sidebar.markdown("---")
st.sidebar.write("Each question: correct vs one distractor (either/or).")


# ---------- Helper to build a single question ----------

def generate_question(df_pool: pd.DataFrame, df_all: pd.DataFrame) -> dict:
    """
    Pick one random question and build options:
    - correct = its own Answer
    - distractor = one other Answer.

    For residency questions (Topic starts with 'Residency rules'):
      - distractor comes from a *different* residency rules topic.
    For everything else:
      - distractor comes from the same topic (fallback to whole bank if needed).

    Ensures distractor text is not the same as the correct answer (after normalisation).
    """

    def norm(s: str) -> str:
        # Normalise for comparison: strip, collapse whitespace, lowercase
        s = (s or "").strip()
        return " ".join(s.split()).lower()

    row = df_pool.sample(1).iloc[0]

    qid = row["id"]
    topic = row["topic"]
    question_text = row["question"]
    correct = row["answer"]
    correct_norm = norm(correct)

    # --- Choose candidate distractors depending on topic type ---

    topic_str = str(topic)
    topic_lower = topic_str.lower()

    if topic_lower.startswith("residency rules"):
        # All residency rows
        residency_mask = df_all["topic"].str.lower().str.startswith("residency rules")

        # Candidates = other residency topics (different from current topic)
        candidate_rows = df_all[
            residency_mask
            & (df_all["topic"] != topic_str)
            & (df_all["id"] != qid)
        ]
    else:
        # Default behaviour: same topic
        candidate_rows = df_all[
            (df_all["topic"] == topic_str)
            & (df_all["id"] != qid)
        ]

    candidates = candidate_rows["answer"].dropna().unique().tolist()

    # Filter out empties and anything equal to the correct answer (after normalisation)
    filtered = []
    for c in candidates:
        c_str = str(c).strip()
        if not c_str:
            continue
        if norm(c_str) == correct_norm:
            continue
        filtered.append(c_str)

    # --- If none, fall back to anywhere in the bank ---
    if not filtered:
        others = df_all[df_all["id"] != qid]["answer"].dropna().unique().tolist()
        for c in others:
            c_str = str(c).strip()
            if not c_str:
                continue
            if norm(c_str) == correct_norm:
                continue
            filtered.append(c_str)

    # Final choice
    if not filtered:
        distractor = "No distractor available"
    else:
        distractor = random.choice(filtered)

    options = [correct, distractor]
    random.shuffle(options)

    return {
        "id": qid,
        "topic": topic_str,
        "question": question_text,
        "correct": correct,
        "options": options,
    }


# ---------- Minimal session state ----------

ss = st.session_state

if "current_q" not in ss:
    ss.current_q = None  # dict with id/topic/question/correct/options
if "feedback" not in ss:
    ss.feedback = None   # None / "correct" / "incorrect"


def reset_radio():
    # Clear previous selection so the radio doesn't try to reuse an old value
    if "answer_radio" in ss:
        del ss["answer_radio"]


def new_question():
    ss.current_q = generate_question(df_pool, df_all)
    ss.feedback = None
    reset_radio()


# Initialise a question, or refresh it if filters changed so that
# the current question is no longer in the pool.
if ss.current_q is None or ss.current_q["id"] not in df_pool["id"].values:
    new_question()

# ---------- Main UI ----------

st.title("TX Drill – Either/Or Mode")

# Handle "Next question" FIRST, but do NOT stop the script
if st.button("Next question"):
    new_question()

# Now, after any potential update, get the current question to display
q = ss.current_q

st.markdown("---")

# --- Question + answer form ---
with st.form("qa_form"):
    if q["topic"]:
        st.markdown(f"**{q['topic']}**")

    st.markdown(f"### {q['question']}")

    selected = st.radio(
        "Select your answer:",
        q["options"],
        key="answer_radio",
    )

    check = st.form_submit_button("Check answer")

# Handle check after the form is submitted
if check:
    if selected == q["correct"]:
        ss.feedback = "correct"
    else:
        ss.feedback = "incorrect"

# ---------- Feedback ----------

if ss.feedback == "correct":
    st.success("✅ Correct!")
elif ss.feedback == "incorrect":
    st.error("❌ Incorrect.")
    with st.expander("See the correct answer"):
        st.markdown(f"**Correct answer:**  \n{q['correct']}")
else:
    st.info("Pick one of the two options and click **Check answer**.")
