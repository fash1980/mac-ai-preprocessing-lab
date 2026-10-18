"""MAC Week 4 Colab practical submission: one PDF per task.

Upload this as app2_testing.py alongside app2.py in the existing GitHub repository.
Requires: typing_input/index.html; reportlab, Pillow, supabase in requirements.txt.
Streamlit Cloud secrets: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
Test Supabase resources: practical_submissions_testing table and
private practical-evidence-testing bucket (created by testing_setup.sql).
"""
import json
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
import hashlib
import logging
import time
import uuid

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageOps, UnidentifiedImageError
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as PDFImage, KeepTogether

st.set_page_config(page_title="MAC | Week 4 Practical TESTING", page_icon="📎", layout="wide")

COMPONENT_DIR = Path(__file__).parent / "typing_input"
typing_input = (
    components.declare_component("practical_testing_pdf_typing_v1", path=str(COMPONENT_DIR))
    if (COMPONENT_DIR / "index.html").exists() else None
)

@st.cache_resource
def make_client(url, key):
    from supabase import create_client
    return create_client(url, key)


def get_db():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
        if url and key:
            return make_client(url, key)
    except (KeyError, FileNotFoundError):
        return None
    except Exception:
        logging.exception("Database configuration error")
    return None


def temporary_error(error):
    import httpx
    if isinstance(error, (httpx.TransportError, httpx.TimeoutException)):
        return True
    description = str(error).lower()
    return any(token in description for token in (
        "temporarily unavailable", "timed out", "timeout", "429", "502", "503", "504", "connection reset"
    ))


def retry_operation(operation, label, maximum=3):
    for attempt in range(maximum):
        try:
            return operation()
        except Exception as exc:
            logging.warning("%s: attempt %s failed: %s", label, attempt + 1, type(exc).__name__)
            if attempt == maximum - 1 or not temporary_error(exc):
                raise
            time.sleep(min(2 ** attempt, 3))


def read_screenshot(upload):
    if upload.size > 4 * 1024 * 1024:
        raise ValueError(f"{upload.name}: source exceeds 4 MB")
    try:
        raw = upload.getvalue()
        with Image.open(BytesIO(raw)) as src:
            src.verify()
        with Image.open(BytesIO(raw)) as src:
            img = ImageOps.exif_transpose(src).convert("RGB")
            img.thumbnail((1450, 1800), Image.Resampling.LANCZOS)
            output = BytesIO()
            img.save(output, format="JPEG", quality=72, optimize=True)
            return output.getvalue(), img.width, img.height
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError(f"{upload.name}: not a readable PNG/JPG") from exc


