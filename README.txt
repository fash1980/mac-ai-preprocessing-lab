COMPUTER NETWORKS LAB 4 — EXPLORATORY ANALYSIS

Files to upload into the ROOT of the existing GitHub repository:
  app3.py
  lab4_questions.json
  typed_answer/index.html    (preserve the folder)

Add "reportlab>=4.0" to the existing requirements.txt (do not overwrite other requirements).

Deploy as a SEPARATE app in Streamlit Community Cloud from the SAME GitHub repository:
  Main file path: app3.py
  App URL: choose e.g. computer-networks-lab4 (subject to availability)

To add a NEW LINK in existing MAC app.py, put these lines immediately after st.title(...):
  st.link_button('🌐 Computer Networks LAB 4 – Exploratory Analysis', 'https://YOUR-LAB4-APP-URL.streamlit.app')
Replace URL with the URL provided by Streamlit after the new app is deployed.
If you want a link in app2.py as well, add the same st.link_button there.

LOCAL TEST:
  pip install -r requirements_lab4.txt
  streamlit run app3.py

COPY/PASTE RESTRICTIONS:
Answer fields are provided by a local custom Streamlit component and block ordinary paste/copy/cut,
keyboard shortcuts, context-menu and drop inside those fields.
This is a best-effort client-side restriction, NOT a secure exam lockdown.
Question content outside the fields, OS screenshots, OCR, DevTools and retyping cannot be blocked reliably.

SUBMISSION:
Student enters name, ID, and all 21 typed answers.
The 'Submit answers & Download PDF' button downloads a professionally formatted student PDF.
The student uploads PDF to MyTimes. This does NOT write submissions to Supabase.
The existing MAC app.py and its Supabase integration remain unchanged.
