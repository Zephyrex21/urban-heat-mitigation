"""
Synthetic Data Generator for Demo (Multi-City)

Generates realistic synthetic data for each city in pipeline.config.CITIES
so the full pipeline, ML model, and frontend can be demonstrated without
downloading real satellite data.

The synthetic data mimics real urban heat island (UHI) patterns:
- City center is hottest (high impervious, low vegetation)
- Suburban areas have moderate temperatures
- Parks and river/coast corridors are cool spots
- Each city's climate baseline (base_temp_c, air_temp_baseline,
  veg_shift, coastal) shifts the synthetic LST distribution so cities
  actually look different from one another instead of all converging
  on one fixed profile.

Usage:
    python -m pipeline.generate_synthetic            # all cities
    python -m pipeline.generate_synthetic new_delhi   # one city
"""

import sys
import json
import math
import numpy as np
import pandas as pd

from pipeline.config import (
    CITIES, DEFAULT_CITY, GRID_CELL_SIZE_M, CRS_WGS84, utm_epsg_for,
    city_grid_file, city_features_file, city_presets_file,
    HOTSPOT_TIERS, INTERVENTIONS, TIER_COLORS,
)

M_PER_DEG_LAT = 111320.0  # ~constant everywhere


def generate_grid(city_id: str):
    """Generate the 500m fishnet grid for a city's bbox."""
    from pyproj import Transformer
    from shapely.geometry import box

    city = CITIES[city_id]
    bbox = city["bbox"]
    center_lon, center_lat = city["center"]
    crs_utm = utm_epsg_for(center_lon, center_lat)

    transformer_to_utm = Transformer.from_crs(CRS_WGS84, crs_utm, always_xy=True)
    transformer_to_wgs = Transformer.from_crs(crs_utm, CRS_WGS84, always_xy=True)

    west_utm, south_utm = transformer_to_utm.transform(bbox["west"], bbox["south"])
    east_utm, north_utm = transformer_to_utm.transform(bbox["east"], bbox["north"])

    cells = []
    grid_ids = []
    centroids_lon = []
    centroids_lat = []
    idx = 0

    x = west_utm
    while x < east_utm:
        y = south_utm
        while y < north_utm:
            corners_utm = [
                (x, y), (x + GRID_CELL_SIZE_M, y),
                (x + GRID_CELL_SIZE_M, y + GRID_CELL_SIZE_M),
                (x, y + GRID_CELL_SIZE_M), (x, y)
            ]
            corners_wgs = [transformer_to_wgs.transform(cx, cy) for cx, cy in corners_utm]

            cx_wgs, cy_wgs = transformer_to_wgs.transform(
                x + GRID_CELL_SIZE_M / 2, y + GRID_CELL_SIZE_M / 2
            )

            cells.append(corners_wgs)
            grid_ids.append(f"cell_{idx:04d}")
            centroids_lon.append(cx_wgs)
            centroids_lat.append(cy_wgs)
            idx += 1
            y += GRID_CELL_SIZE_M
        x += GRID_CELL_SIZE_M

    return grid_ids, cells, centroids_lon, centroids_lat


