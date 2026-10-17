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
