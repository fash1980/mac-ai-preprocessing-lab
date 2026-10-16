# Week 4 Practical Package

Two Google Colab notebooks (each 85–90 minutes):
- `Practical_Week4_Task1_Numerical.ipynb`: patient-like numerical data from built-in `sklearn` diabetes data, imputation, outliers, scaling, train–test leakage, pipeline.
- `Practical_Week4_Task2_Multimodal.ipynb`: built-in sklearn digit images, duplicates, blur, TF–IDF text and negation, synthetic sensor noise/smoothing. No download or internet dataset requests.

**Steps to deploy separate app:**
1. Upload both `.ipynb` files and `app2.py` plus `supabase_practical_setup.sql` to the ROOT of the existing GitHub `fash1980/mac-ai-preprocessing-lab` repository. Do not overwrite `app.py` or `scenarios.json`.
2. In the EXISTING Supabase project `MAC-AI-Preprocessing`, open SQL Editor; paste `supabase_practical_setup.sql` and Run. It adds table `practical_submissions` and private storage bucket `practical-evidence` without modifying tutorial tables.
3. At Streamlit Community Cloud, select **Create app → Deploy a public app from GitHub**. Choose **the same repository and main branch**, but set **Main file path = `app2.py`**, and choose an AVAILABLE DIFFERENT URL (e.g. `mac-week4-practical-submit`). This creates a distinct app URL independent of `app.py`.
4. For this NEW app, in its own Streamlit Cloud Settings > Secrets, insert the existing Supabase project's URL and SERVER-ONLY legacy service-role key as `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`. Never commit credentials to GitHub. Set them for EACH deployed app separately.
5. Upload notebooks to Google Colab (File > Upload notebook). Students enter student ID in each notebook, run cells, finish TODO exercises, and save 2–5 screenshots (including run token) per task.
6. Test with fictitious `TEST001`, upload 2 screenshots, 100+ word analysis, check `practical_submissions` and `Storage > practical-evidence`. Delete dummy record and files after testing.

**Screenshot transfer:** `st.file_uploader` supports uploaded screenshot files; it is NOT a native Ctrl+V clipboard-paste area. Students can use Windows Snipping Tool and save PNG then upload. Do not promise clipboard paste. Avoid collecting medical/patient personal information.

**Ethics & limits:** AI tools can still solve TODO cells, screenshots can be forged, IDs are unauthenticated, and server-side service-role writes warrant rate limits/auth for graded use. Add Taylor's SSO/authentication if available, and use short oral checks of a personalized result. The two notebook tasks are teaching resources, not hard anti-AI enforcement. The student-specific dataset is deterministic and must not be interpreted as secure identity verification.
