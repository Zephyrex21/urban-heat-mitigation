"""
Step 07: Feature Engineering

Assembles the final feature table by joining all data sources
to the analysis grid. Computes derived and interaction features.
Outputs a single Parquet file ready for ML training.
"""

import numpy as np
import pandas as pd
from pathlib import Path

from pipeline.config import (
    PROCESSED_DIR, FEATURES_FILE, GRID_FILE, HOTSPOT_TIERS
)


def compute_zonal_stats(raster_path: Path, grid_gdf, stat: str = "mean") -> np.ndarray:
    """
    Compute zonal statistics of a raster within each grid cell.
    
    Args:
        raster_path: path to GeoTIFF
        grid_gdf: GeoDataFrame with grid cells
        stat: 'mean', 'max', 'std', 'median'
    
    Returns:
        Array of statistic values, one per grid cell
    """
    try:
        import rasterio
        from rasterio.mask import mask as rio_mask
    except ImportError:
        return np.full(len(grid_gdf), np.nan)

    values = []
    with rasterio.open(raster_path) as src:
        for _, cell in grid_gdf.iterrows():
            try:
                out_image, _ = rio_mask(src, [cell.geometry], crop=True, nodata=np.nan)
                pixels = out_image[0][~np.isnan(out_image[0])]
                if len(pixels) == 0:
                    values.append(np.nan)
                elif stat == "mean":
                    values.append(np.mean(pixels))
                elif stat == "max":
                    values.append(np.max(pixels))
                elif stat == "std":
                    values.append(np.std(pixels))
                elif stat == "median":
                    values.append(np.median(pixels))
            except Exception:
                values.append(np.nan)

    return np.array(values)


