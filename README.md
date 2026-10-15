# MAC Machine Learning Preprocessing Pitfalls tutorial

Eight scenario-based analysis activities, taken from the finalized scenario question document. Includes simple interactive illustrations and short-answer entry. Until Supabase is connected, this is **practice mode**: responses are NOT stored permanently.

## Deploy
1. Upload all files in this folder to a GitHub repository.
2. Streamlit Community Cloud: create app from GitHub; main file `app.py`.
3. Supabase: new project -> SQL Editor -> run `supabase_setup.sql`.
4. In Streamlit Cloud, App settings -> Secrets, add:

```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "YOUR_SECRET_SERVER_KEY"
```

5. Reboot app and test ONE fake submission. Check it in Supabase Table Editor.

## Security / classroom readiness
- Never commit your Supabase keys. The service role is powerful and bypasses RLS. Only enter it in Streamlit Cloud's server-side secret settings.
- This prototype uses self-declared student IDs, not verified accounts. Not suitable for graded/high-stakes submissions without authentication, abuse controls, authorization, and institution-approved student-data handling.
- The app does not block paste. Browser-side paste blocking can be bypassed; use scenario-specific individualized analysis for academic integrity.
- This version requires completing all 8 scenarios before submitting. It does not autosave partial responses; refresh/session loss can discard answers.
- Review data retention, consent, access, and where data are hosted with institutional policy before student use.