def generate_features(grid_ids, centroids_lon, centroids_lat, city_id: str, seed=42):
    """
    Generate realistic synthetic features for each grid cell, shaped by
    the target city's climate profile (CITIES[city_id]).
    """
    np.random.seed(seed)
    n = len(grid_ids)
    city = CITIES[city_id]

    lon = np.array(centroids_lon)
    lat = np.array(centroids_lat)

    # City center (the "downtown" gradient origin)
    center_lon, center_lat = city["center"]
    m_per_deg_lon = M_PER_DEG_LAT * math.cos(math.radians(center_lat))

    dist_to_center = np.sqrt(
        ((lon - center_lon) * m_per_deg_lon) ** 2 +
        ((lat - center_lat) * M_PER_DEG_LAT) ** 2
    ) / 1000  # km

    # Urban intensity gradient (higher near center)
    urban_intensity = np.exp(-dist_to_center / 15) + np.random.normal(0, 0.05, n)
    urban_intensity = np.clip(urban_intensity, 0, 1)

    # ─── Land Cover Fractions ───
    veg_shift = city["veg_shift"]
    frac_impervious = 0.3 + 0.5 * urban_intensity + np.random.normal(0, 0.05, n)
    frac_vegetation = (0.35 + veg_shift) - 0.3 * urban_intensity + np.random.normal(0, 0.04, n)
    frac_bare_soil = 0.2 - 0.1 * urban_intensity + np.random.normal(0, 0.03, n)
    frac_water = 0.02 + np.random.exponential(0.01, n)
    if city["coastal"]:
        frac_water += 0.015  # coastal cities run wetter on average

    total = frac_impervious + frac_vegetation + frac_bare_soil + frac_water
    frac_impervious /= total
    frac_vegetation /= total
    frac_bare_soil /= total
    frac_water /= total

    frac_impervious = np.clip(frac_impervious, 0.01, 0.95)
    frac_vegetation = np.clip(frac_vegetation, 0.01, 0.6)
    frac_bare_soil = np.clip(frac_bare_soil, 0.01, 0.5)
    frac_water = np.clip(frac_water, 0.0, 0.15)

    # ─── Vegetation Indices ───
    ndvi_mean = 0.1 + 0.5 * frac_vegetation + np.random.normal(0, 0.03, n)
    ndvi_mean = np.clip(ndvi_mean, -0.1, 0.8)
    ndvi_std = 0.02 + 0.08 * frac_vegetation + np.random.normal(0, 0.01, n)
    ndvi_std = np.clip(ndvi_std, 0.01, 0.2)

    # ─── Built Environment ───
    ndbi_mean = -0.1 + 0.4 * frac_impervious + np.random.normal(0, 0.03, n)
    ndbi_mean = np.clip(ndbi_mean, -0.3, 0.5)

    building_density = 20 + 300 * urban_intensity + np.random.normal(0, 20, n)
    building_density = np.clip(building_density, 0, 500)

    building_height_mean = 3 + 25 * urban_intensity ** 2 + np.random.normal(0, 2, n)
    building_height_mean = np.clip(building_height_mean, 2, 50)

    road_density = 200 + 2000 * urban_intensity + np.random.normal(0, 100, n)
    road_density = np.clip(road_density, 50, 5000)

    # ─── Green Space ───
    park_area_frac = 0.08 - 0.04 * urban_intensity + np.random.exponential(0.02, n)
    park_area_frac = np.clip(park_area_frac, 0, 0.4)

    park_cells = np.random.choice(n, size=int(n * 0.05), replace=False)
    park_area_frac[park_cells] = np.random.uniform(0.3, 0.8, len(park_cells))
    frac_vegetation[park_cells] = np.random.uniform(0.4, 0.7, len(park_cells))
    ndvi_mean[park_cells] = np.random.uniform(0.4, 0.7, len(park_cells))

    tree_canopy_frac = frac_vegetation * 0.6 + np.random.normal(0, 0.02, n)
    tree_canopy_frac = np.clip(tree_canopy_frac, 0, 0.5)

    # ─── Water Proximity ───
    # A simplified single river/coast reference line, oriented along
    # whichever axis the city's config specifies (mirrors how the
    # original Phoenix model treated the Salt River as a fixed-latitude
    # line — generalized here to either axis, and to any city).
    water_axis = city["water_axis"]
    water_value = city["water_value"]
    if water_axis == "lat":
        dist_to_water = np.abs(lat - water_value) * M_PER_DEG_LAT
    else:
        dist_to_water = np.abs(lon - water_value) * m_per_deg_lon
    dist_to_water = dist_to_water + np.random.normal(0, 200, n)
    dist_to_water = np.clip(dist_to_water, 50, 10000)

    water_area_frac = np.where(dist_to_water < 500, 0.05 + np.random.uniform(0, 0.1, n), frac_water)
    if city["coastal"]:
        water_area_frac = np.clip(water_area_frac + 0.02, 0, 0.3)

    # ─── Weather (ERA5-like) ───
    air_temp_max = city["air_temp_baseline"] + 5 * urban_intensity + np.random.normal(0, 1.5, n)
    wind_base = 5.5 if city["coastal"] else 4.0
    wind_speed_mean = wind_base - 2.0 * urban_intensity + np.random.normal(0, 0.5, n)
    wind_speed_mean = np.clip(wind_speed_mean, 0.5, 8)
    solar_radiation = 280 + 40 * (1 - frac_vegetation) + np.random.normal(0, 15, n)
    solar_radiation = np.clip(solar_radiation, 200, 400)

    # ─── Target: LST ───
    # Same physically-motivated structure as the original Phoenix
    # model — impervious surfaces heat up, vegetation cools, etc. —
    # but anchored to this city's own climate baseline instead of a
    # fixed constant, so different cities produce genuinely different
    # LST distributions.
    base_temp_c = city["base_temp_c"]
    lst_mean = (
        base_temp_c
        + 12.0 * frac_impervious
        - 8.0 * ndvi_mean
        + 3.0 * ndbi_mean
        + 0.008 * building_density
        + 0.1 * building_height_mean
        - 0.5 * wind_speed_mean
        + 0.02 * solar_radiation
        - 2.0 * water_area_frac * 10
        - 3.0 * park_area_frac
        + np.random.normal(0, 1.0, n)
    )
    lst_mean = np.clip(lst_mean, base_temp_c + 2, base_temp_c + 28)

    lst_max = lst_mean + 2 + np.random.exponential(1.5, n)
    lst_max = np.clip(lst_max, lst_mean + 0.5, base_temp_c + 32)

    # ─── Assemble DataFrame ───
    df = pd.DataFrame({
        "grid_id": grid_ids,
        "centroid_lon": centroids_lon,
        "centroid_lat": centroids_lat,
        "lst_mean": np.round(lst_mean, 2),
        "lst_max": np.round(lst_max, 2),
        "frac_impervious": np.round(frac_impervious, 4),
        "frac_vegetation": np.round(frac_vegetation, 4),
        "frac_bare_soil": np.round(frac_bare_soil, 4),
        "frac_water": np.round(frac_water, 4),
        "ndvi_mean": np.round(ndvi_mean, 4),
        "ndvi_std": np.round(ndvi_std, 4),
        "ndbi_mean": np.round(ndbi_mean, 4),
        "building_density": np.round(building_density, 1),
        "building_height_mean": np.round(building_height_mean, 1),
        "road_density": np.round(road_density, 1),
        "park_area_frac": np.round(park_area_frac, 4),
        "tree_canopy_frac": np.round(tree_canopy_frac, 4),
        "dist_to_water": np.round(dist_to_water, 1),
        "water_area_frac": np.round(water_area_frac, 4),
        "air_temp_max": np.round(air_temp_max, 1),
        "wind_speed_mean": np.round(wind_speed_mean, 2),
        "solar_radiation": np.round(solar_radiation, 1),
    })

    # ─── Derived Features ───
    eps = 0.01
    df["veg_imperv_ratio"] = np.round(df["frac_vegetation"] / (df["frac_impervious"] + eps), 4)
    df["green_deficit"] = np.round(
        np.clip(1.0 - df["frac_vegetation"] - df["park_area_frac"], 0, 1), 4
    )
    df["thermal_mass_proxy"] = np.round(df["building_density"] * df["building_height_mean"], 1)
    df["cooling_potential"] = np.round(
        (1 - df["frac_vegetation"]) * df["solar_radiation"], 1
    )
    max_h = df["building_height_mean"].max()
    df["sky_view_factor"] = np.round(
        1.0 - (df["building_height_mean"] / max_h) * 0.5, 4
    )

    # ─── Hotspot Tiers (this city's own mean/std) ───
    mean_lst = df["lst_mean"].mean()
    std_lst = df["lst_mean"].std()

    def classify_tier(lst):
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

    df["tier"] = df["lst_mean"].apply(classify_tier)
    df["delta_above_mean"] = np.round(df["lst_mean"] - mean_lst, 2)

    df["priority_score"] = np.round(
        np.clip(df["delta_above_mean"], 0, None) * (1.0 / (df["frac_vegetation"] + eps)), 2
    )
    max_ps = df["priority_score"].max()
    if max_ps > 0:
        df["priority_score"] = np.round(df["priority_score"] / max_ps * 10, 1)

    return df


