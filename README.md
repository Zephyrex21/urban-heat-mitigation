# Urban Heat Mitigation & Cooling Strategies MVP

> **AI-powered urban heat island analysis and cooling intervention simulator for 14 cities — 13 across India plus Phoenix, AZ**

## Quick Start

### Backend
```bash
cd urban-heat-mvp-work
python -m venv venv
venv\Scripts\Activate.ps1        # Windows PowerShell — on Mac/Linux: source venv/bin/activate
pip install -e ".[dev]"

# Generate synthetic demo data for every city (takes ~1 min)
python -m pipeline.generate_synthetic
# Or just one city, e.g.: python -m pipeline.generate_synthetic new_delhi

# Train the model — ONE shared model trained on all cities combined
# (takes a few minutes; computing SHAP values on ~50k rows is the slow part)
python -m models.train_hotspot

# Start API
uvicorn api.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

Pick a city from the dropdown in the sidebar — the map, drivers, and
scenario builder all update for whichever city is selected.

## Architecture

- **Backend**: Python 3.11 · FastAPI · XGBoost · SHAP · GeoPandas
- **Frontend**: React 19 · Vite · Deck.gl · Recharts · MapLibre GL JS
- **Storage**: GeoParquet flat files (zero infrastructure)

### Multi-city design

Every endpoint takes a `?city=<id>` query param (e.g. `new_delhi`,
`mumbai`, `phoenix` — see `GET /api/v1/cities` for the full list and
`pipeline/config.py`'s `CITIES` dict to add more). Grid, feature, and
preset-scenario data are generated and stored per city under
`data/processed/<city_id>/` and `data/scenarios/<city_id>/`.

The ML model itself is **shared across all cities** — one XGBoost
model trained on the combined data from every city, rather than 14
separate models. This means cross-validation uses a leave-cities-out
strategy (each fold holds out a few whole cities) rather than the
within-city spatial split a single-city version would use; it's a
more honest test of "would this generalize to a new city" than it is
a preview of in-production accuracy, since the deployed model has
already seen every served city's data directly.

## Pages

1. **Heat Map** — Interactive grid map with LST coloring and hotspot tiers
2. **Driver Analysis** — SHAP-based feature importance and per-cell explanations
3. **Scenario Builder** — Intervention sliders with split-view before/after map, plus preset scenarios that run through the same live simulation engine