@st.cache_data(show_spinner=False)
def build_pdf(student_id, student_name, task, token, analysis, screenshot_items):
    """Create a locally downloadable PDF; no Supabase call is involved."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=17 * mm, bottomMargin=18 * mm,
    )
    style = getSampleStyleSheet()
    style.add(ParagraphStyle(name="LabTitle", parent=style["Heading1"], fontSize=16, leading=20, textColor=colors.HexColor("#173454")))
    style.add(ParagraphStyle(name="LabText", parent=style["Normal"], fontSize=9.5, leading=14, spaceAfter=7))
    story = [Paragraph("MAC — Week 4 Practical Evidence", style["LabTitle"]), Spacer(1, 7)]
    fields = [("Student ID", student_id), ("Student name", student_name), ("Practical task", task), ("Colab run token", token)]
    for label, value in fields:
        story.append(Paragraph(f"<b>{label}:</b> {escape(str(value))}", style["LabText"]))
    story += [Spacer(1, 7), Paragraph("Evidence-based Analysis", style["Heading2"])]
    for para in analysis.splitlines():
        if para.strip():
            story.append(Paragraph(escape(para.strip()), style["LabText"]))
    story += [Spacer(1, 6), Paragraph("Colab Screenshots", style["Heading2"])]
    max_width = A4[0] - 36 * mm
    max_height = A4[1] - 90 * mm
    for ix, (filename, jpeg_bytes, width, height) in enumerate(screenshot_items, 1):
        factor = min(max_width / width, max_height / height, 1)
        pic = PDFImage(BytesIO(jpeg_bytes), width=width * factor, height=height * factor)
        story.append(KeepTogether([
            Paragraph(f"Evidence {ix}: {escape(filename)}", style["LabText"]),
            pic, Spacer(1, 10),
        ]))
    doc.build(story)
    return buffer.getvalue()


def pdf_in_bucket(storage, location):
    directory, filename = location.rsplit("/", 1)
    result = retry_operation(lambda: storage.list(directory), "list PDF evidence", maximum=2)
    return any(x.get("name") == filename for x in result)


def ensure_pdf_uploaded(storage, location, pdf_bytes):
    # A lost response does not necessarily mean the upload failed.
    if pdf_in_bucket(storage, location):
        return
    for attempt in range(3):
        try:
            storage.upload(location, pdf_bytes, {"content-type": "application/pdf", "upsert": "false"})
            return
        except Exception as exc:
            try:
                if pdf_in_bucket(storage, location):
                    return
            except Exception:
                logging.warning("Cannot verify PDF after unsuccessful upload")
            if not temporary_error(exc) or attempt == 2:
                raise
            time.sleep(min(2 ** attempt, 3))




def ensure_notebook_uploaded(storage, location, notebook_bytes):
    """Upload a notebook under the same submission ID; check existence on retry."""
    if pdf_in_bucket(storage, location):
        return
    for attempt in range(3):
        try:
            storage.upload(
                location, notebook_bytes,
                {"content-type": "application/json", "upsert": "false"},
            )
            return
        except Exception as exc:
            # An interrupted connection may still have stored the notebook.
            try:
                if pdf_in_bucket(storage, location):
                    return
            except Exception:
                logging.warning("Cannot verify notebook after failed upload")
            if not temporary_error(exc) or attempt == 2:
                raise
            time.sleep(min(2 ** attempt, 3))

st.title("Week 4 Practical — Colab Evidence Submission (TESTING)")
st.caption("TESTING APPLICATION — Keep the existing student submission link unchanged.")
st.markdown("""
### Lab Instructions
- Complete both Google Colab notebooks: **Task 1 (Numerical)** and **Task 2 (Multimodal)**.
- Enter your own **Student ID** and run all required experiments.
- Capture 2–5 screenshots of **your own Colab outputs** and enter your **Run Token**.
- Type **100–220 words** of result-based analysis. Copy-paste is restricted in the analysis field.
- Submit **Task 1 and Task 2 separately**.
- **Upload the completed `.ipynb` notebook for the selected task** (mandatory, in addition to screenshots).
- **Download your PDF evidence report** as a backup; a download is not an online submission.
- Only a **Saved successfully** receipt confirms the online submission. If the server fails, submit the PDF through **myTIMeS** as instructed by your tutor.
""")

db = get_db()
if db is None:
    st.warning("Supabase is not configured; PDF download works, but online submission is unavailable.")
if typing_input is None:
    st.error("Missing typing_input/index.html. The manual-typing component must be restored.")

left, right = st.columns(2)
with left:
    student_id = st.text_input("Student ID", max_chars=40)
    student_name = st.text_input("Student name", max_chars=100)
with right:
    task = st.selectbox("Practical task", ["Task 1 — Numerical", "Task 2 — Multimodal"])
    token = st.text_input("Colab run token (from notebook E0)", max_chars=32)

st.markdown("#### Evidence Screenshots")
st.caption("Choose 2–5 PNG/JPG screenshots, no more than 4 MB each. Do not include personal patient data.")
shots = st.file_uploader("Screenshot evidence", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
st.markdown("#### Completed Colab Notebook — Required")
notebook_upload = st.file_uploader(
    "Upload your completed .ipynb file for the selected task",
    type=["ipynb"],
    accept_multiple_files=False,
    key=f"testing_notebook_{task.split(' ')[1]}",
)
st.caption("Save your completed notebook from Colab: File → Download → Download .ipynb. Maximum size 8 MB. Submit Task 1 and Task 2 separately.")

st.markdown("#### Type your evidence-based analysis (100–220 words)")
answer_key = "analysis_task1" if task.startswith("Task 1") else "analysis_task2"
if typing_input is not None:
    typed = typing_input(
        value=st.session_state.get(answer_key, ""),
        default=st.session_state.get(answer_key, ""),
        key=f"pdf_component_{answer_key}",
    )
    if typed is not None:
        st.session_state[answer_key] = str(typed)
analysis = st.session_state.get(answer_key, "")
words = len(analysis.split())
st.caption(f"Recorded word count: {words} (required: 100–220). Wait one second after typing.")
checklist = st.checkbox("I have executed the notebook and the screenshots are from my own Colab session.")

problems = []
if len(student_id.strip()) < 4:
    problems.append("Enter your Student ID (minimum 4 characters).")
if not student_name.strip():
    problems.append("Enter your name.")
if len(token.strip()) < 8:
    problems.append("Enter the Run Token shown by Colab.")
if not 2 <= len(shots or []) <= 5:
    problems.append("Upload 2–5 screenshots.")
if not 100 <= words <= 220:
    problems.append(f"Analysis must be 100–220 words (currently {words}).")
if not checklist:
    problems.append("Confirm the declaration.")

notebook_bytes = None
notebook_name = None
if notebook_upload is None:
    problems.append("Upload your completed .ipynb notebook for this task.")
elif notebook_upload.size > 8 * 1024 * 1024:
    problems.append("Completed notebook is larger than 8 MB. Clear unnecessary large outputs, save, and retry.")
else:
    try:
        notebook_bytes = notebook_upload.getvalue()
        notebook_data = json.loads(notebook_bytes.decode("utf-8"))
        cells = notebook_data.get("cells", []) if isinstance(notebook_data, dict) else []
        if (not isinstance(notebook_data, dict)
                or notebook_data.get("nbformat") != 4
                or not isinstance(cells, list)
                or not any(isinstance(c, dict) and c.get("cell_type") == "code" for c in cells)):
            problems.append("This file is not a valid Colab/Jupyter notebook with code cells.")
        else:
            notebook_name = notebook_upload.name
    except (UnicodeDecodeError, ValueError, AttributeError, TypeError):
        problems.append("The uploaded .ipynb file cannot be read as a valid Jupyter notebook.")

pdf_bytes = None
if not problems:
    try:
        with st.spinner("Preparing your PDF report..."):
            images = tuple((shot.name, *read_screenshot(shot)) for shot in shots)
            pdf_bytes = build_pdf(student_id.strip(), student_name.strip(), task, token.strip().upper(), analysis.strip(), images)
        st.success(f"PDF evidence report prepared ({len(pdf_bytes) / 1024 / 1024:.2f} MB).")
    except Exception:
        logging.exception("PDF generation failed")
        st.error("Could not generate the PDF. Check that each screenshot is a valid image and try again.")
else:
    st.caption("Complete all fields to enable PDF download and online submission.")

fingerprint = hashlib.sha256(pdf_bytes + notebook_bytes).hexdigest() if (pdf_bytes and notebook_bytes) else None
if "pdf_pending" not in st.session_state:
    st.session_state.pdf_pending = None
if "pdf_completed" not in st.session_state:
    st.session_state.pdf_completed = None

if pdf_bytes:
    st.download_button(
        "Download your evidence PDF (backup)",
        data=pdf_bytes,
        file_name=f"Week4_{task.split(' ')[1]}_{student_id.strip()}.pdf",
        mime="application/pdf",
        type="secondary",
    )

clicked = st.button("Submit practical evidence", type="primary", disabled=(db is None or pdf_bytes is None or notebook_bytes is None or bool(problems)))
if clicked and pdf_bytes is not None and notebook_bytes is not None and db is not None:
    completed = st.session_state.pdf_completed
    if completed and completed["fingerprint"] == fingerprint:
        st.success(f"Already submitted. Receipt: {completed['receipt']}")
    else:
        pending = st.session_state.pdf_pending
        if pending is None or pending["fingerprint"] != fingerprint:
            pending = {"fingerprint": fingerprint, "id": uuid.uuid4().hex}
            st.session_state.pdf_pending = pending
        sid = pending["id"]
        pdf_path = f"{sid}/week4_evidence.pdf"
        notebook_path = f"{sid}/completed_colab_notebook.ipynb"
        record = {
            "submission_id": sid,
            "student_id": student_id.strip(),
            "student_name": student_name.strip(),
            "task_name": task,
            "run_token": token.strip().upper(),
            "analysis": analysis.strip(),
            "evidence_paths": [],
            "status": "pending",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            with st.spinner("Saving submission and uploading one PDF..."):
                # First save a traceable pending record. On retry, reuse the same ID.
                retry_operation(
                    lambda: db.table("practical_submissions_testing").upsert(record, on_conflict="submission_id").execute(),
                    "save pending submission",
                )
                storage = db.storage.from_("practical-evidence-testing")
                ensure_pdf_uploaded(storage, pdf_path, pdf_bytes)
                ensure_notebook_uploaded(storage, notebook_path, notebook_bytes)
                result = retry_operation(
                    lambda: db.table("practical_submissions_testing").update({
                        "status": "completed", "evidence_paths": [pdf_path, notebook_path],
                    }).eq("submission_id", sid).execute(),
                    "confirm submission",
                )
                if not getattr(result, "data", None):
                    raise RuntimeError("Completion update was not confirmed by database")
            receipt = sid[:12].upper()
            st.session_state.pdf_completed = {"fingerprint": fingerprint, "receipt": receipt}
            st.session_state.pdf_pending = None
            st.success(f"Saved successfully. Receipt: {receipt}. Keep this receipt.")
        except Exception:
            logging.exception("Single-PDF practical submission failed")
            st.error(
                "Online submission is NOT confirmed. Your PDF backup remains available above. "
                "You may retry Submit with the same browser tab, or submit the downloaded PDF to myTIMeS."
            )

st.caption("TESTING BUILD. PDF and notebook are stored separately in the private practical-evidence bucket. Notebook validity does not prove independent authorship.")
