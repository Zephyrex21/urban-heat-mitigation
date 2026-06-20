"""
Cooling Scenario Simulation Engine

Modifies feature vectors per intervention rules, re-predicts LST
using the trained model, and computes cooling deltas.
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path

from pipeline.config import (
    MODEL_FILE, SCALER_FILE, MODEL_DIR,
    INTERVENTIONS, city_features_file, city_presets_file
)


def load_model_and_data(city_id: str):
    """Load the (shared, multi-city) trained model + scaler, and this
    city's own feature data."""
    import xgboost as xgb
    import joblib

    model = xgb.XGBRegressor()
    model.load_model(str(MODEL_FILE))

    scaler = joblib.load(SCALER_FILE)

    features_df = pd.read_parquet(city_features_file(city_id))

    feature_names_file = MODEL_DIR / "feature_names.json"
    with open(feature_names_file) as f:
        feature_names = json.load(f)

    return model, scaler, features_df, feature_names


def apply_intervention(features: pd.DataFrame, intervention: str,
                       intensity: float, target_cells: list[str] = None) -> pd.DataFrame:
    """
    Apply a cooling intervention by modifying feature values.
    
    Args:
        features: DataFrame of grid cell features
        intervention: intervention key from INTERVENTIONS config
        intensity: 0.0 to 1.0 (fraction of maximum intervention)
        target_cells: list of grid_ids to modify (None = all hotspots)
    
    Returns:
        Modified features DataFrame
    """
    if intervention not in INTERVENTIONS:
        raise ValueError(f"Unknown intervention: {intervention}")

    modified = features.copy()
    config = INTERVENTIONS[intervention]

    # Determine target mask
    if target_cells:
        mask = modified["grid_id"].isin(target_cells)
    else:
        # Default: apply to hotspot cells
        mask = modified["tier"].isin(["critical", "high"])

    if mask.sum() == 0:
        return modified

    # Apply feature modifications
    for feature, max_delta in config["feature_mods"].items():
        if feature not in modified.columns:
            continue

        delta = max_delta * intensity

        if feature in ["solar_radiation"]:
            # Fractional modification
            modified.loc[mask, feature] *= (1 + delta)
        elif feature in ["dist_to_water"]:
            # Absolute modification (reduce distance)
            modified.loc[mask, feature] = np.clip(
                modified.loc[mask, feature] + delta, 50, 10000
            )
        else:
            # Additive modification, clamp to [0, 1] for fractions
            modified.loc[mask, feature] = np.clip(
                modified.loc[mask, feature] + delta, 0, 1
            )

    return modified


def simulate_scenario(city_id: str, interventions: dict[str, float],
                      target_cells: list[str] = None) -> dict:
    """
    Simulate a complete cooling scenario for one city, with one or more
    interventions.

    Args:
        city_id: which city's feature data to simulate on
        interventions: dict of {intervention_name: intensity}
        target_cells: optional list of grid_ids

    Returns:
        Scenario results dict with summary and per-cell details
    """
    model, scaler, features_df, feature_names = load_model_and_data(city_id)
    grid_ids = features_df["grid_id"].values

    # ─── Baseline prediction (always needed before we can even decide
    #     which cells count as "hotspots" right now) ───
    X_original = features_df[feature_names].fillna(0)
    X_orig_scaled = scaler.transform(X_original)
    lst_original = model.predict(X_orig_scaled)

    mean_lst_orig = lst_original.mean()
    std_lst_orig = lst_original.std()

    def classify(lst, mean, std):
        if lst > mean + 2 * std:
            return "critical"
        elif lst > mean + 1 * std:
            return "high"
        elif lst > mean:
            return "moderate"
        elif lst > mean - 1 * std:
            return "normal"
        else:
            return "cool"

    tiers_before = [classify(l, mean_lst_orig, std_lst_orig) for l in lst_original]

    # ─── Resolve the target-cell set ONCE, from this same baseline,
    #     so "which cells get modified" and "which cells count as
    #     hotspots" can never disagree with each other ───
    if target_cells:
        resolved_targets = list(target_cells)
    else:
        resolved_targets = [
            gid for gid, t in zip(grid_ids, tiers_before) if t in ("critical", "high")
        ]
    target_mask = np.isin(grid_ids, resolved_targets)
    n_target = int(target_mask.sum())

    # Apply all interventions using that exact same target set
    modified_df = features_df.copy()
    for intervention, intensity in interventions.items():
        modified_df = apply_intervention(modified_df, intervention, intensity, resolved_targets)

    # Re-predict on the modified features
    X_modified = modified_df[feature_names].fillna(0)
    X_mod_scaled = scaler.transform(X_modified)
    lst_modified = model.predict(X_mod_scaled)

    delta_t = lst_modified - lst_original
    tiers_after = [classify(l, mean_lst_orig, std_lst_orig) for l in lst_modified]

    hotspots_before = sum(1 for t in tiers_before if t in ["critical", "high"])
    hotspots_after = sum(1 for t in tiers_after if t in ["critical", "high"])

    # Cost estimate, based on the area actually targeted
    area_km2 = n_target * 0.25  # each cell is 0.25 km²
    total_cost = sum(
        INTERVENTIONS[k]["cost_per_km2_million"] * v * area_km2
        for k, v in interventions.items()
        if k in INTERVENTIONS
    )

    # Mean/max cooling computed ONLY over the targeted cells. Averaging
    # across the full city (most of which were never touched and have
    # delta_t == 0) drowns out the real per-cell effect of the
    # intervention, so we report the number that actually answers
    # "how much did the cells we intervened on cool down".
    delta_t_targeted = delta_t[target_mask] if n_target > 0 else delta_t

    # Build cell results (vectorized — avoids 10k+ row-by-row .iloc calls)
    cell_results = [
        {
            "grid_id": gid,
            "lst_before": round(float(lb), 2),
            "lst_after": round(float(la), 2),
            "delta_t": round(float(dt), 2),
            "tier_before": tb,
            "tier_after": ta,
        }
        for gid, lb, la, dt, tb, ta in zip(
            grid_ids, lst_original, lst_modified, delta_t, tiers_before, tiers_after
        )
    ]

    return {
        "summary": {
            "cells_modified": n_target,
            "mean_cooling_c": round(float(delta_t_targeted.mean()), 2),
            "max_cooling_c": round(float(delta_t_targeted.min()), 2),
            "hotspots_before": hotspots_before,
            "hotspots_after": hotspots_after,
            "hotspot_reduction_pct": round(
                (hotspots_before - hotspots_after) / max(hotspots_before, 1) * 100, 1
            ),
            "cost_estimate_m": round(total_cost, 1),
            "cost_efficiency_c_per_m": round(
                abs(float(delta_t_targeted.mean())) / max(total_cost, 0.1), 3
            ) if total_cost > 0 else 0,
        },
        "cell_results": cell_results,
    }


def load_preset_scenarios(city_id: str):
    """Load pre-computed scenario results for one city."""
    presets_file = city_presets_file(city_id)
    if not presets_file.exists():
        return []
    with open(presets_file) as f:
        return json.load(f)