def generate_grid_geojson(grid_ids, cells, features_df):
    """Generate GeoJSON for the grid with embedded features."""
    features = []
    for i, (grid_id, coords) in enumerate(zip(grid_ids, cells)):
        row = features_df[features_df["grid_id"] == grid_id].iloc[0]
        props = row.to_dict()
        for k in ["centroid_lon", "centroid_lat"]:
            if k in props:
                del props[k]

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords]
            },
            "properties": props
        }
        features.append(feature)

    return {"type": "FeatureCollection", "features": features}


def generate_scenario_results(features_df, city_id: str):
    """Pre-compute scenario results for the demo presets, for one city."""
    scenarios = []
    base_temp_c = CITIES[city_id]["base_temp_c"]

    presets = {
        "baseline": {
            "name": "Baseline",
            "description": "Current conditions — no interventions",
            "interventions": {},
        },
        "green_phoenix": {
            "name": "Green Cover Boost",
            "description": "Aggressive tree planting (+20%) in all hotspot cells",
            "interventions": {"tree_cover": 0.7},
        },
        "cool_roofs_first": {
            "name": "Cool Roofs First",
            "description": "Cool roofs on all commercial/industrial buildings",
            "interventions": {"cool_roofs": 0.8},
        },
        "balanced_mix": {
            "name": "Balanced Mix",
            "description": "Trees +10%, Cool Roofs +30%, Green Roofs 15%",
            "interventions": {"tree_cover": 0.35, "cool_roofs": 0.3, "green_roofs": 0.15},
        },
        "water_network": {
            "name": "Water Network",
            "description": "Blue infrastructure — retention ponds + tree corridors",
            "interventions": {"water_bodies": 0.5, "tree_cover": 0.3},
        },
        "maximum_cooling": {
            "name": "Maximum Cooling",
            "description": "All interventions at maximum intensity",
            "interventions": {"tree_cover": 1.0, "cool_roofs": 1.0, "green_roofs": 1.0,
                            "water_bodies": 1.0, "albedo_improvement": 1.0},
        },
    }

    hotspot_mask = features_df["tier"].isin(["critical", "high"])
    mean_lst = features_df["lst_mean"].mean()
    std_lst = features_df["lst_mean"].std()

    for scenario_id, config in presets.items():
        df = features_df.copy()

        if config["interventions"]:
            for intervention, intensity in config["interventions"].items():
                if intervention in INTERVENTIONS:
                    mods = INTERVENTIONS[intervention]["feature_mods"]
                    for feature, delta in mods.items():
                        if feature in df.columns:
                            if feature == "solar_radiation":
                                df.loc[hotspot_mask, feature] *= (1 + delta * intensity)
                            elif feature == "dist_to_water":
                                df.loc[hotspot_mask, feature] = np.clip(
                                    df.loc[hotspot_mask, feature] + delta * intensity, 50, 10000
                                )
                            else:
                                df.loc[hotspot_mask, feature] = np.clip(
                                    df.loc[hotspot_mask, feature] + delta * intensity, 0, 1
                                )

            lst_new = (
                base_temp_c
                + 12.0 * df["frac_impervious"]
                - 8.0 * df["ndvi_mean"]
                + 3.0 * df["ndbi_mean"]
                + 0.008 * df["building_density"]
                + 0.1 * df["building_height_mean"]
                - 0.5 * df["wind_speed_mean"]
                + 0.02 * df["solar_radiation"]
                - 2.0 * df["water_area_frac"] * 10
                - 3.0 * df["park_area_frac"]
            )
            lst_new = np.clip(lst_new, base_temp_c + 2, base_temp_c + 28)
            df["lst_after"] = np.round(lst_new, 2)
        else:
            df["lst_after"] = df["lst_mean"]

        df["delta_t"] = np.round(df["lst_after"] - df["lst_mean"], 2)

        hotspot_area_km2 = hotspot_mask.sum() * 0.25
        total_cost = 0
        for intervention, intensity in config["interventions"].items():
            if intervention in INTERVENTIONS:
                total_cost += (
                    INTERVENTIONS[intervention]["cost_per_km2_million"] *
                    intensity * hotspot_area_km2
                )

        def classify_after(lst):
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

        df["tier_after"] = df["lst_after"].apply(classify_after)

        hotspots_before = features_df["tier"].isin(["critical", "high"]).sum()
        hotspots_after = df["tier_after"].isin(["critical", "high"]).sum()

        if config["interventions"] and hotspot_mask.sum() > 0:
            cooling_series = df.loc[hotspot_mask, "delta_t"]
        else:
            cooling_series = df["delta_t"]

        scenario = {
            "scenario_id": scenario_id,
            "name": config["name"],
            "description": config["description"],
            "interventions": config["interventions"],
            "mean_cooling_c": round(cooling_series.mean(), 2),
            "max_cooling_c": round(cooling_series.min(), 2),
            "hotspots_before": int(hotspots_before),
            "hotspots_after": int(hotspots_after),
            "hotspot_reduction_pct": round(
                (hotspots_before - hotspots_after) / max(hotspots_before, 1) * 100, 1
            ),
            "cost_estimate_m": round(total_cost, 1),
            "cost_efficiency": round(
                abs(cooling_series.mean()) / max(total_cost, 0.1), 3
            ) if total_cost > 0 else 0,
            # Note: per-cell results are intentionally NOT stored here.
            # The frontend runs these same interventions through the
            # live /scenarios/simulate endpoint when a preset is
            # applied, which keeps the map and the summary numbers
            # guaranteed-consistent and avoids ~50MB+ of duplicated
            # per-cell data across 14 cities × 6 presets.
        }
        scenarios.append(scenario)

    return scenarios


