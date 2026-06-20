# 🌡️ Urban Heat Mitigation and cooling V1

AI-powered urban heat island analysis and cooling-intervention simulator — covering **14 cities** (13 across India + Phoenix, AZ).

*Status: V1 — actively being improved.*

## Live Demo

- 🌐 Frontend: _add your Vercel link here_
- ⚙️ API: _add your Render link here_

## Features

- **Heat Map** — interactive grid map (Deck.gl + MapLibre) showing land surface temperature and hotspot tiers
- **Driver Analysis** — SHAP-based explainability showing what's driving the heat in each grid cell
- **Scenario Builder** — simulate cooling interventions (tree cover, reflective roofs, etc.) with a live before/after split view

## Tech Stack

| | |
|---|---|
| **Backend** | FastAPI · XGBoost · SHAP · GeoPandas |
| **Frontend** | React · Vite · Deck.gl · MapLibre GL · Recharts |
| **Storage** | GeoParquet flat files — zero infrastructure |

## Run Locally

Data and a trained model are already included in this repo — no generation or training needed to run it.

**Backend**
```bash
python -m venv venv
venv\Scripts\Activate.ps1     # Windows. Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

**Frontend** (in a second terminal)
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` and pick a city from the sidebar.

## Project Structure

```
api/        FastAPI routes — grid, hotspots, drivers, scenarios
pipeline/   Synthetic data generation & feature engineering
models/     XGBoost training, SHAP explainability, trained artifacts
data/       Per-city processed grids & scenario presets
frontend/   React + Vite app
```

## How It Works

One shared XGBoost model is trained across all 14 cities (rather than 14 separate models), so cross-validation uses a leave-cities-out split — a fair test of generalizing to a new city, not a preview of in-production accuracy. Every API endpoint takes a `?city=<id>` query param; add a new city by extending `CITIES` in `pipeline/config.py`.