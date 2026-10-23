import json
import streamlit as st
from supabase import create_client

st.set_page_config(
    page_title="MAC Tutorial 4 | Submission Viewer",
    page_icon="📋",
    layout="wide",
)

st.title("Machine Learning Preprocessing Tutorial Week 4")
st.subheader("Student Submission Viewer")
st.caption("Read-only view of saved submissions from Supabase.")

@st.cache_resource
def get_supabase_client(url: str, key: str):
    return create_client(url, key)

def get_credentials():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
        if url and key:
            return url, key
    except (KeyError, FileNotFoundError):
        pass
    return None, None

def fetch_submissions():
    url, key = get_credentials()
    if not url or not key:
        st.error(
            "Supabase credentials are missing. Add SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY to Streamlit secrets."
        )
        st.stop()

    db = get_supabase_client(url, key)
    # Read in batches so the viewer is not limited to the first 1,000 rows.
    records = []
    page_size = 500
    start = 0

    while True:
        response = (
            db.table("tutorial_submissions")
            .select("id, student_id, student_name, answers, submitted_at")
            .order("id", desc=False)
            .range(start, start + page_size - 1)
            .execute()
        )
        batch = response.data or []
        records.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size

    return records

try:
    records = fetch_submissions()
except Exception as exc:
    st.error("Could not retrieve submissions from Supabase.")
    st.caption(f"Technical detail: {exc}")
    st.stop()

if not records:
    st.info("No submissions were found in tutorial_submissions.")
    st.stop()

# Optional search/filter controls.
left, middle, right = st.columns([2, 2, 1])
with left:
    search = st.text_input("Search student name or ID", placeholder="Enter name or ID")
with middle:
    ids = sorted({str(r.get("student_id") or "") for r in records})
    selected_id = st.selectbox("Filter by student ID", ["All students"] + ids)
with right:
    st.metric("Total submissions", len(records))

filtered = records
if search.strip():
    term = search.strip().casefold()
    filtered = [
        r for r in filtered
        if term in str(r.get("student_name") or "").casefold()
        or term in str(r.get("student_id") or "").casefold()
    ]
if selected_id != "All students":
    filtered = [r for r in filtered if str(r.get("student_id") or "") == selected_id]

if not filtered:
    st.warning("No submissions match these filters.")
    st.stop()

# Use session state to navigate one submission at a time.
if "submission_index" not in st.session_state:
    st.session_state.submission_index = 0
st.session_state.submission_index = min(
    st.session_state.submission_index, len(filtered) - 1
)

def previous_submission():
    st.session_state.submission_index = max(0, st.session_state.submission_index - 1)

def next_submission():
    st.session_state.submission_index = min(
        len(filtered) - 1, st.session_state.submission_index + 1
    )

nav1, nav2, nav3 = st.columns([1, 2, 1])
with nav1:
    st.button(
        "← Previous",
        on_click=previous_submission,
        disabled=st.session_state.submission_index == 0,
        use_container_width=True,
    )
with nav2:
    st.markdown(
        f"<div style='text-align:center;padding-top:8px'><b>Submission "
        f"{st.session_state.submission_index + 1} of {len(filtered)}</b></div>",
        unsafe_allow_html=True,
    )
with nav3:
    st.button(
        "Next →",
        on_click=next_submission,
        disabled=st.session_state.submission_index >= len(filtered) - 1,
        use_container_width=True,
    )

record = filtered[st.session_state.submission_index]

st.divider()
student_col, id_col, submission_col = st.columns([2, 1, 1])
with student_col:
    st.markdown("**Student name**")
    st.write(record.get("student_name") or "Not provided")
with id_col:
    st.markdown("**Student ID**")
    st.write(record.get("student_id") or "Not provided")
with submission_col:
    st.markdown("**Submission record**")
    st.write(f"ID: {record.get('id', 'N/A')}")
    if record.get("submitted_at"):
        st.caption(f"Submitted: {record['submitted_at']}")

answers = record.get("answers") or {}
if isinstance(answers, str):
    try:
        answers = json.loads(answers)
    except json.JSONDecodeError:
        st.error("The answers field is not valid JSON.")
        st.code(answers)
        st.stop()

if not isinstance(answers, dict):
    st.warning("The saved answers are not in the expected JSON object format.")
    st.json(answers)
    st.stop()

total_questions = 0
answered_questions = 0

for scenario_title, questions in answers.items():
    if not isinstance(questions, dict):
        with st.expander(str(scenario_title), expanded=True):
            st.write(questions)
        continue

    total_questions += len(questions)
    answered_questions += sum(
        1 for answer in questions.values()
        if answer is not None and str(answer).strip()
    )

st.progress(
    answered_questions / total_questions if total_questions else 0,
    text=f"Answered: {answered_questions} / {total_questions} questions",
)

for scenario_title, questions in answers.items():
    with st.expander(str(scenario_title), expanded=True):
        if isinstance(questions, dict):
            for question, answer in questions.items():
                st.markdown(f"**{question}**")
                if answer is None or not str(answer).strip():
                    st.info("No answer submitted.")
                else:
                    st.markdown(str(answer))
                st.divider()
        else:
            st.write(questions)

st.caption("This page is read-only. It does not edit or delete student submissions.")
