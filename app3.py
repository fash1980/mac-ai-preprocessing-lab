"""Cisco Lab 4 exploratory worksheet, standalone Streamlit entry point.
Run: streamlit run app3.py
Dependencies: streamlit, reportlab
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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether, HRFlowable
from streamlit.components.v1 import declare_component

ROOT = Path(__file__).parent
QUESTIONS = json.loads((ROOT / 'lab4_questions.json').read_text(encoding='utf-8'))
ANSWER_WIDGET = declare_component('lab4_typed_answer', path=str(ROOT / 'typed_answer'))
st.set_page_config(page_title='Computer Networks LAB 4 | Exploratory Analysis', page_icon='🌐', layout='wide')

st.markdown('''<style>
.block-container {max-width:1100px; padding-top:1.7rem}
[data-testid="stMarkdownContainer"] p {line-height:1.5}
.student-prompt{background:#eef5ff;padding:10px 14px;border-left:3px solid #326bbb;border-radius:4px}
.lab4-question *:not(textarea) {-webkit-user-select:none;user-select:none}
</style>''', unsafe_allow_html=True)

styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='LabTitle',parent=styles['Heading1'],fontSize=16,leading=20,spaceAfter=12,textColor=colors.HexColor('#153c68'),alignment=TA_CENTER))
styles.add(ParagraphStyle(name='LabSub',parent=styles['Normal'],fontSize=10,leading=15,spaceAfter=7))
styles.add(ParagraphStyle(name='LabSection',parent=styles['Heading2'],fontSize=12,leading=16,spaceBefore=13,spaceAfter=7,textColor=colors.HexColor('#174d87')))
styles.add(ParagraphStyle(name='LabQ',parent=styles['Heading3'],fontSize=10.5,leading=15,spaceAfter=5))
styles.add(ParagraphStyle(name='LabAnswer',parent=styles['Normal'],fontSize=9.5,leading=14,spaceAfter=12))

def make_pdf(name,student_id,group,answers):
    buf=BytesIO()
    doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=18*mm,bottomMargin=18*mm,title='Computer Networks Lab 4 Exploratory Analysis')
    story=[Paragraph('COMPUTER NETWORKS LAB 4',styles['LabTitle']),Paragraph('Exploratory Analysis — Student Submission',styles['LabTitle']),HRFlowable(width='100%',thickness=1,color=colors.HexColor('#c3d3e4')),Spacer(1,6*mm)]
    timestamp=datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M UTC')
    for label,val in [('Student name',name),('Student ID',student_id),('Group / section',group or 'Not specified'),('Generated',timestamp)]:
        story.append(Paragraph(f'<b>{escape(label)}:</b> {escape(val)}',styles['LabSub']))
    section=None
    for i,q in enumerate(QUESTIONS):
        if q['section']!=section:
            section=q['section'];story.append(Paragraph(escape(section),styles['LabSection']))
        response=escape(answers[i]).replace('\n','<br/>')
        question=Paragraph(escape(q['title'])+' — '+escape(q['question']),styles['LabQ'])
        answer=Paragraph('<b>Student answer:</b><br/>'+response,styles['LabAnswer'])
        story.append(KeepTogether([question,answer]))
    story.append(Paragraph('This document reproduces the answers entered by the student. It does not certify correctness or completion of the Packet Tracer .pka activity.',styles['LabSub']))
    def footer(canvas, doc):
        canvas.saveState();canvas.setFont('Helvetica',8);canvas.setFillColor(colors.grey)
        canvas.drawString(18*mm,11*mm,f'{student_id} | Computer Networks LAB 4')
        canvas.drawRightString(192*mm,11*mm,f'Page {doc.page}');canvas.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return buf.getvalue()

st.markdown("""
<div style="
    background-color: #12335B;
    border: 2px solid #0B2545;
    border-radius: 8px;
    padding: 20px;
    text-align: center;
    font-family: Arial, sans-serif;
    color: white;
    margin-bottom: 25px;
">
    <div style="font-size: 30px; font-weight: bold;">
        Computer Networks LAB 4
    </div>
    <div style="font-size: 24px; font-weight: 500; margin-top: 8px;">
        Exploratory Analysis
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div style="
    background-color: #F2F4F7;
    border: 1px solid #B5D0E0;
    border-left: 5px solid #176B9A;
    border-radius: 8px;
    padding: 18px 24px;
    font-family: Arial, sans-serif;
    font-size: 17px;
    color: #18324B;
    line-height: 1.9;
    margin-bottom: 20px;
