"""
XGBoost LST Prediction Model

Trains an XGBoost regressor to predict Land Surface Temperature (LST)
from urban morphology, land cover, and weather features.
Uses spatial cross-validation to prevent data leakage.

Usage:
    python -m models.train_hotspot
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path

from pipeline.config import (
    CITIES, MODEL_FILE, SCALER_FILE, MODEL_DIR,
    SHAP_FILE, city_features_file
)

# ─── Feature Configuration ──────────────────────────────────────

TARGET = "lst_mean"

FEATURE_COLS = [
    "frac_impervious", "frac_vegetation", "frac_bare_soil", "frac_water",
    "ndvi_mean", "ndvi_std", "ndbi_mean",
    "building_density", "building_height_mean", "road_density",
    "park_area_frac", "tree_canopy_frac",
    "dist_to_water", "water_area_frac",
    "air_temp_max", "wind_speed_mean", "solar_radiation",
    # NOTE: raw centroid_lon/centroid_lat are deliberately excluded.
    # With multiple cities, coordinates act as a near-perfect city
    # identifier (each city has its own climate baseline), so including
    # them let the model "cheat" by partly memorizing which city a cell
    # belongs to rather than learning physically meaningful urban-form
    # relationships — centroid_lat ended up the #1 SHAP driver, ahead of
    # vegetation/impervious surface, which isn't an actionable insight
    # for a city planner. air_temp_max already carries each city's
    # climate baseline as an interpretable feature instead.
    "veg_imperv_ratio", "green_deficit", "thermal_mass_proxy",
    "cooling_potential", "sky_view_factor",
]


def load_data():
    """Load and combine every city's feature table into one training set."""
    frames = []
    for city_id in CITIES:
        fpath = city_features_file(city_id)
        if not fpath.exists():
            print(f"  [WARN] No features file for '{city_id}' — skipping "
                  f"(run pipeline.generate_synthetic first)")
            continue
        city_df = pd.read_parquet(fpath)
        city_df["city_id"] = city_id
        frames.append(city_df)

    if not frames:
        raise FileNotFoundError(
            "No per-city features.parquet files found. Run "
            "`python -m pipeline.generate_synthetic` first."
        )

    df = pd.concat(frames, ignore_index=True)

    # Filter to available features
    available = [c for c in FEATURE_COLS if c in df.columns]
    missing = [c for c in FEATURE_COLS if c not in df.columns]
    if missing:
        print(f"  [WARN] Missing features: {missing}")

    X = df[available].copy()
    y = df[TARGET].copy()

    # Handle any NaN
    X = X.fillna(X.median())
    mask = ~y.isna()
    X = X[mask]
    y = y[mask]

    print(f"  Cities: {df['city_id'].nunique()}, Features: {X.shape[1]}, Samples: {X.shape[0]}")
    print(f"  Target range: {y.min():.1f}°C to {y.max():.1f}°C (mean: {y.mean():.1f}°C)")

    return X, y, df[mask]


def spatial_cv_split(df, n_splits=5):
    """
    Create leave-cities-out cross-validation splits: each fold holds out
    a different group of whole cities, training on the rest. This is a
    stronger generalization test than splitting by latitude band within
    a single city (the original approach), and is the natural fit now
    that cells come from multiple geographically disjoint cities — a
    pure latitude split would otherwise just separate, say, "northern
    Delhi" from "southern Mumbai" rather than testing whether the model
    generalizes to an unseen city at all.
    """
    cities = sorted(df["city_id"].unique())
    rng = np.random.RandomState(42)
    rng.shuffle(cities)
    city_folds = np.array_split(cities, min(n_splits, len(cities)))

    folds = []
    for fold_cities in city_folds:
        test_mask = df["city_id"].isin(fold_cities).values
        train_mask = ~test_mask
        folds.append((np.where(train_mask)[0], np.where(test_mask)[0]))

    return folds


