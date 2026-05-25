# Breathe ESG Intake Review Prototype

Django REST backend with a React analyst UI for ingesting SAP, utility, and corporate travel activity data, normalizing it, flagging suspicious rows, and approving or locking rows for audit.

## Live demo

**Temporary tunnel (while your machine is running the app):**  
https://drink-physiology-statewide-serve.trycloudflare.com

No login required. Use the reviewer selector in the sidebar to stamp audit events. Demo tenant **ACME Global Manufacturing** is pre-seeded with sample SAP, utility, and travel data.

For a permanent deployment, use Render (see below).

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

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/YOUR_USER/tech-intern-assignment-breathe-esg-context)

Replace the repo URL above after you push to GitHub.

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
