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
.block-container {max-width: 650px; padding-top: 3rem;}
h1 {color: #163c53; font-size: 2rem !important;}
div[data-testid="stAlert"] {border-radius: 12px;}
</style>
""", unsafe_allow_html=True)
st.title("📄 Your Reviewed Tutorial")
st.write("MAC Tutorial Week 4 — Download your teacher-reviewed PDF")
st.caption("Each Student ID may claim its PDF once. Keep the downloaded file safe.")

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
    entered_id = st.text_input("Student ID", placeholder="Enter your Student ID", max_chars=40).strip()
    requested = st.form_submit_button("Find My Reviewed PDF", type="primary", use_container_width=True)

if requested:
    st.session_state.pdf_ready = False
    st.session_state.pop("pdf_bytes", None)
    student_id = entered_id.upper()

    if not re.fullmatch(r"[A-Z0-9_-]{3,40}", student_id):
        st.warning("Please enter a valid Student ID.")
    else:
        try:
            # Same canonical ID must be used for lookup and one-time claim.
            if already_claimed(student_id):
                st.warning("You have already downloaded your PDF. Please contact your lecturer if you need help.")
            else:
                record = find_latest_submission(student_id)
                if not record:
                    st.warning("No matching approved PDF is available for this Student ID.")
                else:
                    name, path, data = read_approved_pdf(record["id"])
                    if data is None:
                        st.info("Your reviewed PDF is not available yet. Please check again later.")
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
                            st.success("PDF ready. Please download and save it now; this is your only access session.")
                        else:
                            st.warning("You have already downloaded your PDF, or this review is no longer available.")
        except Exception:
            st.error("Unable to process the request right now. Please contact your lecturer.")

if st.session_state.pdf_ready:
    st.download_button(
        "⬇ Download My Reviewed PDF",
        data=st.session_state.pdf_bytes,
        file_name=st.session_state.pdf_filename,
        mime="application/pdf",
        type="primary",
        use_container_width=True,
        on_click=lambda: st.session_state.update(pdf_ready=False),
    )

st.divider()
st.caption("For download problems, please contact your lecturer with your Student ID. Do not share your PDF.")
