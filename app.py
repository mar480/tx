import random
import streamlit as st
import pandas as pd


# ---------- Data loading ----------

@st.cache_data
def load_questions(path: str = "questions.csv") -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    for col in ["sheet", "topic", "subject", "question", "answer"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()
    return df


df_all = load_questions()

if df_all.empty:
    st.error("No questions found in questions.csv")
    st.stop()

# ---------- Sidebar: filters & settings ----------

st.sidebar.title("Filters")

sheets = sorted(df_all["sheet"].unique())
sheet_choice = st.sidebar.selectbox(
    "Sheet",
    options=["All"] + sheets,
    index=0,
)

if sheet_choice == "All":
    df_sheet = df_all.copy()
else:
    df_sheet = df_all[df_all["sheet"] == sheet_choice]

topics = sorted([t for t in df_sheet["topic"].unique() if t])
topic_choice = st.sidebar.multiselect(
    "Topics",
    options=topics,
    default=topics,
)

num_options = st.sidebar.slider(
    "Number of answer options",
    min_value=2,
    max_value=6,
    value=4,
    step=1,
)

st.sidebar.markdown("---")
st.sidebar.write("Tip: narrow the sheet/topic to get better distractors.")

if topic_choice:
    df_pool = df_sheet[df_sheet["topic"].isin(topic_choice)]
else:
    df_pool = df_sheet.copy()

if df_pool.empty:
    st.error("No questions match the current filters.")
    st.stop()

# ---------- Question generation ----------

def make_question(df_pool: pd.DataFrame, df_all: pd.DataFrame, num_options: int):
    """Pick one random question and a list of answer options (correct + distractors)."""
    row = df_pool.sample(1).iloc[0]

    correct_answer = row["answer"]
    qid = row["id"]
    sheet = row["sheet"]
    topic = row["topic"]
    subject = row["subject"]
    question_text = row["question"]

    # Distractors: start from same sheet/topic pool
    same_topic = df_pool[df_pool["id"] != qid]
    candidates = same_topic["answer"].dropna().unique().tolist()
    candidates = [c for c in candidates if c.strip() and c.strip() != correct_answer.strip()]

    # Top up from whole bank if needed
    if len(candidates) < num_options - 1:
        extra_pool = df_all[df_all["id"] != qid]["answer"].dropna().unique().tolist()
        extra_pool = [c for c in extra_pool if c.strip() and c.strip() != correct_answer.strip()]
        random.shuffle(extra_pool)
        needed = (num_options - 1) - len(candidates)
        candidates.extend(extra_pool[:needed])

    random.shuffle(candidates)
    distractors = candidates[: max(0, num_options - 1)]

    options = [correct_answer] + distractors
    random.shuffle(options)

    return {
        "id": qid,
        "sheet": sheet,
        "topic": topic,
        "subject": subject,
        "question": question_text,
        "correct": correct_answer,
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
    ss.current_q = make_question(df_pool, df_all, num_options)
    ss.last_checked = False
    ss.last_correct = None
    ss.last_checked_qid = None
    # Reset the radio selection
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

st.title("TX Drill App – Rote Question Practice")

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

# Wrap the interaction in a form so radio clicks alone don't trigger logic
with st.form("qa_form"):
    # Meta
    meta_line = f"**[{q['sheet']}]**"
    if q["topic"]:
        meta_line += f" – {q['topic']}"
    if q["subject"]:
        meta_line += f" – {q['subject']}"
    st.markdown(meta_line)

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
    # After new_question() we don't show old feedback, so early-exit draw:


# ---------- Feedback ----------

if ss.last_checked and ss.current_q["id"] == ss.last_checked_qid:
    if ss.last_correct:
        st.success("✅ Correct!")
    else:
        st.error("❌ Incorrect.")

    with st.expander("Show correct answer text", expanded=True):
        st.markdown(f"**Correct answer:**  \n{q['correct']}")

    with st.expander("See all options you were choosing between"):
        for opt in q["options"]:
            if opt == q["correct"]:
                st.markdown(f"- **✅ {opt}**")
            else:
                st.markdown(f"- {opt}")
else:
    st.info("Select an option and click **Check answer** to see if you're right.")
