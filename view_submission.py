"""Teacher-only MAC Tutorial 4 review viewer.
Put contextual_feedback_review.json next to this file in GitHub.
Requires streamlit, supabase, reportlab and Streamlit Secrets.
Preliminary suggestions are NEVER auto-approved or written to Supabase.
"""
import json
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.platypus import Table, TableStyle
import streamlit as st
from supabase import create_client
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

st.set_page_config(page_title='MAC Tutorial 4 | Teacher Review', page_icon='📋', layout='wide')
st.title('Machine Learning Preprocessing Tutorial Week 4')
st.subheader('Teacher Review & Preliminary Feedback')
st.caption('Only the latest submission per student is shown. Scores and comments are preliminary until approved by the teacher. Reviews remain in this browser session.')

FEEDBACK_FILE = Path(__file__).parent / 'contextual_feedback_review.json'

@st.cache_resource
def get_client(url, key):
    return create_client(url, key)

@st.cache_data(ttl=120, show_spinner='Loading submissions...')
def fetch_submissions(url, key):
    db = get_client(url, key)
    records, start = [], 0
    while True:
        batch = (db.table('tutorial_submissions')
                 .select('id,student_id,student_name,answers,submitted_at')
                 .order('id').range(start, start + 499).execute()).data or []
        records.extend(batch)
        if len(batch) < 500:
            break
        start += 500
    return records

@st.cache_data
def load_feedback(file_contents):
    rows = json.loads(file_contents)
    return {str(row['submission_id']): row for row in rows}

try:
    url = st.secrets['SUPABASE_URL']
    key = st.secrets['SUPABASE_SERVICE_ROLE_KEY']
except (KeyError, FileNotFoundError):
    st.error('Configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in Streamlit Secrets.')
    st.stop()

if not FEEDBACK_FILE.exists():
    st.error('Missing contextual_feedback_review.json. Upload it to the same GitHub folder as this Python file.')
    st.stop()
try:
    feedback_by_id = load_feedback(FEEDBACK_FILE.read_bytes())
except (ValueError, KeyError, TypeError) as exc:
    st.error(f'Cannot read feedback JSON: {exc}')
    st.stop()

try:
    if st.sidebar.button('Refresh submissions'):
        fetch_submissions.clear()
    all_records = fetch_submissions(url, key)
except Exception as exc:
    st.error(f'Unable to load submissions: {exc}')
    st.stop()

if not all_records:
    st.info('No submissions found.')
    st.stop()

def submitted_key(row):
    # ISO UTC timestamps sort chronologically; ID breaks ties.
    return (str(row.get('submitted_at') or ''), int(row['id']) if str(row['id']).isdigit() else str(row['id']))

latest = {}
for row in all_records:
    sid = str(row.get('student_id') or '').strip()
    # Avoid merging different students whose ID is missing.
    group = sid if sid else f"missing-id-{row['id']}"
    if group not in latest or submitted_key(row) > submitted_key(latest[group]):
        latest[group] = row
records = sorted(latest.values(), key=lambda r: (str(r.get('student_name') or '').casefold(), str(r.get('student_id') or '')))

st.sidebar.metric('Unique students (latest)', len(records))
st.sidebar.metric('Preliminary grading records', len(feedback_by_id))
st.sidebar.info('No Supabase writes. Export an approved PDF before closing the session.')
search = st.text_input('Search student name or ID')
student_ids = sorted({str(r.get('student_id') or '') for r in records})
chosen_id = st.selectbox('Filter by student ID', ['All students'] + student_ids)
filtered = [r for r in records if
            (not search.strip() or search.casefold().strip() in str(r.get('student_name') or '').casefold()
             or search.casefold().strip() in str(r.get('student_id') or '').casefold())
            and (chosen_id == 'All students' or str(r.get('student_id') or '') == chosen_id)]
if not filtered:
    st.warning('No matching records.')
    st.stop()

current_ids = [str(r['id']) for r in filtered]
if st.session_state.get('review_record_id') not in current_ids:
    st.session_state.review_record_id = current_ids[0]
index = current_ids.index(st.session_state.review_record_id)

