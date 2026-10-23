import json
from io import BytesIO
from xml.sax.saxutils import escape

import streamlit as st
from supabase import create_client
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether, HRFlowable

st.set_page_config(page_title='MAC Tutorial 4 | Teacher Review', page_icon='📋', layout='wide')
st.title('Machine Learning Preprocessing Tutorial Week 4')
st.subheader('Teacher Review & Feedback')
st.caption('Read-only student submissions. Teacher comments are held in this browser session until exported.')

@st.cache_resource
def get_client(url, key):
    return create_client(url, key)

@st.cache_data(ttl=120, show_spinner='Loading submissions...')
def fetch_submissions(url, key):
    db = get_client(url, key)
    records = []
    start = 0
    while True:
        batch = (db.table('tutorial_submissions')
                 .select('id,student_id,student_name,answers,submitted_at')
                 .order('id').range(start, start + 499).execute()).data or []
        records.extend(batch)
        if len(batch) < 500:
            break
        start += 500
    return records

try:
    url = st.secrets['SUPABASE_URL']
    key = st.secrets['SUPABASE_SERVICE_ROLE_KEY']
    if not url or not key:
        raise KeyError('Missing Supabase credentials')
except (KeyError, FileNotFoundError):
    st.error('Configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in Streamlit app Secrets.')
    st.stop()

try:
    if st.sidebar.button('Refresh submissions'):
        fetch_submissions.clear()
    records = fetch_submissions(url, key)
except Exception as exc:
    st.error(f'Unable to load submissions: {exc}')
    st.stop()

if not records:
    st.info('No submissions found.')
    st.stop()

search = st.text_input('Search student name or ID')
student_ids = sorted({str(r.get('student_id') or '') for r in records})
chosen_id = st.selectbox('Filter by student ID', ['All students'] + student_ids)
filtered = [r for r in records if (
    (not search.strip() or search.casefold().strip() in str(r.get('student_name') or '').casefold()
     or search.casefold().strip() in str(r.get('student_id') or '').casefold())
    and (chosen_id == 'All students' or str(r.get('student_id') or '') == chosen_id)
)]
if not filtered:
    st.warning('No matching records.')
    st.stop()

# Each submission ID has separate comment widget keys.
if 'review_record_id' not in st.session_state:
    st.session_state.review_record_id = filtered[0]['id']
current_ids = [r['id'] for r in filtered]
if st.session_state.review_record_id not in current_ids:
    st.session_state.review_record_id = current_ids[0]
index = current_ids.index(st.session_state.review_record_id)

def navigate(delta):
    pos = current_ids.index(st.session_state.review_record_id)
    st.session_state.review_record_id = current_ids[max(0, min(len(current_ids)-1, pos+delta))]

left, middle, right = st.columns([1, 2, 1])
with left:
    st.button('← Previous student', on_click=navigate, args=(-1,), disabled=index == 0, use_container_width=True)
with middle:
    st.markdown(f'<p style="text-align:center"><b>Submission {index+1} of {len(filtered)}</b></p>', unsafe_allow_html=True)
with right:
    st.button('Next student →', on_click=navigate, args=(1,), disabled=index == len(filtered)-1, use_container_width=True)

record = filtered[index]
rec_id = str(record['id'])
st.divider()
a, b, c = st.columns([2, 1, 1])
a.markdown(f"**Student:** {record.get('student_name') or 'Not provided'}")
b.markdown(f"**ID:** {record.get('student_id') or 'Not provided'}")
c.markdown(f"**Record:** {rec_id}")
if record.get('submitted_at'):
    st.caption(f"Submitted: {record['submitted_at']}")

answers = record.get('answers') or {}
if isinstance(answers, str):
    try:
        answers = json.loads(answers)
    except json.JSONDecodeError:
        st.error('Answers JSON could not be decoded.')
        st.stop()
if not isinstance(answers, dict):
    st.json(answers)
    st.stop()

num_questions = sum(len(v) for v in answers.values() if isinstance(v, dict))
num_answered = sum(bool(str(a).strip()) for v in answers.values() if isinstance(v, dict) for a in v.values() if a is not None)
st.progress(num_answered / num_questions if num_questions else 0, text=f'Student answers: {num_answered} / {num_questions}')