def run_for_city(city_id: str):
    """Generate all synthetic data for a single city."""
    city = CITIES[city_id]
    print("\n" + "-" * 60)
    print(f"  {city['name']}, {city['state']} ({city_id})")
    print("-" * 60)

    print("  [1/4] Generating grid...")
    grid_ids, cells, centroids_lon, centroids_lat = generate_grid(city_id)
    print(f"    Created {len(grid_ids)} grid cells")

    print("  [2/4] Generating features...")
    features_df = generate_features(grid_ids, centroids_lon, centroids_lat, city_id)
    features_df.to_parquet(city_features_file(city_id), index=False)
    print(f"    LST range: {features_df['lst_mean'].min():.1f}°C to {features_df['lst_mean'].max():.1f}°C "
          f"(mean {features_df['lst_mean'].mean():.1f}°C)")
    tier_counts = features_df["tier"].value_counts()
    print("    Tiers: " + ", ".join(f"{t}={tier_counts.get(t, 0)}" for t in
                                     ["critical", "high", "moderate", "normal", "cool"]))

    print("  [3/4] Generating grid GeoJSON...")
    geojson = generate_grid_geojson(grid_ids, cells, features_df)
    with open(city_grid_file(city_id), "w") as f:
        json.dump(geojson, f)
    print(f"    Saved → {city_grid_file(city_id)}")

    print("  [4/4] Pre-computing scenarios...")
    scenarios = generate_scenario_results(features_df, city_id)
    with open(city_presets_file(city_id), "w") as f:
        json.dump(scenarios, f, indent=2, default=str)
    print(f"    Generated {len(scenarios)} preset scenarios")

    return features_df


def run():
    """Generate synthetic data for every city (or one, if given on argv)."""
    print("=" * 60)
    print("  Generating Synthetic Urban Heat Data (Multi-City)")
    print("=" * 60)

    requested = sys.argv[1] if len(sys.argv) > 1 else None
    if requested:
        if requested not in CITIES:
            print(f"\n  Unknown city '{requested}'. Available: {', '.join(sorted(CITIES))}")
            sys.exit(1)
        city_ids = [requested]
    else:
        city_ids = list(CITIES.keys())

    for city_id in city_ids:
        run_for_city(city_id)

    print("\n" + "=" * 60)
    print(f"  Done. Generated data for {len(city_ids)} cit{'y' if len(city_ids) == 1 else 'ies'}.")
    print(f"  Default city for the API: {DEFAULT_CITY}")
    print("=" * 60)


if __name__ == "__main__":
    run()
