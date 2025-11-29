import random
import streamlit as st
import pandas as pd


# ---------- Data loading ----------

@st.cache_data
def load_questions(path: str = r"C:\Users\r.marks\OneDrive - Financial Reporting Council\Desktop\tx\better quiz.csv") -> pd.DataFrame:
    """
    Load the simple quiz CSV with columns: Topic, Question, Answer.
    Normalise into: id, topic, question, answer.
    """
    df = pd.read_csv(path, encoding="utf-8-sig")

    # Normalise column names
    rename_map = {}
    for col in df.columns:
        if col.lower() == "topic":
            rename_map[col] = "topic"
        elif col.lower() == "question":
            rename_map[col] = "question"
        elif col.lower() == "answer":
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

# ---------- Sidebar: filters ----------

st.sidebar.title("Filters")

topics = sorted([t for t in df_all["topic"].unique() if t])
topic_choice = st.sidebar.multiselect(
    "Topics",
    options=topics,
    default=topics,  # default: all topics
)

if topic_choice:
    df_pool = df_all[df_all["topic"].isin(topic_choice)]
else:
    df_pool = df_all.copy()

if df_pool.empty:
    st.error("No questions match the current filters.")
    st.stop()

st.sidebar.markdown("---")
st.sidebar.write("This mode always gives you two options: correct vs one distractor.")


# ---------- Question generation ----------

def make_question(df_pool: pd.DataFrame, df_all: pd.DataFrame):
    """
    Pick one random question and build options:
    - correct = its own Answer
    - distractor = one other Answer, ideally same topic, else from whole bank
    """
    row = df_pool.sample(1).iloc[0]

    qid = row["id"]
    topic = row["topic"]
    question_text = row["question"]
    correct = row["answer"]

    # Try to get distractors from same topic
    same_topic = df_all[(df_all["topic"] == topic) & (df_all["id"] != qid)]
    candidates = same_topic["answer"].dropna().unique().tolist()
    candidates = [c for c in candidates if c.strip() and c.strip() != correct.strip()]

    # If none, fall back to any other answer in the bank
    if not candidates:
        other = df_all[df_all["id"] != qid]["answer"].dropna().unique().tolist()
        candidates = [c for c in other if c.strip() and c.strip() != correct.strip()]

    if not candidates:
        # Degenerate case: only one question in entire bank
        distractor = "No distractor available"
    else:
        distractor = random.choice(candidates)

    options = [correct, distractor]
    random.shuffle(options)

    return {
        "id": qid,
        "topic": topic,
        "question": question_text,
        "correct": correct,
        "options": options,
    }


# ---------- Session state ----------

ss = st.session_state

if "current_q" not in ss:
    ss.current_q = None
if "score" not in ss:
    ss.score = 0
if "questions_seen" not in ss:
    ss.questions_seen = 0
if "last_checked" not in ss:
    ss.last_checked = False
if "last_correct" not in ss:
    ss.last_correct = None
if "last_checked_qid" not in ss:
    ss.last_checked_qid = None


def new_question():
    ss.current_q = make_question(df_pool, df_all)
    ss.last_checked = False
    ss.last_correct = None
    ss.last_checked_qid = None
    if "answer_radio" in ss:
        del ss["answer_radio"]


def record_answer(selected_option: str):
    """Mark the current question as answered, update score once per question."""
    q = ss.current_q
    if q is None:
        return

    already_marked = ss.last_checked and (ss.last_checked_qid == q["id"])
    is_corr = selected_option == q["correct"]

    ss.last_checked = True
    ss.last_correct = is_corr
    ss.last_checked_qid = q["id"]

    if not already_marked:
        ss.questions_seen += 1
        if is_corr:
            ss.score += 1


if ss.current_q is None:
    new_question()


# ---------- Main UI ----------

st.title("TX Drill App – Either/Or Practice")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Questions seen", ss.questions_seen)
with col2:
    st.metric("Correct", ss.score)
with col3:
    acc = f"{(ss.score / ss.questions_seen * 100):.1f}%" if ss.questions_seen > 0 else "—"
    st.metric("Accuracy", acc)

st.markdown("---")

q = ss.current_q

with st.form("qa_form"):
    # Meta: topic line
    if q["topic"]:
        st.markdown(f"**{q['topic']}**")

    st.markdown(f"### {q['question']}")

    selected = st.radio(
        "Select your answer:",
        q["options"],
        key="answer_radio",
    )

    col_a, col_b = st.columns(2)
    with col_a:
        check = st.form_submit_button("Check answer")
    with col_b:
        next_q = st.form_submit_button("Next question")

# Handle form actions
if check:
    record_answer(selected)

if next_q:
    new_question()

# ---------- Feedback ----------

if ss.last_checked and ss.current_q["id"] == ss.last_checked_qid:
    if ss.last_correct:
        st.success("✅ Correct!")
    else:
        st.error("❌ Incorrect.")

    with st.expander("Show correct answer text", expanded=True):
        st.markdown(f"**Correct answer:**  \n{q['correct']}")

    with st.expander("See both options you were choosing between"):
        for opt in q["options"]:
            if opt == q["correct"]:
                st.markdown(f"- **✅ {opt}**")
            else:
                st.markdown(f"- {opt}")
else:
    st.info("Pick one of the two options and click **Check answer**.")
