"""
Hotspot detection and clustering endpoint.
"""

import math
import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends

from pipeline.config import CITIES, TIER_COLORS, city_features_file
from api.deps import get_city_id

router = APIRouter(prefix="/api/v1/hotspots", tags=["hotspots"])


@router.get("")
async def get_hotspots(city_id: str = Depends(get_city_id)):
    """
    Returns clustered hotspot regions with summary statistics for a city.
    Uses DBSCAN to cluster contiguous hotspot cells.
    """
    df = pd.read_parquet(city_features_file(city_id))

    # City-wide stats
    mean_lst = float(df["lst_mean"].mean())
    std_lst = float(df["lst_mean"].std())
    hotspot_mask = df["tier"].isin(["critical", "high"])
    hotspot_cells = int(hotspot_mask.sum())

    city_stats = {
        "mean_lst": round(mean_lst, 2),
        "std_lst": round(std_lst, 2),
        "total_cells": len(df),
        "hotspot_cells": hotspot_cells,
        "hotspot_pct": round(hotspot_cells / len(df) * 100, 1),
    }

    # Cluster hotspot cells using DBSCAN
    from sklearn.cluster import DBSCAN

    hotspot_df = df[hotspot_mask].copy()

    if len(hotspot_df) == 0:
        return {"city_stats": city_stats, "clusters": []}

    coords = hotspot_df[["centroid_lon", "centroid_lat"]].values
    # Convert degrees to approximate meters for DBSCAN, using this
    # city's actual latitude for the lon->meters conversion factor
    # (cos(lat) varies a lot across cities — e.g. ~0.98 at Kochi's ~10°N
    # vs ~0.86 at Chandigarh's ~31°N — so a single fixed constant would
    # silently distort cluster shapes for most cities).
    _, center_lat = CITIES[city_id]["center"]
    m_per_deg_lon = 111320 * math.cos(math.radians(center_lat))
    coords_m = coords.copy()
    coords_m[:, 0] *= m_per_deg_lon
    coords_m[:, 1] *= 111320  # lat to meters (~constant everywhere)

    clustering = DBSCAN(eps=750, min_samples=2).fit(coords_m)
    hotspot_df["cluster"] = clustering.labels_

    # Build cluster summaries
    clusters = []
    # Try to load SHAP importance for primary driver
    try:
        from models.explain import get_global_importance
        importance = get_global_importance()
        top_driver = importance[0]["feature"] if importance else "frac_impervious"
    except Exception:
        top_driver = "frac_impervious"

    for cluster_id in sorted(hotspot_df["cluster"].unique()):
        if cluster_id == -1:
            continue  # skip noise points

        cluster_cells = hotspot_df[hotspot_df["cluster"] == cluster_id]

        clusters.append({
            "cluster_id": int(cluster_id),
            "cell_count": len(cluster_cells),
            "area_km2": round(len(cluster_cells) * 0.25, 2),
            "mean_lst": round(float(cluster_cells["lst_mean"].mean()), 2),
            "max_lst": round(float(cluster_cells["lst_mean"].max()), 2),
            "delta_above_mean": round(float(cluster_cells["lst_mean"].mean()) - mean_lst, 2),
            "primary_driver": top_driver,
            "priority_score": round(float(cluster_cells["priority_score"].mean()), 1),
            "centroid": [
                round(float(cluster_cells["centroid_lon"].mean()), 6),
                round(float(cluster_cells["centroid_lat"].mean()), 6),
            ],
            "grid_ids": cluster_cells["grid_id"].tolist(),
        })

    # Sort by priority score
    clusters.sort(key=lambda c: c["priority_score"], reverse=True)

    return {
        "city_stats": city_stats,
        "clusters": clusters,
    }