# Keep the original question wording as stored in Supabase JSONB.
for si, (scenario, questions) in enumerate(answers.items()):
    with st.expander(str(scenario), expanded=True):
        if isinstance(questions, dict):
            for qi, (question, answer) in enumerate(questions.items()):
                st.markdown(f'**{question}**')
                if answer is None or not str(answer).strip():
                    st.caption('No answer submitted.')
                else:
                    st.write(str(answer))
                st.text_area('Teacher comment', key=f'comment_{rec_id}_{si}_{qi}', height=90,
                             placeholder='Write feedback on this answer...')
                st.divider()
        else:
            st.write(questions)
        st.text_area('Scenario feedback', key=f'scenario_{rec_id}_{si}', height=90,
                     placeholder='Optional feedback for this scenario...')

st.subheader('Overall Teacher Feedback')
st.text_area('Overall comments', key=f'overall_{rec_id}', height=150,
             placeholder='Strengths, improvements, and recommendations...')
st.text_input('Marks / Grade (optional)', key=f'marks_{rec_id}', placeholder='e.g. 24/30 or B+')

# Downloadable PDF is generated from the current student's saved answers and in-session review fields.
def make_pdf():
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=19*mm, leftMargin=19*mm,
                            topMargin=18*mm, bottomMargin=18*mm)
    base = getSampleStyleSheet()
    base.add(ParagraphStyle(name='ReportTitleCustom', parent=base['Title'], fontSize=16, leading=20,
                            textColor=colors.HexColor('#20334a'), spaceAfter=12))
    base.add(ParagraphStyle(name='ScenarioCustom', parent=base['Heading2'], fontSize=12,
                            textColor=colors.HexColor('#165c70'), spaceBefore=12, spaceAfter=7))
    base.add(ParagraphStyle(name='QuestionCustom', parent=base['BodyText'], fontSize=9.5,
                            leading=14, spaceBefore=8, spaceAfter=4))
    base.add(ParagraphStyle(name='AnswerCustom', parent=base['BodyText'], fontSize=9.5,
                            leading=14, leftIndent=8, spaceAfter=5))
    base.add(ParagraphStyle(name='CommentCustom', parent=base['BodyText'], fontSize=9.5,
                            leading=14, leftIndent=8, textColor=colors.HexColor('#24556b'), spaceAfter=8))
    story = [Paragraph('MAC Tutorial Week 4 — Reviewed Submission', base['ReportTitleCustom'])]
    def p(value, style='BodyText'):
        return Paragraph(escape(str(value if value is not None else '')).replace('\n', '<br/>'), base[style])
    story += [p(f"Student: {record.get('student_name') or 'Not provided'}"),
              p(f"Student ID: {record.get('student_id') or 'Not provided'}"),
              p(f"Submission record: {rec_id}"),
              p(f"Submitted at: {record.get('submitted_at') or 'Not available'}"), Spacer(1, 9)]
    for si, (scenario, questions) in enumerate(answers.items()):
        story.append(p(scenario, 'ScenarioCustom'))
        if isinstance(questions, dict):
            for qi, (question, answer) in enumerate(questions.items()):
                comment = st.session_state.get(f'comment_{rec_id}_{si}_{qi}', '').strip()
                story.append(p(question, 'QuestionCustom'))
                story.append(p('Student answer: ' + (str(answer) if answer is not None and str(answer).strip() else '[No answer]'), 'AnswerCustom'))
                story.append(p('Teacher comment: ' + (comment or '[No comment]'), 'CommentCustom'))
        else:
            story.append(p(questions))
        scenario_comment = st.session_state.get(f'scenario_{rec_id}_{si}', '').strip()
        if scenario_comment:
            story.append(p('Scenario feedback: ' + scenario_comment, 'CommentCustom'))
        story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#d7dfe5')))
    story.append(p('Overall Teacher Feedback', 'ScenarioCustom'))
    story.append(p(st.session_state.get(f'overall_{rec_id}', '').strip() or '[No overall feedback]'))
    story.append(Spacer(1, 8))
    story.append(p('Marks / Grade: ' + (st.session_state.get(f'marks_{rec_id}', '').strip() or 'Not assigned')))
    doc.build(story)
    output.seek(0)
    return output.getvalue()

st.divider()
st.download_button('⬇ Download Reviewed Submission (PDF)', data=make_pdf(),
                   file_name=f"MAC_Tutorial4_Review_{rec_id}.pdf", mime='application/pdf',
                   type='primary', use_container_width=True)
st.warning('Comments are not saved to Supabase. Download the PDF before closing or refreshing this browser session. Keep this admin viewer access-restricted.')
