"""Computer Networks Lab 4 — standalone Streamlit exploratory worksheet.
Run: streamlit run app3.py
Dependencies: streamlit, reportlab, pillow
Required alongside app3.py: lab4_questions.json, typed_answer/index.html,
city_topology.png, office_topology.png
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import streamlit as st
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)
from streamlit.components.v1 import declare_component

ROOT = Path(__file__).resolve().parent
st.set_page_config(
    page_title="Computer Networks LAB 4 | Exploratory Analysis",
    page_icon="🌐",
    layout="wide",
)

questions_file = ROOT / "lab4_questions.json"
if not questions_file.is_file():
    st.error("Missing lab4_questions.json in the same directory as app3.py.")
    st.stop()

QUESTIONS = json.loads(questions_file.read_text(encoding="utf-8"))
if not isinstance(QUESTIONS, list) or not QUESTIONS:
    st.error("lab4_questions.json must contain a non-empty list of questions.")
    st.stop()

component_folder = ROOT / "typed_answer"
if not (component_folder / "index.html").is_file():
    st.error("Missing typed_answer/index.html. Upload the entire typed_answer folder.")
    st.stop()

ANSWER_WIDGET = declare_component("lab4_typed_answer", path=str(component_folder))

st.markdown(
    """<style>
    .block-container {max-width: 1100px; padding-top: 1.7rem;}
    [data-testid="stMarkdownContainer"] p {line-height: 1.5;}
    </style>""",
    unsafe_allow_html=True,
)

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="LabTitle", parent=styles["Heading1"], fontSize=16, leading=21,
    spaceAfter=10, textColor=colors.HexColor("#153c68"), alignment=TA_CENTER,
))
styles.add(ParagraphStyle(
    name="LabSub", parent=styles["Normal"], fontSize=9.5, leading=14, spaceAfter=7,
))
styles.add(ParagraphStyle(
    name="LabSection", parent=styles["Heading2"], fontSize=12, leading=16,
    spaceBefore=13, spaceAfter=7, textColor=colors.HexColor("#174d87"),
))
styles.add(ParagraphStyle(
    name="LabQ", parent=styles["Heading3"], fontSize=10.5, leading=15, spaceAfter=5,
))
styles.add(ParagraphStyle(
    name="LabAnswer", parent=styles["Normal"], fontSize=9.5, leading=14, spaceAfter=12,
))


def make_pdf(name: str, student_id: str, group: str,
             answers: list[str], screenshots: list[bytes | None]) -> bytes:
    """Create a PDF containing each question, typed answer, and uploaded image."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title="Computer Networks Lab 4 Exploratory Analysis",
    )
    story = [
        Paragraph("COMPUTER NETWORKS LAB 4", styles["LabTitle"]),
        Paragraph("Exploratory Analysis - Student Submission", styles["LabTitle"]),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#c3d3e4")),
        Spacer(1, 6 * mm),
    ]
    timestamp = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    for label, value in [
        ("Student name", name),
        ("Student ID", student_id),
        ("Group / section", group or "Not specified"),
        ("Generated", timestamp),
    ]:
        story.append(Paragraph(
            f"<b>{escape(label)}:</b> {escape(value)}", styles["LabSub"]
        ))

    current_section = None
    for i, question in enumerate(QUESTIONS):
        if question["section"] != current_section:
            current_section = question["section"]
            story.append(Paragraph(escape(current_section), styles["LabSection"]))

        # Number questions by display order, even after edits to the JSON list.
        title = re.sub(r"^Q\d+\.\s*", "", question["title"])
        story.append(Paragraph(
            f"Q{i + 1}. {escape(title)} - {escape(question['question'])}",
            styles["LabQ"],
        ))
        response = escape(answers[i]).replace("\n", "<br/>")
        story.append(Paragraph(
            "<b>Student answer:</b><br/>" + response, styles["LabAnswer"]
        ))

        if screenshots[i] is not None:
            image_buffer = BytesIO(screenshots[i])
            image_flowable = Image(image_buffer)
            max_width, max_height = 165 * mm, 105 * mm
            scale = min(
                max_width / image_flowable.imageWidth,
                max_height / image_flowable.imageHeight,
                1.0,
            )
            image_flowable.drawWidth = image_flowable.imageWidth * scale
            image_flowable.drawHeight = image_flowable.imageHeight * scale
            story.append(Paragraph(
                "<b>Packet Tracer screenshot evidence:</b>", styles["LabSub"]
            ))
            story.append(image_flowable)
            story.append(Spacer(1, 5 * mm))

    story.append(Paragraph(
        "This document reproduces the student's submitted answers and screenshots. "
        "It does not certify correctness or completion of the Packet Tracer activity.",
        styles["LabSub"],
    ))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(18 * mm, 11 * mm,
                          f"{student_id} | Computer Networks LAB 4")
        canvas.drawRightString(192 * mm, 11 * mm, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


st.markdown("""
<div style="background-color:#12335B;border:2px solid #0B2545;
            border-radius:8px;padding:20px;text-align:center;
            font-family:Arial,sans-serif;color:white;margin-bottom:25px;">
  <div style="font-size:30px;font-weight:bold;">Computer Networks LAB 4</div>
  <div style="font-size:24px;font-weight:500;margin-top:8px;">Exploratory Analysis</div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div style="background-color:#F2F4F7;border:1px solid #B5D0E0;
            border-left:5px solid #176B9A;border-radius:8px;
            padding:18px 24px;font-family:Arial,sans-serif;
            font-size:17px;color:#18324B;line-height:1.9;margin-bottom:20px;">
  <div style="font-size:20px;font-weight:bold;margin-bottom:8px;">Lab Instructions</div>
  <ul style="margin:0;padding-left:25px;">
    <li>Use the actual <b>Edit Topologies.pka</b> activity to investigate every question.</li>
    <li>Type your observations in the provided answer fields.</li>
    <li>Copy and paste are restricted in the answer fields.</li>
    <li>Upload a Packet Tracer screenshot below each answer as evidence.</li>
    <li>Download the PDF and submit it to <b>MyTimes</b> with your completed Packet Tracer file.</li>
  </ul>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Student details")
    student_name = st.text_input("Full name *", key="lab4_name")
    student_id = st.text_input("Student ID *", key="lab4_id")
    group = st.text_input("Practical Group", key="lab4_group")
    st.divider()
    st.markdown("""
    <div style="font-family:Arial,sans-serif;font-size:16px;line-height:1.8;">
      <b>Submission Instructions:</b>
      <ul>
        <li>Answer every question and upload the required evidence.</li>
        <li>Download the generated PDF after completing the worksheet.</li>
        <li>Upload the PDF to <b>MyTimes</b> along with the completed Cisco Packet Tracer file.</li>
      </ul>
    </div>
    """, unsafe_allow_html=True)

with st.expander("Instructions - read before starting", expanded=True):
    st.markdown("""1. Open **Edit Topologies.pka** in Cisco Packet Tracer and save a working copy.
2. Switch between **Logical** and **Physical** views when required.
3. Explore each location and inspect its actual devices. **Do not guess unseen IP addresses.**
4. Answer in your own words and upload screenshot evidence for each question.
5. Download the completed PDF and upload it to **MyTimes** alongside your Packet Tracer activity file.

**Note:** The activity instructions give `192.168.20.5` as the ping target for Office-Admin,
but the topology notes label that address as the Network Controller. Verify the target
IP address in Packet Tracer before pinging.""")

city_image = ROOT / "city_topology.png"
if city_image.is_file():
    st.image(str(city_image), caption="City-level topology from the original activity", width=680)
else:
    st.warning("city_topology.png is missing; the worksheet will continue without this image.")

section_name = None
answers: list[str] = []
screenshots: list[bytes | None] = []

for i, question in enumerate(QUESTIONS):
    if question["section"] != section_name:
        section_name = question["section"]
        st.divider()
        st.header(section_name)
        if section_name == "B. Office Cluster":
            office_image = ROOT / "office_topology.png"
            if office_image.is_file():
                st.image(
                    str(office_image),
                    caption="Original Office cluster: inspect actual configurations in Packet Tracer",
                    use_container_width=True,
                )

    with st.container(border=True):
        clean_title = re.sub(r"^Q\d+\.\s*", "", question["title"])
        st.subheader(f"Q{i + 1}. {clean_title}")
        st.markdown(question["question"])

        with st.expander("How to investigate in Packet Tracer"):
            for step_no, step in enumerate(question["steps"], 1):
                st.write(f"{step_no}. {step}")

        st.caption(question["prompt"])
        value = ANSWER_WIDGET(
            key=f"lab4_answer_{i}",
            default="",
            placeholder=f"Type your findings for Q{i + 1}. {clean_title}...",
        )
        answers.append(value.strip() if isinstance(value, str) else "")

        st.markdown("**Packet Tracer Screenshot Evidence**")
        uploaded_file = st.file_uploader(
            f"Upload screenshot for Q{i + 1} (PNG/JPG)",
            type=["png", "jpg", "jpeg"],
            key=f"lab4_screenshot_{i}",
        )
        if uploaded_file is not None:
            screenshot_bytes = uploaded_file.getvalue()
            if len(screenshot_bytes) > 8 * 1024 * 1024:
                st.error("This image is larger than 8 MB. Upload a smaller screenshot.")
                screenshots.append(None)
            else:
                try:
                    from PIL import Image as PILImage
                    with PILImage.open(BytesIO(screenshot_bytes)) as check_image:
                        check_image.verify()
                    screenshots.append(screenshot_bytes)
                    st.image(
                        screenshot_bytes,
                        caption=f"Evidence for Q{i + 1}: {clean_title}",
                        width=550,
                    )
                    st.success("Screenshot uploaded.")
                except Exception:
                    screenshots.append(None)
                    st.error("Please upload a valid PNG or JPG screenshot.")
        else:
            screenshots.append(None)

answered = sum(bool(answer) for answer in answers)
st.divider()
st.progress(
    answered / len(QUESTIONS),
    text=f"Completed: {answered} / {len(QUESTIONS)} questions",
)

with st.container(border=True):
    st.subheader("Review & Submit")
    st.write(
        f"**Student:** {student_name or 'Not entered'} | "
        f"**ID:** {student_id or 'Not entered'}"
    )

    missing_answers = [
        i + 1 for i, answer in enumerate(answers) if len(answer) < 25
    ]
    missing_screenshots = [
        i + 1 for i, screenshot in enumerate(screenshots) if screenshot is None
    ]

    if missing_answers:
        st.warning(
            "Write at least 25 characters for each answer. Incomplete: "
            + ", ".join(f"Q{i}" for i in missing_answers)
        )
    if missing_screenshots:
        st.warning(
            "Screenshot evidence missing for: "
            + ", ".join(f"Q{i}" for i in missing_screenshots)
        )

    ready = bool(
        student_name.strip()
        and student_id.strip()
        and not missing_answers
        and not missing_screenshots
    )
    if not ready:
        st.caption(
            f"Provide your name, Student ID, all {len(QUESTIONS)} answers "
            "and all required screenshots to enable PDF download."
        )

    pdf_bytes = b""
    if ready:
        try:
            pdf_bytes = make_pdf(
                student_name.strip(), student_id.strip(), group.strip(),
                answers, screenshots,
            )
        except Exception as exc:
            st.error(f"Could not generate the PDF: {exc}")
            ready = False

    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "_", student_id.strip())[:70]
    st.download_button(
        "Submit answers & Download PDF",
        data=pdf_bytes,
        file_name=f"{safe_id}_Computer_Networks_LAB4_Exploratory_Analysis.pdf",
        mime="application/pdf",
        type="primary",
        disabled=not ready,
        use_container_width=True,
        on_click="ignore",
    )
    st.caption(
        "This downloads your PDF only. It does not upload your answers to MyTimes. "
        "Upload the PDF and completed Packet Tracer activity file yourself."
    )
