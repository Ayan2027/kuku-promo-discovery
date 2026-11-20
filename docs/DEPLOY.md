# Deploy the prototype

The repository ships two prototypes:

1. `prototype/index.html` — self-contained static demo. No server, no data files, no input pack.
2. `app.py` — Streamlit human-triage app. Falls back to `demo/` when real outputs are absent.

## Option A — open the static prototype

Double-click `prototype/index.html`, or serve the folder:

```powershell
python -m http.server 8000
# open http://localhost:8000/prototype/
```

For a public link, push the repository to GitHub and enable **Settings → Pages → Deploy from branch → main / (root)**. The prototype is then at:

```
https://<your-user>.github.io/<repo>/prototype/
```

The static prototype contains only synthetic demo data, so this is the safest public link.

## Option B — Streamlit Community Cloud

1. Push the repository to GitHub. Do **not** commit `data/input/`, `data/processed/`, `data/exports/` or `raw_outputs/`.
2. Go to <https://share.streamlit.io>, create an app, and select `app.py` as the main file.
3. Add secrets only if you want the AI path:
   ```toml
   AI_PROVIDER = "gemini"
   GEMINI_API_KEY = "..."
   ```
   Otherwise leave `AI_PROVIDER=local`; the app uses the deterministic fallback.
4. Deploy. The app will use `demo/` because the real outputs are not in the public repo.

## Option C — Docker

```powershell
docker build -t kuku-promo-demo .
docker run --rm -p 8501:8501 kuku-promo-demo
# open http://localhost:8501
```

The Dockerfile sets `DEMO_MODE=1` and `AI_PROVIDER=local` by default.

## What not to deploy

- `data/input/` — confidential input pack.
- `data/processed/`, `data/exports/`, `raw_outputs/` — contain screenplay excerpts.
- `.env` — secrets.

The evaluator can receive those folders through the private submission archive (`submission/Kuku_Problem1_Submission.zip`).