def navigate(delta):
    pos = current_ids.index(st.session_state.review_record_id)
    st.session_state.review_record_id = current_ids[max(0, min(len(current_ids) - 1, pos + delta))]

left, middle, right = st.columns([1, 2, 1])
with left:
    st.button('← Previous student', on_click=navigate, args=(-1,), disabled=index == 0, use_container_width=True)
with middle:
    st.markdown(f'<p style="text-align:center"><b>Student {index+1} of {len(filtered)}</b></p>', unsafe_allow_html=True)
with right:
    st.button('Next student →', on_click=navigate, args=(1,), disabled=index == len(filtered)-1, use_container_width=True)

record = filtered[index]
rec_id = str(record['id'])
grade = feedback_by_id.get(rec_id)
st.divider()
a, b, c = st.columns([2, 1, 1])
a.markdown(f"**Student:** {record.get('student_name') or 'Not provided'}")
b.markdown(f"**ID:** {record.get('student_id') or 'Not provided'}")
c.markdown(f"**Record:** {rec_id}")
st.caption(f"Submitted: {record.get('submitted_at') or 'Not available'}")
if not grade:
    st.warning('No preliminary feedback found for this submission ID. This may be a newer submission than the grading export. Do not use feedback from an older record.')
else:
    st.info('Preliminary grading loaded for this exact submission ID. Please verify suggested scores and comments before approving.')

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
num_answered = sum(bool(str(ans).strip()) for v in answers.values() if isinstance(v, dict) for ans in v.values() if ans is not None)
st.progress(num_answered / num_questions if num_questions else 0, text=f'Student answers: {num_answered} / {num_questions}')

# Keys use exact question text, not iteration position, so JSONB order changes won't misplace comments.
def widget_key(kind, scenario='', question=''):
    import hashlib
    raw = json.dumps([rec_id, kind, scenario, question], ensure_ascii=False)
    return kind + '_' + hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]

review_rows = []
for scenario, questions in answers.items():
    with st.expander(str(scenario), expanded=True):
        grade_scenario = (grade or {}).get('scenarios', {}).get(scenario, {})
        if isinstance(questions, dict):
            for question, answer in questions.items():
                st.markdown(f'**{question}**')
                st.write(str(answer) if answer is not None and str(answer).strip() else 'No answer submitted.')
                suggestion = grade_scenario.get(question, {})
                score_key = widget_key('score', scenario, question)
                comment_key = widget_key('comment', scenario, question)
                approve_key = widget_key('approved', scenario, question)
                if score_key not in st.session_state:
                    st.session_state[score_key] = int(suggestion.get('suggested_score_out_of_2', 0)) if suggestion else 0
                if comment_key not in st.session_state:
                    st.session_state[comment_key] = str(suggestion.get('feedback_draft') or '')
                if approve_key not in st.session_state:
                    st.session_state[approve_key] = False
                if suggestion:
                    st.caption('Preliminary rubric evidence: ' + (', '.join(suggestion.get('rubric_evidence') or []) or 'Not detected'))
                else:
                    st.warning('No matching grading entry for this question. Manual review required.')
                sc, approved_col = st.columns([1, 2])
                with sc:
                    st.selectbox('Suggested / edited marks (out of 2)', [0, 1, 2], key=score_key)
                with approved_col:
                    st.checkbox('Teacher reviewed and approved', key=approve_key)
                st.text_area('Editable feedback', key=comment_key, height=85,
                             placeholder='Teacher comment...')
                review_rows.append({'scenario': scenario, 'question': question, 'answer': answer,
                                    'score_key': score_key, 'comment_key': comment_key, 'approved_key': approve_key})
                st.divider()
        else:
            st.write(questions)
        sk = widget_key('scenario', scenario)
        if sk not in st.session_state:
            st.session_state[sk] = ''
        st.text_area('Scenario feedback (optional)', key=sk, height=85)

approved = sum(bool(st.session_state[r['approved_key']]) for r in review_rows)
points = sum(int(st.session_state[r['score_key']]) for r in review_rows)
st.subheader('Overall Teacher Feedback')
st.write(f'**Suggested / edited total:** {points}/{2*len(review_rows)}  ·  **Teacher-approved questions:** {approved}/{len(review_rows)}')
overall_key = widget_key('overall')
if overall_key not in st.session_state:
    st.session_state[overall_key] = ''
