# Breathe ESG Intake Review Prototype

Django REST backend with a React analyst UI for ingesting SAP, utility, and corporate travel activity data, normalizing it, flagging suspicious rows, and approving or locking rows for audit.

## Live demo (online — Render)

**GitHub repo:** https://github.com/JaswanthPolarowthu07/breathe-esg-intake

**One-click deploy to Render (permanent URL):**  
https://render.com/deploy?repo=https://github.com/JaswanthPolarowthu07/breathe-esg-intake

1. Sign in to Render (GitHub login is fine).
2. Click **Apply** on the Blueprint (uses `render.yaml` — web service + PostgreSQL).
3. Wait ~5–8 minutes for the first build.
4. Open your app at `https://breathe-esg-intake.onrender.com` (or the URL Render shows in the dashboard).

No login required in the app. Demo tenant **ACME Global Manufacturing** is seeded on first boot.

## Local run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo --with-samples
python manage.py runserver
```

Open `http://127.0.0.1:8000/`.

## Deployment (Render)

The repo includes `render.yaml`, `build.sh`, `Procfile`, and `runtime.txt`.

1. Push this repository to GitHub.
2. In [Render](https://render.com), create a **Blueprint** from the repo (or a **Web Service** + **PostgreSQL** using `render.yaml`).
3. Render runs migrations and `seed_demo --if-empty` on first boot, then serves the app with Gunicorn.
4. Health check: `/api/health/`

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/JaswanthPolarowthu07/breathe-esg-intake)

## Documentation

- `MODEL.md` — data model and tenancy/audit design
- `DECISIONS.md` — source subsets and ambiguity resolutions
- `TRADEOFFS.md` — deliberate omissions
- `SOURCES.md` — real-world format research and sample data rationale

## Sample files

Download from the Intake tab or directly:

- `/api/samples/sap/download/`
- `/api/samples/utility/download/`
- `/api/samples/travel/download/`

Bundled paths:

- `sample_data/sap_material_procurement_export.csv`
- `sample_data/utility_portal_greenbutton_like.csv`
- `sample_data/concur_travel_export.json`
