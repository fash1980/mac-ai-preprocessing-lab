"""Computer Networks Lab 4 — durable per-question Supabase saves.
Run: streamlit run app3.py
Needs: lab4_questions.json, typed_answer/index.html, optional topology PNG files.
Setup: execute supabase_setup.sql, create private Storage bucket lab4-evidence,
       and configure .streamlit/secrets.toml (see secrets.example.toml).
"""
from __future__ import annotations

import hashlib
import logging
import hmac
import re
import secrets
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import streamlit as st
from PIL import Image as PILImage, ImageOps, UnidentifiedImageError
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer
from supabase import create_client
from streamlit.components.v1 import declare_component

ROOT = Path(__file__).resolve().parent
ANSWER_WIDGET = declare_component("lab4_secure_typed_answer", path=str(ROOT / "typed_answer"))
logger = logging.getLogger("lab4")


def log_database_error(operation: str, exc: Exception) -> None:
    """Log a useful error without printing any configured credential."""
    detail = str(exc)
    for sensitive in (globals().get("SERVICE_KEY", ""), globals().get("URL", "")):
        if sensitive:
            detail = detail.replace(sensitive, "[REDACTED]")
    # Avoid logging arbitrary response data or embedded tokens verbatim.
    detail = re.sub(r"(?:eyJ[A-Za-z0-9_-]+\.){2}[A-Za-z0-9_-]+", "[REDACTED_JWT]", detail)
    detail = re.sub(r"sb_(?:secret|publishable)_[A-Za-z0-9_-]+", "[REDACTED_KEY]", detail)
    logger.error("Lab4 Supabase %s failed | %s | %s", operation, type(exc).__name__, detail[:700])

BUCKET = "lab4-evidence"
MAX_UPLOAD_BYTES = 6 * 1024 * 1024
MAX_IMAGE_SIDE = 1600
st.set_page_config(page_title="Computer Networks LAB 4", page_icon="🌐", layout="wide")

q_path = ROOT / "lab4_questions.json"
if not q_path.is_file():
    st.error("Missing lab4_questions.json next to app3.py")
    st.stop()
import json
QUESTIONS = json.loads(q_path.read_text(encoding="utf-8"))
if not isinstance(QUESTIONS, list) or not QUESTIONS:
    st.error("lab4_questions.json must contain a non-empty list")
    st.stop()

try:
    URL = st.secrets["SUPABASE_URL"]
    SERVICE_KEY = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
except (KeyError, FileNotFoundError):
    st.error("Supabase server secrets missing. Configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
    st.stop()

# Avoid sharing a mutable HTTP client instance between concurrent user sessions.
@st.cache_resource
def _config_ok(url: str, key: str) -> bool:
    return bool(url.startswith("https://") and key)
if not _config_ok(URL, SERVICE_KEY):
    st.error("Supabase configuration is invalid.")
    st.stop()

def db():
    return create_client(URL, SERVICE_KEY)


def password_hash(pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), bytes.fromhex(salt), 210_000).hex()


def normalize_id(value: str) -> str:
    value = value.strip().upper()
    if not re.fullmatch(r"[A-Z0-9_-]{3,40}", value):
        raise ValueError("Student ID: 3–40 characters, letters/numbers/-/_ only.")
    return value


def sign_in_or_register(student_id: str, name: str, group: str, pin: str):
    """Create an account once; existing accounts require their previous PIN."""
    client = db()
    result = client.table("lab4_students").select("student_id,full_name,practical_group,pin_salt,pin_hash").eq("student_id", student_id).limit(1).execute()
    if result.data:
        person = result.data[0]
        candidate = password_hash(pin, person["pin_salt"])
        if not hmac.compare_digest(candidate, person["pin_hash"]):
            raise ValueError("Student ID already exists. Enter the original recovery PIN.")
        return person, False
    if not name.strip():
        raise ValueError("Full name is required to create a new account.")
    salt = secrets.token_hex(16)
    record = {
        "student_id": student_id,
        "full_name": name.strip()[:150],
        "practical_group": group.strip()[:80],
        "pin_salt": salt,
        "pin_hash": password_hash(pin, salt),
    }
    try:
        client.table("lab4_students").insert(record).execute()
        return record, True
    except Exception:
        # Handle simultaneous first-time registration safely; never overwrite credentials.
        again = client.table("lab4_students").select("student_id,full_name,practical_group,pin_salt,pin_hash").eq("student_id", student_id).limit(1).execute()
        if again.data:
            person = again.data[0]
            if hmac.compare_digest(password_hash(pin, person["pin_salt"]), person["pin_hash"]):
                return person, False
            raise ValueError("Student ID already exists. Enter its original recovery PIN.")
        raise


