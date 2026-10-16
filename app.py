import json
from datetime import datetime, timezone
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
typing_input = components.declare_component(
    "typing_input",
    path=str(Path(__file__).parent / "typing_input")
)
st.set_page_config(
    page_title="Tutorial 4 AAI | Data Wrangling",
    page_icon="preprocessing_icon.png.jpg",
    layout="wide"
)
SCENARIOS = json.loads((Path(__file__).parent / 'scenarios.json').read_text(encoding='utf-8'))

st.title("Machine Learning Preprocessing Tutorial Week 4")


@st.cache_resource
def database_client(url, secret):
    from supabase import create_client
    return create_client(url, secret)

def database_ready():
    try:
        return bool(st.secrets['SUPABASE_URL'] and st.secrets['SUPABASE_SERVICE_ROLE_KEY'])
    except (KeyError, FileNotFoundError):
        return False

if not database_ready():
    st.warning("Practice mode: database not connected. Responses will NOT be stored permanently. Connect Supabase before classroom use.")

with st.sidebar:
    st.header("Student details")
    student_id = st.text_input("Student ID", placeholder="e.g., 0123456", key='student_id')
    student_name = st.text_input("Name", key='student_name')
    st.divider()
    selection = st.radio("Choose a scenario", options=list(range(len(SCENARIOS))), format_func=lambda i: f"Scenario {i+1}")
    

scenario = SCENARIOS[selection]
st.subheader(scenario['title'])
st.write(scenario['description'])
if scenario['table']:
    st.dataframe(pd.DataFrame(scenario['table'][1:],columns=scenario['table'][0]),hide_index=True,use_container_width=True)

# Interactive illustrations accompany, not replace, the exact scenario questions.
if selection == 0:
    st.caption("Explore glucose imputation sensitivity; the extreme value should be investigated rather than assumed erroneous.")
    readings = np.array([180,150,900,110], dtype=float)
    method = st.selectbox("Compare glucose imputation method", ["Mean", "Median"], key='imputation')
    estimate = float(readings.mean() if method=='Mean' else np.median(readings))
    st.metric("Estimated P02 glucose", f"{estimate:.1f}")
    st.caption("Please remember that this activity is for demonstration purposes only. In actual machine learning model development, imputation should be fitted using the training data only to prevent data leakage and ensure reliable model evaluation.")
elif selection == 1:
    st.caption("Explore the effect of scaling on transaction amounts.")
    amounts = np.array([100,150,200,250,10000],dtype=float)
    choice=st.selectbox("Scaling",["Original", "Min–Max", "Robust (median / IQR)"],key='scaling')
    if choice=='Min–Max': values=(amounts-amounts.min())/(amounts.max()-amounts.min())
    elif choice.startswith('Robust'):
        q25,q75=np.quantile(amounts,[.25,.75]); values=(amounts-np.median(amounts))/(q75-q25)
    else: values=amounts
    st.bar_chart(pd.DataFrame({'Account':list('ABCDE'),'Value':values}).set_index('Account'))
    
elif selection == 2:
    st.caption("PIID pressure-injury images. I2 is artificially blurred; I3 is an exact copy; I4 has an intentionally incorrect teaching label. Not for clinical interpretation.")
    image_dir = Path(__file__).parent / "scenario3_images"
    image_files = [
        "I1_reference.jpg",
        "I2_blurred.jpg",
        "I3_duplicate.jpg",
        "I4_wrong_label.jpg",
    ]
    captions = [
        "I1 — Reference image (PIID, stage 1 filename)",
        "I2 — Artificially blurred copy of I1",
        "I3 — Exact duplicate of I1 (different filename)",
        "I4 — Different PIID image (stage 3 filename), deliberately mislabelled 'stage 1' for this exercise",
    ]
    cols = st.columns(4)
    for col, filename, caption in zip(cols, image_files, captions):
        with col:
            st.image(str(image_dir / filename), caption=caption, use_container_width=True)
