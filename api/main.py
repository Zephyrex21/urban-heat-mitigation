"""
FastAPI application entrypoint for the Urban Heat MVP.
"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

from pipeline.config import CITIES, DEFAULT_CITY, list_cities, city_features_file
from api.deps import get_city_id
from api.routers import grid, hotspots, drivers, scenarios
from api.schemas import OverviewResponse

app = FastAPI(
    title="Urban Heat MVP API",
    description="API for the Urban Heat Mitigation & Cooling Strategies MVP",
    version="1.0.0",
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://urban-heat-mitigation-mu.vercel.app",
        "http://localhost:5173",                            # keep this so local dev still works
    ],                                                     
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(grid.router)
app.include_router(hotspots.router)
app.include_router(drivers.router)
app.include_router(scenarios.router)


@app.get("/api/v1/cities", tags=["overview"])
async def get_cities():
    """
    Returns every city available in the demo, for the frontend's city
    picker. Includes the default city id so the frontend knows which
    one to select on first load.
    """
    return {
        "default_city": DEFAULT_CITY,
        "cities": list_cities(),
    }


@app.get("/api/v1/overview", response_model=OverviewResponse, tags=["overview"])
async def get_overview(city_id: str = Depends(get_city_id)):
    """
    Returns high-level KPI metrics for the city overview.
    """
    city = CITIES[city_id]
    df = pd.read_parquet(city_features_file(city_id))

    hotspot_mask = df["tier"].isin(["critical", "high"])
    hotspot_count = int(hotspot_mask.sum())

    mean_lst = float(df["lst_mean"].mean())

    # Try to load global importance for top driver
    try:
        from models.explain import get_global_importance
        importance = get_global_importance()
        top_driver = importance[0]["feature"] if importance else "frac_impervious"
    except Exception:
        top_driver = "frac_impervious"

    return {
        "city": f"{city['name']}, {city['state']}",
        "analysis_period": city["season_label"],
        "grid_cells": len(df),
        "mean_lst_c": round(mean_lst, 2),
        "max_lst_c": round(float(df["lst_max"].max()), 2),
        "min_lst_c": round(float(df["lst_mean"].min()), 2),
        "std_lst_c": round(float(df["lst_mean"].std()), 2),
        "uhi_intensity_c": round(float(df["lst_mean"].max()) - mean_lst, 2),
        "hotspot_area_km2": round(hotspot_count * 0.25, 2),
        "hotspot_count": hotspot_count,
        "top_driver": top_driver,
        "best_intervention": "Tree Cover (+20%)",  # Static for demo, could be dynamic
        "max_potential_cooling_c": -4.5,
        "tier_distribution": df["tier"].value_counts().to_dict(),
    }


@app.get("/health", tags=["system"])
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}