def load_progress(student_id: str) -> dict[int, dict]:
    rows = db().table("lab4_progress").select("question_index,answer,evidence_path,saved_at").eq("student_id", student_id).execute().data or []
    return {int(row["question_index"]): row for row in rows}


def normalize_screenshot(upload) -> bytes:
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValueError("Screenshot too large. Please select an image smaller than 6 MB.")
    raw = upload.getvalue()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError("Screenshot too large (6 MB maximum).")
    try:
        with PILImage.open(BytesIO(raw)) as source:
            source.verify()
        with PILImage.open(BytesIO(raw)) as source:
            source = ImageOps.exif_transpose(source)
            source.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
            if source.mode in ("RGBA", "P"):
                rgb = PILImage.new("RGB", source.size, "white")
                rgba = source.convert("RGBA")
                rgb.paste(rgba, mask=rgba.getchannel("A"))
                source = rgb
            else:
                source = source.convert("RGB")
            result = BytesIO()
            source.save(result, format="JPEG", quality=78, optimize=True)
            return result.getvalue()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("Invalid image. Upload a real PNG or JPG screenshot.") from exc


def save_question(student_id: str, number: int, answer: str, upload, previous: dict | None):
    """Upload new unique image first; write DB pointer last. Cleanup on failed DB save."""
    client = db()
    path = (previous or {}).get("evidence_path")
    new_path = None
    if upload is not None:
        optimized = normalize_screenshot(upload)
        new_path = f"{student_id}/q{number:03d}/{uuid.uuid4().hex}.jpg"
        client.storage.from_(BUCKET).upload(
            path=new_path, file=optimized,
            file_options={"content-type": "image/jpeg", "upsert": "false"},
        )
        path = new_path
    try:
        client.table("lab4_progress").upsert(
            {
                "student_id": student_id,
                "question_index": number,
                "answer": answer,
                "evidence_path": path,
                "saved_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="student_id,question_index",
        ).execute()
    except Exception:
        if new_path:
            try:
                client.storage.from_(BUCKET).remove([new_path])
            except Exception:
                pass
        raise
    # Old file can be deleted only after the new DB pointer is saved.
    old_path = (previous or {}).get("evidence_path")
    if new_path and old_path and old_path != new_path:
        try:
            client.storage.from_(BUCKET).remove([old_path])
        except Exception:
            pass  # Old orphan does not invalidate successful save.


def _pdf_styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(name="LabTitleCustom", parent=s["Heading1"], fontSize=16,
                         leading=20, textColor=colors.HexColor("#153c68"), alignment=TA_CENTER, spaceAfter=10))
    s.add(ParagraphStyle(name="LabSectionCustom", parent=s["Heading2"], fontSize=12,
                         spaceBefore=12, textColor=colors.HexColor("#174d87")))
    s.add(ParagraphStyle(name="LabQuestionCustom", parent=s["Heading3"], fontSize=10.5, leading=14))
    s.add(ParagraphStyle(name="LabNormalCustom", parent=s["Normal"], fontSize=9, leading=13, spaceAfter=9))
    return s