elif selection == 3:
    t=np.linspace(0,2,320)
    clean=np.sin(2*np.pi*4*t)+0.45*np.exp(-((t-1.06)/.035)**2)
    rng=np.random.default_rng(2026)
    noisy=clean+rng.normal(0,.30,t.shape)
    span=st.slider("Smoothing window",3,71,29,2)
    filtered=np.convolve(noisy,np.ones(span)/span,mode='same')
    fig=go.Figure()
    for x,label in [(clean,'Clean (synthetic)'),(noisy,'Noisy (synthetic)'),(filtered,'Smoothed')]:fig.add_trace(go.Scatter(x=t,y=x,name=label,mode='lines'))
    fig.update_layout(height=310,xaxis_title='Time (s)',yaxis_title='Amplitude (a.u.)')
    st.plotly_chart(fig,use_container_width=True)
    st.caption('Synthetic educational signals, not actual EEG recordings.')
elif selection == 4:
    st.caption('The cosine-similarity scores in the table are provided for reasoning. They are illustrative, not computed by a live embedding model.')
    st.info('Compare T1/T2/T3 by the stated scores, then consider the effect of removing negation or preprocessing pretrained embeddings.')
    
    st.info("""
    **Understanding Cosine Similarity**

    Text embeddings convert sentences into numerical vectors
    representing their meaning.

    Cosine similarity measures the similarity between two
    vectors based on the angle between them.

    **How to interpret the scores:**
    - Close to 1: Very similar meaning
    - Close to 0: Little or no semantic similarity
    - Close to -1: Opposite vector directions
      (not necessarily opposite meanings)

    **Example from the table:**
    - T1 (0.92): High similarity
    - T2 (0.41): Lower similarity
    - T3 (0.86): High similarity despite being in Malay

    **Note:** A higher score suggests greater semantic
    similarity, but does not guarantee identical meaning.
    """)

elif selection == 5:
    st.caption('Compare workflow orders: train-set-only fitting vs full-dataset preprocessing.')
    st.code('Incorrect: entire dataset → impute / scale → row-wise split → train / evaluate\nCorrect: patient-wise split → fit imputer and scaler on training data → transform test → evaluate',language='text')
elif selection == 6:
    st.caption('Prediction-time audit: select which inputs are actually available before the fraud decision.')
    st.info('The investigation outcome is entered two days later. Transaction counts should use only history up to the prediction time.')
elif selection == 7:
    chart=pd.DataFrame({'Model':['A','B'],'Training':[94,99],'Validation':[91,96],'Final test':[89,73]}).set_index('Model')
    st.bar_chart(chart)
    st.caption('Illustrative model accuracies; differences alone do not prove leakage or overfitting.')

st.divider()
st.markdown('#### Type your analysis')
for j, question in enumerate(scenario['questions']):
    st.markdown(f'**{question}**')
    answer_key = f'answer_{selection}_{j}'

    typed = typing_input(
        value=st.session_state.get(answer_key, ''),
        key=f'custom_{answer_key}',
        default=st.session_state.get(answer_key, '')
    )

    if typed is not None:
        st.session_state[answer_key] = typed

answers={s['title']:{q:st.session_state.get(f'answer_{i}_{j}','').strip() for j,q in enumerate(s['questions'])} for i,s in enumerate(SCENARIOS)}
answered=sum(bool(a) for v in answers.values() for a in v.values())
total=sum(len(s['questions']) for s in SCENARIOS)
st.progress(answered/total,text=f'Questions answered: {answered} / {total}')

with st.expander('Review and submit'):
    st.write('Student ID:',student_id or '(missing)')
    st.write('Name:',student_name or '(missing)')
    st.write('Completed answers:',answered,'/',total)
    if answered != total:
        st.warning('Complete all scenario questions before submitting.')
    if not database_ready():
        st.info('Submission disabled until Supabase credentials are configured. You can still test the activities.')
    if st.button('Submit all answers',type='primary',disabled=(not database_ready() or not student_id.strip() or not student_name.strip() or answered != total)):
        payload={'student_id':student_id.strip(),'student_name':student_name.strip(),'answers':answers,'submitted_at':datetime.now(timezone.utc).isoformat()}
        try:
            db=database_client(st.secrets['SUPABASE_URL'],st.secrets['SUPABASE_SERVICE_ROLE_KEY'])
            db.table('tutorial_submissions').insert(payload).execute()
            st.success('Your answers were submitted successfully.')
            st.session_state['submitted']=True
        except Exception:
            st.error('Submission failed. Inform your tutor; the answers have not been confirmed as saved.')