def train_model(X, y, df):
    """Train XGBoost with spatial CV and evaluate."""
    import xgboost as xgb
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    import joblib

    # Scale features
    scaler = StandardScaler()
    X_scaled = pd.DataFrame(
        scaler.fit_transform(X),
        columns=X.columns,
        index=X.index
    )

    # Leave-cities-out CV
    folds = spatial_cv_split(df)
    cv_scores = {"rmse": [], "mae": [], "r2": []}

    print("\n  Leave-Cities-Out Cross-Validation:")
    for fold_idx, (train_idx, test_idx) in enumerate(folds):
        held_out = sorted(df.iloc[test_idx]["city_id"].unique())
        X_train, X_test = X_scaled.iloc[train_idx], X_scaled.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        model = xgb.XGBRegressor(
            n_estimators=500,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            min_child_weight=5,
            random_state=42,
            verbosity=0,
        )
        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False,
        )

        y_pred = model.predict(X_test)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)

        cv_scores["rmse"].append(rmse)
        cv_scores["mae"].append(mae)
        cv_scores["r2"].append(r2)
        print(f"    Fold {fold_idx + 1} (held out: {', '.join(held_out)}): "
              f"RMSE={rmse:.3f}°C, MAE={mae:.3f}°C, R²={r2:.4f}")

    print(f"\n  Mean CV Scores:")
    print(f"    RMSE: {np.mean(cv_scores['rmse']):.3f} ± {np.std(cv_scores['rmse']):.3f}°C")
    print(f"    MAE:  {np.mean(cv_scores['mae']):.3f} ± {np.std(cv_scores['mae']):.3f}°C")
    print(f"    R²:   {np.mean(cv_scores['r2']):.4f} ± {np.std(cv_scores['r2']):.4f}")

    # Train final model on all data
    print("\n  Training final model on all data...")
    final_model = xgb.XGBRegressor(
        n_estimators=500,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        min_child_weight=5,
        random_state=42,
        verbosity=0,
    )
    final_model.fit(X_scaled, y)

    # Save model and scaler
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    final_model.save_model(str(MODEL_FILE))
    joblib.dump(scaler, SCALER_FILE)

    # Save feature names
    feature_names_file = MODEL_DIR / "feature_names.json"
    with open(feature_names_file, "w") as f:
        json.dump(list(X.columns), f)

    # Save CV scores
    scores_file = MODEL_DIR / "cv_scores.json"
    with open(scores_file, "w") as f:
        json.dump({k: [float(v) for v in vals] for k, vals in cv_scores.items()}, f, indent=2)

    print(f"\n  Model saved → {MODEL_FILE.name}")
    print(f"  Scaler saved → {SCALER_FILE.name}")

    return final_model, scaler, X_scaled


def compute_shap_values(model, X_scaled, df):
    """Compute SHAP values for model explainability."""
    try:
        import shap
    except ImportError:
        print("  [SKIP] SHAP not installed")
        return

    print("\n  Computing SHAP values...")
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_scaled)

    # Save SHAP values
    shap_df = pd.DataFrame(shap_values, columns=X_scaled.columns)
    shap_df["grid_id"] = df["grid_id"].values
    shap_df["city_id"] = df["city_id"].values
    shap_df["base_value"] = explainer.expected_value
    shap_df.to_parquet(SHAP_FILE, index=False)

    # Global feature importance
    mean_abs_shap = np.abs(shap_values).mean(axis=0)
    importance = sorted(
        zip(X_scaled.columns, mean_abs_shap),
        key=lambda x: x[1], reverse=True
    )

    print("\n  Global Feature Importance (SHAP):")
    for feat, imp in importance[:10]:
        bar = "█" * int(imp / importance[0][1] * 30)
        print(f"    {feat:25s} {bar} {imp:.4f}")

    # Save importance
    importance_file = MODEL_DIR / "feature_importance.json"
    importance_data = [
        {
            "feature": feat,
            "importance": round(float(imp), 4),
            "direction": "positive" if np.corrcoef(
                X_scaled[feat].values, shap_values[:, list(X_scaled.columns).index(feat)]
            )[0, 1] > 0 else "negative"
        }
        for feat, imp in importance
    ]
    with open(importance_file, "w") as f:
        json.dump(importance_data, f, indent=2)

    print(f"\n  SHAP values saved → {SHAP_FILE.name}")


def run():
    """Full training pipeline."""
    print("=" * 60)
    print("  Training XGBoost LST Prediction Model")
    print("=" * 60)

    # Load data
    print("\n[1/3] Loading data...")
    X, y, df = load_data()

    # Train
    print("\n[2/3] Training model...")
    model, scaler, X_scaled = train_model(X, y, df)

    # SHAP
    print("\n[3/3] Computing explainability...")
    compute_shap_values(model, X_scaled, df)

    print("\n" + "=" * 60)
    print("  Training complete!")
    print("=" * 60)


if __name__ == "__main__":
    run()
