import random
import streamlit as st
import pandas as pd


# ---------- Data loading ----------

@st.cache_data
def load_questions(path: str = "questions.csv") -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    # Clean up any NaNs in text columns
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

# Sheet filter
sheets = sorted(df_all["sheet"].unique())
sheet_choice = st.sidebar.selectbox(
    "Sheet",
    options=["All"] + sheets,
    index=0,
)

# Topic filter, dependent on sheet
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

# How many answer options per question?
num_options = st.sidebar.slider(
    "Number of answer options",
    min_value=2,
    max_value=6,
    value=4,
    step=1,
)

st.sidebar.markdown("---")
st.sidebar.write("Tip: narrow the sheet/topic to get better distractors.")

# Apply topic filter
if topic_choice:
    df_pool = df_sheet[df_sheet["topic"].isin(topic_choice)]
else:
    df_pool = df_sheet.copy()

if df_pool.empty:
    st.error("No questions match the current filters.")
    st.stop()

# ---------- Helpers to generate questions ----------

def make_question(df_pool: pd.DataFrame, df_all: pd.DataFrame, num_options: int):
    """Pick one random question and a list of answer options (correct + distractors)."""
    row = df_pool.sample(1).iloc[0]

    correct_answer = row["answer"]
    qid = row["id"]
    sheet = row["sheet"]
    topic = row["topic"]
    subject = row["subject"]
    question_text = row["question"]

    # Try to draw distractors from the same sheet/topic
    same_topic = df_pool[df_pool["id"] != qid]
    candidates = same_topic["answer"].dropna().unique().tolist()
    candidates = [c for c in candidates if c.strip() and c.strip() != correct_answer.strip()]

    # If not enough, top up from anywhere in the bank
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


# ---------- Session state initialisation ----------

if "current_q" not in st.session_state:
    st.session_state.current_q = None
if "selected_option" not in st.session_state:
    st.session_state.selected_option = None
if "answered" not in st.session_state:
    st.session_state.answered = False
if "is_correct" not in st.session_state:
    st.session_state.is_correct = None
if "score" not in st.session_state:
    st.session_state.score = 0
if "questions_seen" not in st.session_state:
    st.session_state.questions_seen = 0


def new_question():
    st.session_state.current_q = make_question(df_pool, df_all, num_options)
    st.session_state.selected_option = None
    st.session_state.answered = False
    st.session_state.is_correct = None


def submit_answer():
    if st.session_state.selected_option is None:
        return
    st.session_state.answered = True
    is_corr = st.session_state.selected_option == st.session_state.current_q["correct"]
    st.session_state.is_correct = is_corr
    st.session_state.questions_seen += 1
    if is_corr:
        st.session_state.score += 1


# Ensure we always have a question
if st.session_state.current_q is None:
    new_question()

# ---------- Main UI ----------

st.title("TX Drill App – Rote Question Practice")

# Stats
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Questions seen", st.session_state.questions_seen)
with col2:
    st.metric("Correct", st.session_state.score)
with col3:
    acc = (
        f"{(st.session_state.score / st.session_state.questions_seen * 100):.1f}%"
        if st.session_state.questions_seen > 0
        else "—"
    )
    st.metric("Accuracy", acc)

st.markdown("---")

q = st.session_state.current_q

# Meta info
meta_line = f"**[{q['sheet']}]**"
if q["topic"]:
    meta_line += f" – {q['topic']}"
if q["subject"]:
    meta_line += f" – {q['subject']}"
st.markdown(meta_line)

st.markdown(f"### {q['question']}")

# Options as radio buttons
st.session_state.selected_option = st.radio(
    "Select your answer:",
    q["options"],
    index=0 if st.session_state.selected_option is None else q["options"].index(
        st.session_state.selected_option
    ),
    key="answer_radio",
)

# Buttons
col_a, col_b = st.columns([1, 1])
with col_a:
    if st.button("Check answer"):
        submit_answer()
with col_b:
    if st.button("Next question"):
        new_question()

# Feedback / solution
if st.session_state.answered:
    if st.session_state.is_correct:
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