st.text_area('Overall comments', key=overall_key, height=130)
if approved != len(review_rows):
    st.warning('Some questions have not been approved. Any downloaded PDF will be marked PRELIMINARY.')
else:
    st.success('All questions reviewed and approved for this student.')

# PDF is built from the current visible, editable review fields.
def make_pdf():
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=19*mm, leftMargin=19*mm,
                            topMargin=18*mm, bottomMargin=18*mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='ReportTitleCustom', parent=styles['Title'], fontSize=15, leading=19, spaceAfter=10))
    styles.add(ParagraphStyle(name='ScenarioCustom', parent=styles['Heading2'], fontSize=11, spaceBefore=12, spaceAfter=6))
    styles.add(ParagraphStyle(name='SmallCustom', parent=styles['BodyText'], fontSize=9, leading=13, spaceAfter=5))
    def p(value, style='SmallCustom'):
        return Paragraph(escape(str(value if value is not None else '')).replace('\n', '<br/>'), styles[style])
    status = 'APPROVED' if approved == len(review_rows) else 'PRELIMINARY — TEACHER REVIEW REQUIRED'
    story = [
        p('MAC Tutorial Week 4 — Reviewed Submission', 'ReportTitleCustom')
    ]
    
    student_details = [
        ['STATUS', status],
        ['STUDENT', str(record.get('student_name') or 'Not provided')],
        ['STUDENT ID', str(record.get('student_id') or 'Not provided')],
        ['SUBMISSION RECORD', rec_id],
        ['SUBMITTED', str(record.get('submitted_at') or '')],
        ['MARKS', f'{points}/{2*len(review_rows)}']
    ]
    
    info_table = Table(
        student_details,
        colWidths=[42*mm, 128*mm],
        hAlign='LEFT'
    )
    
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#EEF3F6')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#456681')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#172B4D')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('TOPPADDING', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
    ]))
    
    story.append(info_table)
    story.append(Spacer(1, 12))
    for scenario, questions in answers.items():
        story.append(p(scenario, 'ScenarioCustom'))
        if isinstance(questions, dict):
            for question, answer in questions.items():
                r = next((x for x in review_rows if x['scenario'] == scenario and x['question'] == question), None)
                if not r:
                    continue
                story.extend([
                    p(question),
                    p('Student answer: ' + (
                        str(answer) if answer is not None else '[No answer]'
                    )),
                    p(f"Marks: {st.session_state[r['score_key']]}/2")
                ])
                
                feedback_box = Table(
                    [
                        [p('Teacher comment: ' + (
                            st.session_state[r['comment_key']].strip()
                            or '[No comment]'
                        ))],
                        [p('Review status: ' + (
                            'Approved'
                            if st.session_state[r['approved_key']]
                            else 'Pending teacher approval'
                        ))]
                    ],
                    colWidths=[165*mm],
                    hAlign='LEFT'
                )
                
                feedback_box.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#EEF3F6')),
                    ('LEFTPADDING', (0, 0), (-1, -1), 12),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                    ('TOPPADDING', (0, 0), (-1, -1), 7),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]))

                story.append(feedback_box)
                story.append(Spacer(1, 10))
        scenario_comment = st.session_state.get(widget_key('scenario', scenario), '').strip()
        if scenario_comment:
            story.append(p('Scenario feedback: ' + scenario_comment))
        story.append(HRFlowable(width='100%', thickness=0.5, color=colors.lightgrey))
    story.append(p('Overall Teacher Feedback', 'ScenarioCustom'))
    story.append(p(st.session_state[overall_key].strip() or '[No overall feedback]'))
    doc.build(story)
    return output.getvalue()

st.divider()
st.download_button('⬇ Download Reviewed Submission (PDF)', data=make_pdf(),
                   file_name=f'MAC_Tutorial4_Review_{rec_id}.pdf', mime='application/pdf',
                   type='primary', use_container_width=True)
st.warning('Feedback is NOT saved to Supabase. This viewer uses a service-role key: keep the app private and restrict teacher/admin access. Never put that key in GitHub.')
