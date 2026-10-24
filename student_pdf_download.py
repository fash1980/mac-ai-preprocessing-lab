"""Student-facing one-time download of approved MAC Tutorial 4 review PDFs.

Deploy separately from the teacher's review app. Requirements: streamlit, supabase.
Configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in Streamlit Secrets.
Run one_time_download_setup.sql once in the Supabase SQL Editor first.
"""

import re

import streamlit as st
from supabase import create_client


st.set_page_config(page_title="MAC Tutorial 4 | Reviewed PDF", page_icon="📄", layout="centered")

st.markdown("""
<style>
.block-container {max-width: 720px; padding-top: 2.2rem;}
h1 {color: #173b50; font-size: 2rem !important; letter-spacing: -.6px;}
div[data-testid="stAlert"] {border-radius: 12px;}
div[data-testid="stForm"] {border-radius: 16px; border-color: #dae8eb; padding: 1.25rem;}
div.stButton > button[kind="primary"], div.stDownloadButton > button[kind="primary"] {
  background: #116b75; border-color: #116b75; border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

# Inline illustration: no extra image file or image package required.
st.html("""
<div style="border-radius:20px;background:linear-gradient(120deg,#e9f5f4,#f3f8fc);padding:12px 20px;margin-bottom:14px">
<svg role="img" aria-label="Illustration of a reviewed report with checkmarks and a download arrow"
     viewBox="0 0 600 175" style="width:100%;height:auto;display:block" xmlns="http://www.w3.org/2000/svg">
  <circle cx="465" cy="81" r="74" fill="#d6eeea"/>
  <circle cx="136" cy="43" r="10" fill="#b6dfdc"/>
  <circle cx="194" cy="132" r="7" fill="#e1c978"/>
  <path d="M37 137h255" stroke="#bfdcde" stroke-width="3" stroke-linecap="round"/>
  <path d="M355 145l4-108c1-8 6-12 14-12h123l31 31v89c0 8-5 13-13 13H369c-9 0-14-4-14-13Z"
        fill="#ffffff" stroke="#a8ced0" stroke-width="3"/>
  <path d="M496 25v33h31" fill="#e8f3f2" stroke="#a8ced0" stroke-width="3"/>
  <path d="M387 74l8 8 14-16M387 106l8 8 14-16" stroke="#16948d" stroke-width="5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M426 75h57M426 107h45" stroke="#a9bdc8" stroke-width="5" stroke-linecap="round"/>
  <circle cx="524" cy="131" r="31" fill="#116b75"/>
  <path d="M524 112v28m-11-11 11 11 11-11M511 148h26" stroke="white" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
  <rect x="54" y="36" width="245" height="16" rx="8" fill="#6caaa8" opacity=".7"/>
  <rect x="54" y="67" width="207" height="12" rx="6" fill="#9abfc1" opacity=".65"/>
  <rect x="54" y="90" width="178" height="12" rx="6" fill="#9abfc1" opacity=".45"/>
</svg>
</div>
""")

st.title("MAC Tutorial 4 – Your Feedback Report")
st.write("Your tutorial has been reviewed. Enter your Student ID below to get your feedback report.")
st.info("You can download your report only once, so please save the PDF on your device.", icon="ℹ️")

BUCKET = "mac-tutorial-reviewed-pdfs"


@st.cache_resource
def database(url, key):
    return create_client(url, key)


try:
    db = database(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_SERVICE_ROLE_KEY"])
except (KeyError, FileNotFoundError):
    st.error("Portal is not configured yet. Please contact your lecturer.")
    st.stop()


def find_latest_submission(student_id):
    # Query only the latest submission; do not accidentally return an older review.
    response = (
        db.table("tutorial_submissions")
        .select("id,student_id,submitted_at")
        .ilike("student_id", student_id)
        .order("submitted_at", desc=True)
        .order("id", desc=True)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def read_approved_pdf(submission_id):
    filename = f"MAC_Tutorial4_Review_{submission_id}.pdf"
    folder = f"submissions/{submission_id}"
    # Before reserving the one-time claim, verify that the approved file exists.
    files = db.storage.from_(BUCKET).list(folder)
    if not any(item.get("name") == filename for item in files):
        return None, None, None
    storage_path = f"{folder}/{filename}"
    contents = db.storage.from_(BUCKET).download(storage_path)
    if not isinstance(contents, bytes):
        contents = bytes(contents)
    if not contents.startswith(b"%PDF-"):
        raise ValueError("The stored file is not a valid PDF.")
    return filename, storage_path, contents


def already_claimed(student_id):
    result = (
        db.table("tutorial_pdf_download_claims")
        .select("student_id")
        .eq("student_id", student_id)
        .limit(1)
        .execute()
    )
    return bool(result.data)


if "pdf_ready" not in st.session_state:
    st.session_state.pdf_ready = False

with st.form("download_request"):
    entered_id = st.text_input("Student ID", placeholder="e.g. your university Student ID", max_chars=40).strip()
    requested = st.form_submit_button("Get My Feedback Report", type="primary", use_container_width=True)

if requested:
    st.session_state.pdf_ready = False
    st.session_state.pop("pdf_bytes", None)
    student_id = entered_id.upper()

    if not re.fullmatch(r"[A-Z0-9_-]{3,40}", student_id):
        st.warning("Please check your Student ID and try again.")
    else:
        try:
            # Same canonical ID must be used for lookup and one-time claim.
            if already_claimed(student_id):
                st.warning("This report has already been downloaded. If you had a problem saving it, please contact your lecturer.")
            else:
                record = find_latest_submission(student_id)
                if not record:
                    st.warning("We couldn't find a report for this Student ID. Please check the ID you entered.")
                else:
                    name, path, data = read_approved_pdf(record["id"])
                    if data is None:
                        st.info("Your feedback report isn't ready yet. Please check back later.")
                    else:
                        claimed = db.rpc("claim_tutorial_pdf_download", {
                            "p_student_id": student_id,
                            "p_submission_id": str(record["id"]),
                            "p_storage_path": path,
                        }).execute().data
                        if claimed is True:
                            st.session_state.pdf_ready = True
                            st.session_state.pdf_bytes = data
                            st.session_state.pdf_filename = name
                            st.success("Your report is ready! Click the download button below and save the file.")
                        else:
                            st.warning("This report has already been accessed or is no longer available. Please contact your lecturer.")
        except Exception:
            st.error("Something went wrong. Please try again later or contact your lecturer.")

if st.session_state.pdf_ready:
    st.download_button(
        "⬇ Download My Feedback Report",
        data=st.session_state.pdf_bytes,
        file_name=st.session_state.pdf_filename,
        mime="application/pdf",
        type="primary",
        use_container_width=True,
        on_click=lambda: st.session_state.update(pdf_ready=False),
    )

st.divider()
st.caption("Having trouble? Contact your lecturer and include your Student ID.")
