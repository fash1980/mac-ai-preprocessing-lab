"""Week 4 Practical evidence submission: resumable submissions and bounded retries.

GitHub: upload this file as app2.py. Needs typing_input/index.html.
Secrets: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
Run the accompanying one-time SQL migration before deploying.
"""
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import hashlib
import logging
import time
import uuid

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageOps, UnidentifiedImageError

st.set_page_config(page_title="MAC | Week 4 Practical Submission", page_icon="📎", layout="wide")

COMPONENT_PATH = Path(__file__).parent / "typing_input"
typing_input = (
    components.declare_component("practical_typing_input_robust_v1", path=str(COMPONENT_PATH))
    if (COMPONENT_PATH / "index.html").is_file()
    else None
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
        pass
    except Exception:
        logging.exception("Supabase connection configuration failed")
    return None


def is_transient(exc):
    import httpx
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return True
    msg = str(exc).lower()
    return any(s in msg for s in (
        "temporarily unavailable", "timeout", "timed out", "connection reset",
        "connection closed", "429", "502", "503", "504", "service unavailable",
    ))


def retry_call(fn, label, attempts=3):
    for n in range(attempts):
        try:
            return fn()
        except Exception as exc:
            logging.warning("%s attempt %s failed: %s", label, n + 1, type(exc).__name__)
            if n == attempts - 1 or not is_transient(exc):
                raise
            time.sleep(min(2 ** n, 4))


def prepared_image(upload):
    """Convert student screenshot to compact RGB JPEG, max 1900px wide.

    Images retain enough resolution to read most notebook outputs while reducing
    large PNG uploads. Reject files whose source exceeds the class limit.
    """
    if upload.size > 4 * 1024 * 1024:
        raise ValueError(f"{upload.name}: exceeds 4 MB source size limit")
    try:
        image = Image.open(BytesIO(upload.getvalue()))
        image.verify()
        image = Image.open(BytesIO(upload.getvalue()))
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((1900, 2400), Image.Resampling.LANCZOS)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError(f"{upload.name}: invalid or unsupported image") from exc
    for quality in (83, 72, 62):
        b = BytesIO()
        image.save(b, format="JPEG", optimize=True, quality=quality)
        if b.tell() <= 950_000 or quality == 62:
            return b.getvalue()
    raise RuntimeError("Image conversion unexpectedly failed")


def object_exists(storage, path):
    """Check exact filename in a submission folder after ambiguous upload error."""
    folder, filename = path.rsplit("/", 1)
    objects = retry_call(lambda: storage.list(folder), "check uploaded file", attempts=2)
    return any(o.get("name") == filename for o in objects)


def upload_with_recovery(storage, path, content):
    # Unique submission UUID ensures a path cannot collide with another student.
    if object_exists(storage, path):
        return
    for attempt in range(3):
        try:
            storage.upload(path, content, {"content-type": "image/jpeg", "upsert": "false"})
            return
        except Exception as exc:
            # A network disconnect can occur AFTER Supabase stored the object.
            # Check before retrying to avoid duplicate file errors.
            try:
                if object_exists(storage, path):
                    return
            except Exception:
                logging.warning("Could not confirm object after upload error")
            if ("already exists" in str(exc).lower() or "409" in str(exc)):
                # Path is scoped to a unique submission; if it exists, reuse it.
                if object_exists(storage, path):
                    return
            if not is_transient(exc) or attempt == 2:
                raise
            time.sleep(min(2 ** attempt, 4))


db = get_db()
st.title("Week 4 Practical — Colab Evidence Submission")
st.caption("MAC · Applied Artificial Intelligence · Separate from the Scenario Tutorial")
st.markdown("""
### Lab Instructions
- Complete both Google Colab notebooks: **Task 1 (Numerical Data)** and **Task 2 (Multimodal Data)**.
- Enter your own **Student ID** in each notebook before executing the cells.
- Complete the unfinished Python code and run the experiments.
- Capture screenshots of your **actual Colab outputs** as evidence.
- Enter the **Run Token** generated by each notebook.
- **Copy-paste is restricted in the analysis field. Type your answer manually.**
- Submit **Task 1 and Task 2 separately** with screenshots and observations.
""")
if db is None:
    st.warning("Database not configured. Submissions cannot be saved.")
if typing_input is None:
    st.error("Missing typing_input/index.html. Restore this file before collecting submissions.")

left, right = st.columns(2)
with left:
    student_id = st.text_input("Student ID", max_chars=40)
    student_name = st.text_input("Student name", max_chars=100)
with right:
    task = st.selectbox("Practical task", ["Task 1 — Numerical", "Task 2 — Multimodal"])
    token = st.text_input("Colab run token (from notebook E0)", max_chars=32)

st.markdown("#### Evidence screenshots")
st.caption("Upload 2–5 Colab screenshots (PNG/JPG), maximum 4 MB each before compression. No real patient information.")
shots = st.file_uploader("Screenshot evidence", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
st.markdown("#### Type your evidence-based analysis (100–220 words)")
answer_key = "analysis_task1" if task.startswith("Task 1") else "analysis_task2"
if typing_input is not None:
    typed = typing_input(
        value=st.session_state.get(answer_key, ""),
        key=f"practical_robust_{answer_key}",
        default=st.session_state.get(answer_key, ""),
    )
    if typed is not None:
        st.session_state[answer_key] = str(typed)
analysis = st.session_state.get(answer_key, "")
word_count = len(analysis.split())
st.caption(f"Recorded word count: {word_count} (required: 100–220). Wait one second after typing before submitting.")
checklist = st.checkbox("I have executed the notebook and the screenshots are from my own Colab session.")

# A stable UUID is retained for retries during a session. The operation will
# reuse files already uploaded under this UUID rather than starting over.
if "pending_submission" not in st.session_state:
    st.session_state.pending_submission = None
if "completed_submission" not in st.session_state:
    st.session_state.completed_submission = None

submit = st.button("Submit practical evidence", type="primary", disabled=db is None or typing_input is None)
if submit:
    problems = []
    if len(student_id.strip()) < 4:
        problems.append("Enter a valid Student ID.")
    if not student_name.strip():
        problems.append("Enter your name.")
    if len(token.strip()) < 8:
        problems.append("Enter the Colab run token.")
    if not 2 <= len(shots or []) <= 5:
        problems.append("Upload 2–5 screenshots.")
    if not 100 <= word_count <= 220:
        problems.append(f"Analysis must have 100–220 words (currently {word_count}).")
    if not checklist:
        problems.append("Confirm the declaration.")
    if problems:
        for p in problems:
            st.error(p)
    else:
        try:
            with st.spinner("Preparing and storing evidence. Please keep this page open..."):
                # Compute a content fingerprint so a changed answer or screenshot
                # starts a new submission rather than mixing two attempts.
                images = [prepared_image(shot) for shot in shots]
                h = hashlib.sha256()
                for part in (student_id.strip(), student_name.strip(), task, token.strip(), analysis.strip()):
                    h.update(part.encode("utf-8"))
                    h.update(b"\0")
                for data in images:
                    h.update(hashlib.sha256(data).digest())
                fingerprint = h.hexdigest()
                completed = st.session_state.completed_submission
                if completed and completed["fingerprint"] == fingerprint:
                    st.success(f"Already submitted. Receipt: {completed['receipt']}")
                else:
                    pending = st.session_state.pending_submission
                    if not pending or pending["fingerprint"] != fingerprint:
                        pending = {"fingerprint": fingerprint, "id": uuid.uuid4().hex}
                        st.session_state.pending_submission = pending
                    sid = pending["id"]
                    paths = [f"{sid}/evidence_{i + 1}.jpg" for i in range(len(images))]
                    base = {
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
                    # Record-first means every attempt is traceable, even if the
                    # screenshot network upload subsequently fails.
                    retry_call(
                        lambda: db.table("practical_submissions").upsert(base, on_conflict="submission_id").execute(),
                        "create pending record",
                    )
                    storage = db.storage.from_("practical-evidence")
                    progress = st.progress(0, text="Uploading screenshots")
                    for i, (path, content) in enumerate(zip(paths, images)):
                        upload_with_recovery(storage, path, content)
                        progress.progress((i + 1) / len(images), text=f"Uploaded {i + 1} of {len(images)}")
                    # Mark as complete ONLY once all screenshot paths exist.
                    retry_call(
                        lambda: db.table("practical_submissions")
                            .update({"status": "completed", "evidence_paths": paths})
                            .eq("submission_id", sid).execute(),
                        "complete submission",
                    )
                    receipt = sid[:12].upper()
                    st.session_state.completed_submission = {"fingerprint": fingerprint, "receipt": receipt}
                    st.session_state.pending_submission = None
                    st.success(f"Submission saved with all screenshots. Receipt: {receipt}. Keep this receipt.")
        except ValueError as exc:
            st.error(str(exc))
        except Exception:
            logging.exception("Practical submission retryable failure")
            st.error(
                "Submission is not yet complete. A pending record may have been saved. "
                "Keep this browser tab open and press Submit again after checking your connection. "
                "Your current attempt will reuse its submission ID and existing uploaded screenshots."
            )

st.caption(
    "Student IDs are self-declared. Paste restrictions are not foolproof. "
    "Only rows with status 'completed' count as successful submissions."
)