">
    <div style="font-size: 20px; font-weight: bold; margin-bottom: 8px;">
        Lab Instructions
    </div>
    <ul style="margin: 0; padding-left: 25px;">
        <li>Use the actual <b>Edit Topologies.pka</b> activity to investigate every question.</li>
        <li>Type your observations into the provided answer fields.</li>
        <li>Copy Paste is disabled in this activity</li>
        <li>For all the answers you need to explore Edit Topologies.pka </b>.</li>
     </ul>
</div>
""", unsafe_allow_html=True)
with st.sidebar:
    st.header('Student details')
    student_name=st.text_input('Full name *',key='lab4_name')
    student_id=st.text_input('Student ID *',key='lab4_id')
    group=st.text_input('Practical Group',key='lab4_group')
    st.divider()
    st.markdown("""
<div style="font-family: Arial, sans-serif; font-size: 17px; line-height: 1.9;">

<b>Submission Instructions:</b>
<ul>
    <li>All questions must be answered before submission.</li>
    <li>Your completed answers will be automatically generated as a PDF.</li>
    <li>Download the generated PDF after completing the worksheet.</li>
    <li>Upload the PDF to <b>MyTimes</b> along with cicso .pkt file.</li>
</ul>

</div>
""", unsafe_allow_html=True)

with st.expander('Instructions — read before starting',expanded=True):
    st.markdown('''1. Open **Edit Topologies.pka** in Cisco Packet Tracer and save a working copy.
2. Switch between **Logical** and **Physical** views when required.
3. Explore each location, click its actual devices and record findings. **Do not guess unseen IP addresses.**
4. Answer all 21 questions in your own words. Write observed values and tests, not just device names.
5. Click **Submit answers & Download PDF** and upload the generated PDF to **MyTimes** alongside your completed `.pka` file, according to your instructor's directions.

**Note:** The activity instructions mention `192.168.20.5` for Office-Admin, but the topology notes label that address as the Network Controller. Verify the actual target IP in Packet Tracer before pinging.''')

st.image(str(ROOT / 'city_topology.png'),caption='City-level topology: Home, ISP, Library and Office (from the original activity)',use_container_width=False,width=680)
st.caption('Paste/copy is disabled inside the answer input widgets. Browser-level restrictions cannot prevent screenshots, retyping, external AI tools or developer-tool workarounds; instructor verification remains important.')

section_name=None
answers=[]
for i,q in enumerate(QUESTIONS):
    if q['section']!=section_name:
        section_name=q['section']; st.divider();st.header(section_name)
        if section_name=='B. Office Cluster':
            st.image(str(ROOT / 'office_topology.png'),caption='Original Office cluster view: investigate the actual configuration in Packet Tracer',use_container_width=True)
    with st.container(border=True):
        st.subheader(q['title'])
        st.markdown(q['question'])
        with st.expander('How to investigate in Packet Tracer'):
            for step_no,step in enumerate(q['steps'],1):st.write(f'{step_no}. {step}')
        st.caption(q['prompt'])
        value=ANSWER_WIDGET(key=f'lab4_answer_{i}',default='',placeholder=f'Type your findings for {q["title"]}...')
        answers.append((value or '').strip() if isinstance(value,str) else '')

answered=sum(bool(x) for x in answers)
st.divider()
st.progress(answered/len(QUESTIONS),text=f'Completed: {answered} / {len(QUESTIONS)} questions')
with st.container(border=True):
    st.subheader('Review & Submit')
    st.write(f'**Student:** {student_name or "Not entered"} | **ID:** {student_id or "Not entered"}')
    missing=[i+1 for i,x in enumerate(answers) if len(x)<25]
    if missing:st.warning('Write at least 25 characters for each answer. Incomplete: '+', '.join('Q'+str(i) for i in missing))
    ready=bool(student_name.strip() and student_id.strip() and not missing)
    if not ready:st.caption('Provide name, Student ID and all 21 responses to enable the download.')
    pdf_bytes=make_pdf(student_name.strip(),student_id.strip(),group.strip(),answers) if ready else b''
    safe_id=re.sub(r'[^A-Za-z0-9_-]+','_',student_id.strip())[:70]
    st.download_button('Submit answers & Download PDF',data=pdf_bytes,file_name=f'{safe_id}_Computer_Networks_LAB4_Exploratory_Analysis.pdf',mime='application/pdf',type='primary',disabled=not ready,use_container_width=True,on_click='ignore')
    st.caption('The PDF download is the submission artifact. This page does not upload your answers to MyTimes or certify server-side receipt. Upload the PDF yourself to MyTimes.')