def compute_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute interaction and derived features from base features.
    """
    eps = 0.01

    # Vegetation-to-impervious ratio
    df["veg_imperv_ratio"] = df["frac_vegetation"] / (df["frac_impervious"] + eps)

    # Green deficit: how far from ideal green coverage
    df["green_deficit"] = 1.0 - df["frac_vegetation"] - df["park_area_frac"]
    df["green_deficit"] = df["green_deficit"].clip(lower=0)

    # Thermal mass proxy
    df["thermal_mass_proxy"] = df["building_density"] * df["building_height_mean"]

    # Cooling potential: areas with high solar load and low vegetation
    df["cooling_potential"] = (1 - df["frac_vegetation"]) * df["solar_radiation"]

    # Sky view factor estimate (simplified)
    max_height = df["building_height_mean"].max()
    if max_height > 0:
        df["sky_view_factor"] = 1.0 - (df["building_height_mean"] / max_height) * 0.5
    else:
        df["sky_view_factor"] = 1.0

    return df


def compute_spatial_lag(df: pd.DataFrame, grid_gdf, features: list[str]) -> pd.DataFrame:
    """
    Compute spatial lag features (mean of neighboring cells).
    Uses queen contiguity (adjacent cells including diagonals).
    """
    try:
        from shapely.strtree import STRtree
    except ImportError:
        return df

    tree = STRtree(grid_gdf.geometry.values)
    
    for feat in features:
        lag_values = []
        for idx, cell in grid_gdf.iterrows():
            # Buffer slightly to catch neighbors
            buffered = cell.geometry.buffer(1)  # tiny buffer for touching
            neighbor_idxs = tree.query(buffered)
            # Exclude self
            neighbor_idxs = [i for i in neighbor_idxs if i != idx]
            if neighbor_idxs:
                lag_values.append(df.iloc[neighbor_idxs][feat].mean())
            else:
                lag_values.append(df.iloc[idx][feat])
        df[f"{feat}_lag"] = lag_values

    return df


def assign_hotspot_tiers(df: pd.DataFrame, target_col: str = "lst_mean") -> pd.DataFrame:
    """
    Classify each grid cell into a hotspot tier based on LST.
    """
    mean_lst = df[target_col].mean()
    std_lst = df[target_col].std()

    def classify(lst):
        if lst > mean_lst + 2 * std_lst:
            return "critical"
        elif lst > mean_lst + 1 * std_lst:
            return "high"
        elif lst > mean_lst:
            return "moderate"
        elif lst > mean_lst - 1 * std_lst:
            return "normal"
        else:
            return "cool"

    df["tier"] = df[target_col].apply(classify)
    df["delta_above_mean"] = df[target_col] - mean_lst

    # Priority score: intensity × (1 / green fraction)
    df["priority_score"] = (
        df["delta_above_mean"].clip(lower=0) *
        (1.0 / (df["frac_vegetation"] + 0.01))
    )
    # Normalize to 0-10
    max_ps = df["priority_score"].max()
    if max_ps > 0:
        df["priority_score"] = (df["priority_score"] / max_ps * 10).round(1)

    return df


def run():
    """Assemble the final feature table."""
    print("[Step 07] Building feature table...")

    try:
        import geopandas as gpd
    except ImportError:
        print("  [SKIP] geopandas not installed")
        return

    # Load grid
    if not GRID_FILE.exists():
        print("  [ERROR] Grid file not found — run step 06 first")
        return
    grid = gpd.read_file(GRID_FILE)

    # Start building features DataFrame
    df = pd.DataFrame({"grid_id": grid["grid_id"]})
    df["centroid_lon"] = grid["centroid_lon"]
    df["centroid_lat"] = grid["centroid_lat"]

    # LST from composite raster
    lst_file = PROCESSED_DIR / "lst_composite.tif"
    if lst_file.exists():
        df["lst_mean"] = compute_zonal_stats(lst_file, grid, "mean")
        df["lst_max"] = compute_zonal_stats(lst_file, grid, "max")
    else:
        print("  [WARN] No LST composite — features will be incomplete")

    # LULC fractions
    lulc_file = PROCESSED_DIR / "lulc_classified.tif"
    if lulc_file.exists():
        # Compute per-class fractions via zonal stats on binary masks
        pass  # Already handled in step 03

    # Load any pre-computed feature files
    osm_features_file = PROCESSED_DIR / "osm_features.parquet"
    if osm_features_file.exists():
        osm_df = pd.read_parquet(osm_features_file)
        df = df.merge(osm_df, on="grid_id", how="left")

    weather_file = PROCESSED_DIR / "weather_features.parquet"
    if weather_file.exists():
        weather_df = pd.read_parquet(weather_file)
        df = df.merge(weather_df, on="grid_id", how="left")

    # Fill missing columns with defaults
    default_features = {
        "frac_impervious": 0.5, "frac_vegetation": 0.2, "frac_bare_soil": 0.1,
        "frac_water": 0.01, "ndvi_mean": 0.2, "ndvi_std": 0.05,
        "ndbi_mean": 0.1, "building_density": 50, "building_height_mean": 5.0,
        "road_density": 500, "park_area_frac": 0.05, "tree_canopy_frac": 0.1,
        "dist_to_water": 2000, "water_area_frac": 0.01,
        "air_temp_max": 45.0, "wind_speed_mean": 3.0, "solar_radiation": 300,
    }
    for col, default in default_features.items():
        if col not in df.columns:
            df[col] = default

    # Derived features
    df = compute_derived_features(df)

    # Spatial lag features
    lag_features = ["lst_mean", "ndvi_mean", "frac_impervious"]
    lag_cols = [f for f in lag_features if f in df.columns and not df[f].isna().all()]
    if lag_cols:
        df = compute_spatial_lag(df, grid, lag_cols)

    # Hotspot tiers
    if "lst_mean" in df.columns and not df["lst_mean"].isna().all():
        df = assign_hotspot_tiers(df)

    # Save
    df.to_parquet(FEATURES_FILE, index=False)
    print(f"  [OK] Feature table: {len(df)} cells × {len(df.columns)} features")
    print(f"  Saved → {FEATURES_FILE.name}")

    if "tier" in df.columns:
        print(f"  Tier distribution:")
        for tier, count in df["tier"].value_counts().items():
            print(f"    {tier}: {count} ({count/len(df)*100:.1f}%)")

    print("[Step 07] Done.")
    return df


if __name__ == "__main__":
    run()