def make_pdf(person: dict, progress: dict[int, dict]) -> bytes:
    s = _pdf_styles()
    buf = BytesIO()
    document = SimpleDocTemplate(buf, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
                                 topMargin=18 * mm, bottomMargin=18 * mm,
                                 title="Computer Networks Lab 4 Exploratory Analysis")
    story = [Paragraph("COMPUTER NETWORKS LAB 4", s["LabTitleCustom"]),
             Paragraph("Exploratory Analysis — Student Submission", s["LabTitleCustom"]),
             HRFlowable(width="100%", thickness=1, color=colors.HexColor("#c3d3e4")), Spacer(1, 5 * mm)]
    for label, val in (("Student name", person["full_name"]),
                       ("Student ID", person["student_id"]),
                       ("Practical Group", person.get("practical_group") or "Not specified")):
        story.append(Paragraph(f"<b>{escape(label)}:</b> {escape(str(val))}", s["LabNormalCustom"]))
    current_section = None
    client = db()
    for i, question in enumerate(QUESTIONS, 1):
        row = progress.get(i, {})
        if question["section"] != current_section:
            current_section = question["section"]
            story.append(Paragraph(escape(current_section), s["LabSectionCustom"]))
        title = re.sub(r"^Q\d+\.\s*", "", question["title"])
        story.append(Paragraph(f"Q{i}. {escape(title)} — {escape(question['question'])}", s["LabQuestionCustom"]))
        safe_answer = escape(row.get("answer") or "").replace("\n", "<br/>")
        story.append(Paragraph("<b>Student answer:</b><br/>" + safe_answer, s["LabNormalCustom"]))
        path = row.get("evidence_path")
        if path:
            # Only download one optimized screenshot at a time; no images in session state.
            binary = client.storage.from_(BUCKET).download(path)
            image = Image(BytesIO(binary))
            ratio = min(165 * mm / image.imageWidth, 105 * mm / image.imageHeight, 1.0)
            image.drawWidth *= ratio
            image.drawHeight *= ratio
            story.extend([Paragraph("<b>Packet Tracer screenshot evidence:</b>", s["LabNormalCustom"]), image, Spacer(1, 5 * mm)])
    story.append(Paragraph("This PDF reproduces the student's saved responses and screenshots; it does not certify correctness.", s["LabNormalCustom"]))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(18 * mm, 11 * mm, person["student_id"][:35])
        canvas.drawRightString(192 * mm, 11 * mm, f"Page {doc.page}")
        canvas.restoreState()
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


st.markdown("""<div style="background:#12335B;color:white;border-radius:8px;padding:20px;text-align:center;margin-bottom:18px">
<div style="font-size:28px;font-weight:700">Computer Networks LAB 4</div>
<div style="font-size:21px">Exploratory Analysis</div></div>""", unsafe_allow_html=True)
st.info("Work on **one question at a time**. Click **Save Progress to Supabase** after EACH question. "
        "You can reconnect later with your Student ID and recovery PIN; saved answers and screenshots will return.")

if "person" not in st.session_state:
    st.session_state.person = None
if "question_number" not in st.session_state:
    st.session_state.question_number = 1

with st.sidebar:
    st.header("Student account / Recovery")
    if st.session_state.person is None:
        with st.form("login_form"):
            student_id_input = st.text_input("Student ID *", max_chars=40)
            student_name_input = st.text_input("Full Name (required for first login)", max_chars=150)
            group_input = st.text_input("Practical Group", max_chars=80)
            pin_input = st.text_input("Recovery PIN (minimum 6 characters)", type="password")
            login = st.form_submit_button("Start / Restore Saved Work", width="stretch")
        if login:
            try:
                sid = normalize_id(student_id_input)
                if len(pin_input) < 6:
                    raise ValueError("Enter a recovery PIN of at least 6 characters.")
                person, created = sign_in_or_register(sid, student_name_input, group_input, pin_input)
                for old_key in list(st.session_state):
                    if old_key.startswith(("answer_entry_q", "image_upload_q", "save_form_q")):
                        st.session_state.pop(old_key, None)
                st.session_state.person = {k: person[k] for k in ("student_id", "full_name", "practical_group")}
                st.session_state.question_number = 1
                st.session_state.pop("question_selector", None)
                st.session_state.pdf_data = None
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                log_database_error("login/register", exc)
                st.error("Database connection failed. Your login was not confirmed. Ask your lecturer to check Streamlit app logs.")
                st.caption(f"Diagnostic: {type(exc).__name__} (full sanitized detail is in Manage app → Logs)")
    else:
        person = st.session_state.person
        st.success(f"Logged in: {person['full_name']}")
        st.caption(f"Student ID: {person['student_id']}")
        if st.button("Log out / Switch student", width="stretch"):
            for key in list(st.session_state):
                if key in ("person", "pdf_data", "question_number", "question_selector") or key.startswith(("answer_entry_q", "image_upload_q", "save_form_q")):
                    st.session_state.pop(key, None)
            st.rerun()

