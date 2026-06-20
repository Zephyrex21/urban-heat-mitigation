"""
SHAP Explainability Module

Provides functions to compute and query SHAP values for
global and per-cell model explanations.

Since the model is now trained on combined data from every city,
grid_ids (e.g. "cell_0042") are NOT globally unique — every city's
grid starts numbering from cell_0000. All per-cell lookups therefore
require a city_id to disambiguate. Global feature importance is the
one exception: it reflects the model's overall learned behavior
across all cities and isn't filtered by city.
"""

import json
import pandas as pd

from pipeline.config import MODEL_DIR, SHAP_FILE, city_features_file

_shap_cache = None


def _load_shap_df():
    """Load the (city-spanning) SHAP values parquet, cached in-process."""
    global _shap_cache
    if _shap_cache is None:
        _shap_cache = pd.read_parquet(SHAP_FILE)
    return _shap_cache


def get_global_importance():
    """Get global feature importance ranking (shared across all cities)."""
    importance_file = MODEL_DIR / "feature_importance.json"
    if not importance_file.exists():
        return []
    with open(importance_file) as f:
        return json.load(f)


def get_cell_explanation(city_id: str, grid_id: str):
    """
    Get SHAP waterfall explanation for a single grid cell in a given city.

    Returns:
        dict with predicted LST, base value, and per-feature SHAP contributions,
        or None if the cell isn't found.
    """
    shap_df = _load_shap_df()
    features_df = pd.read_parquet(city_features_file(city_id))

    shap_row = shap_df[(shap_df["grid_id"] == grid_id) & (shap_df["city_id"] == city_id)]
    feat_row = features_df[features_df["grid_id"] == grid_id]

    if shap_row.empty or feat_row.empty:
        return None

    shap_row = shap_row.iloc[0]
    feat_row = feat_row.iloc[0]
    base_value = float(shap_row["base_value"])

    feature_cols = [c for c in shap_df.columns if c not in ("grid_id", "city_id", "base_value")]

    shap_values = []
    for col in feature_cols:
        if col in features_df.columns:
            shap_values.append({
                "feature": col,
                "value": float(feat_row[col]) if col in feat_row.index else 0,
                "shap": round(float(shap_row[col]), 4),
            })

    shap_values.sort(key=lambda x: abs(x["shap"]), reverse=True)

    predicted_lst = base_value + sum(sv["shap"] for sv in shap_values)

    return {
        "grid_id": grid_id,
        "city_id": city_id,
        "predicted_lst": round(predicted_lst, 2),
        "base_value": round(base_value, 2),
        "shap_values": shap_values[:15],  # top 15 features
    }


def get_top_drivers_for_hotspots(city_id: str):
    """
    Identify the primary heat drivers for hotspot cells in a given city.
    Returns aggregated SHAP importance for that city's critical/high tier
    cells only.
    """
    shap_df = _load_shap_df()
    features_df = pd.read_parquet(city_features_file(city_id))

    hotspot_ids = features_df[features_df["tier"].isin(["critical", "high"])]["grid_id"]
    hotspot_shap = shap_df[
        (shap_df["city_id"] == city_id) & (shap_df["grid_id"].isin(hotspot_ids))
    ]

    feature_cols = [c for c in shap_df.columns if c not in ("grid_id", "city_id", "base_value")]

    importance = {}
    for col in feature_cols:
        importance[col] = {
            "mean_abs_shap": round(float(hotspot_shap[col].abs().mean()), 4) if len(hotspot_shap) else 0.0,
            "mean_shap": round(float(hotspot_shap[col].mean()), 4) if len(hotspot_shap) else 0.0,
            "direction": "heating" if len(hotspot_shap) and hotspot_shap[col].mean() > 0 else "cooling",
        }

    sorted_importance = sorted(
        importance.items(),
        key=lambda x: x[1]["mean_abs_shap"],
        reverse=True
    )

    return [
        {"feature": k, **v}
        for k, v in sorted_importance[:10]
    ]