if st.session_state.person is None:
    st.markdown("Enter your details and choose a recovery PIN in the sidebar. Existing students must use their original PIN.")
    st.stop()

person = st.session_state.person
sid = person["student_id"]
try:
    progress = load_progress(sid)
except Exception as exc:
    log_database_error("load progress", exc)
    st.error("Cannot read saved work from Supabase right now. Please retry later; do not assume progress is saved.")
    st.caption(f"Diagnostic: {type(exc).__name__}")
    st.stop()

fully_saved = [i for i in range(1, len(QUESTIONS) + 1)
               if len((progress.get(i, {}).get("answer") or "").strip()) >= 25
               and bool(progress.get(i, {}).get("evidence_path"))]
st.progress(len(fully_saved) / len(QUESTIONS),
            text=f"Complete answers + screenshots SAVED in Supabase: {len(fully_saved)} / {len(QUESTIONS)}")

with st.expander("Lab instructions — read before starting", expanded=False):
    st.markdown("""1. Open **Edit Topologies.pka** in Cisco Packet Tracer and save a working copy.
2. Switch between **Logical** and **Physical** views when needed.
3. Investigate actual configurations; **do not guess unseen IP addresses**.
4. Enter an answer, attach screenshot evidence, and click **Save Progress to Supabase** after every question.
5. Once all questions are saved, generate the PDF and upload it and the Packet Tracer file to **MyTimes**.

**Note:** Activity instructions give `192.168.20.5` as a ping target for Office-Admin, but notes call this the Network Controller. Verify the address in Packet Tracer.""")

n = st.selectbox("Choose question (only ONE image uploader is active at a time)",
                 options=list(range(1, len(QUESTIONS) + 1)),
                 index=max(0, min(st.session_state.question_number - 1, len(QUESTIONS) - 1)),
                 format_func=lambda x: f"Q{x} — {'✓ saved' if x in progress else 'not saved'} — {re.sub(r'^Q\d+\.\s*', '', QUESTIONS[x-1]['title'])}",
                 key="question_selector")
st.session_state.question_number = n
question = QUESTIONS[n - 1]
row = progress.get(n, {})
st.divider()
st.header(question["section"])
if question["section"] == "B. Office Cluster" and (ROOT / "office_topology.png").is_file():
    st.image(str(ROOT / "office_topology.png"), caption="Office cluster topology", width=680)
elif n == 1 and (ROOT / "city_topology.png").is_file():
    st.image(str(ROOT / "city_topology.png"), caption="City-level topology", width=680)

title = re.sub(r"^Q\d+\.\s*", "", question["title"])
st.subheader(f"Q{n}. {title}")
st.markdown(question["question"])
with st.expander("How to investigate in Packet Tracer"):
    for i, step in enumerate(question.get("steps", []), 1):
        st.write(f"{i}. {step}")
st.caption(question.get("prompt", ""))

if row:
    saved_when = row.get("saved_at") or "previous session"
    st.success(f"Previously saved in Supabase — {saved_when}. You may edit and save again.")
    if row.get("evidence_path"):
        st.caption("✓ Screenshot evidence already safely stored. No need to upload it again unless replacing it.")

# Only one form/image exists per browser session. No image bytes in st.session_state.
# Changing questions remounts form so the database answer, not stale session state, is displayed.
# Custom typing component blocks paste/copy/drop with a MAC-style warning dialog.
# Unlike a Streamlit form, a custom component must be placed OUTSIDE st.form.
# Only one question and one uploader remain mounted at any time.
answer = ANSWER_WIDGET(default=row.get("answer") or "", key=f"answer_entry_q{n}")
answer = answer if isinstance(answer, str) else (row.get("answer") or "")
image_upload = st.file_uploader("Screenshot evidence (PNG/JPG; maximum 6 MB)",
                                type=["png", "jpg", "jpeg"], key=f"image_upload_q{n}")
submitted = st.button(f"💾 Save Progress to Supabase — Q{n}", type="primary", width="stretch")

if submitted:
    try:
        answer = answer.strip()
        if not answer and image_upload is None and not row.get("evidence_path"):
            raise ValueError("Enter an answer or upload evidence before saving.")
        with st.spinner("Saving Q%d securely to Supabase..." % n):
            save_question(sid, n, answer, image_upload, row)
        st.session_state.pdf_data = None
        st.success(f"✅ Your progress for Question {n} has been saved successfully in Supabase. You can safely return to it later.")
        # New DB save is verifiable on next app rerun; avoid rerun here so success message remains visible.
    except ValueError as exc:
        st.error(f"NOT SAVED: {exc}")
    except Exception as exc:
        log_database_error("save question", exc)
        st.error("NOT CONFIRMED SAVED: Supabase operation failed. Do not move on until a success message appears. "
                 "Try Save Progress again. If it repeats, inform your lecturer.")
        st.caption(f"Technical error type: {type(exc).__name__}")

# Button callbacks execute before Streamlit instantiates the selectbox on the next run.
# Never modify a widget's session-state key after the widget has been rendered.
def navigate_question(target: int):
    st.session_state.question_number = target
    st.session_state.question_selector = target

left, right = st.columns(2)
with left:
    st.button("← Previous question", disabled=(n == 1), width="stretch",
              on_click=navigate_question, args=(n - 1,))
with right:
    st.button("Next question →", disabled=(n == len(QUESTIONS)), width="stretch",
              on_click=navigate_question, args=(n + 1,))

st.divider()
st.subheader("Review and PDF submission")
st.caption("A question counts as complete only if the saved answer has at least 25 characters AND a screenshot is in Supabase. "
           "Saving partial work is still allowed.")
if len(fully_saved) < len(QUESTIONS):
    missing = [str(i) for i in range(1, len(QUESTIONS)+1) if i not in fully_saved]
    st.warning("Before final PDF: complete and save Q" + ", Q".join(missing))
else:
    st.success("All questions and evidence are recorded in Supabase.")
    if st.button("Prepare PDF from Supabase saved data", width="stretch"):
        try:
            with st.spinner("Retrieving saved evidence and preparing PDF..."):
                fresh = load_progress(sid)
                if any(len((fresh.get(i, {}).get("answer") or "").strip()) < 25
                       or not fresh.get(i, {}).get("evidence_path")
                       for i in range(1, len(QUESTIONS) + 1)):
                    raise ValueError("Some answers or evidence are no longer available. Reload and check your progress.")
                st.session_state.pdf_data = make_pdf(person, fresh)
            st.success("PDF prepared from saved Supabase data.")
        except Exception as exc:
            log_database_error("prepare PDF", exc)
            st.session_state.pdf_data = None
            st.error("PDF creation failed. Your saved Supabase progress remains intact; retry PDF preparation.")
            st.caption(f"Technical error type: {type(exc).__name__}")
    if st.session_state.get("pdf_data"):
        st.download_button("Download completed PDF", data=st.session_state.pdf_data,
                           file_name=f"{sid}_Computer_Networks_LAB4_Exploratory_Analysis.pdf",
                           mime="application/pdf", width="stretch", on_click="ignore")
    st.caption("The PDF download does NOT submit to MyTimes. Upload your PDF and Packet Tracer activity file there yourself.")
