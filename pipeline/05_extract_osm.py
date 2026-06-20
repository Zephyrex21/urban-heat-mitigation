"""
Step 05: Extract OpenStreetMap Urban Morphology Features

Extracts building footprints, road networks, green spaces, and water features
from OSM data and computes per-grid-cell urban morphology metrics.
"""

import numpy as np
from pathlib import Path

from pipeline.config import RAW_DIR, PROCESSED_DIR, CITY_BBOX


def extract_buildings(osm_path: Path) -> dict:
    """
    Extract building footprints and compute:
    - building_density: count per km²
    - building_height_mean: average height in meters
    - building_footprint_frac: fraction of cell covered by buildings
    
    Uses osmnx for on-the-fly download if PBF not available.
    """
    try:
        import geopandas as gpd
    except ImportError:
        print("  [SKIP] geopandas not installed")
        return {}

    # Try loading from file first
    if osm_path.exists() and osm_path.suffix == ".gpkg":
        buildings = gpd.read_file(osm_path, layer="buildings")
    else:
        # Fallback: use osmnx
        try:
            import osmnx as ox
            bbox = CITY_BBOX
            buildings = ox.features_from_bbox(
                bbox=( bbox["north"], bbox["south"], bbox["east"], bbox["west"]),
                tags={"building": True}
            )
            print(f"  [OK] Downloaded {len(buildings)} buildings from OSM")
        except Exception as e:
            print(f"  [WARN] Could not load buildings: {e}")
            return {}

    return {"buildings": buildings}


def extract_roads(osm_path: Path) -> dict:
    """
    Extract road network and compute:
    - road_density: total road length (m) per km²
    - road_type_mix: fraction of highways vs local streets
    """
    try:
        import osmnx as ox
        bbox = CITY_BBOX
        G = ox.graph_from_bbox(
            bbox=(bbox["north"], bbox["south"], bbox["east"], bbox["west"]),
            network_type="drive"
        )
        edges = ox.graph_to_gdfs(G, nodes=False)
        print(f"  [OK] Downloaded {len(edges)} road segments from OSM")
        return {"roads": edges}
    except Exception as e:
        print(f"  [WARN] Could not load roads: {e}")
        return {}


def extract_green_spaces(osm_path: Path) -> dict:
    """
    Extract parks, gardens, and green areas.
    Computes: park_area_frac per grid cell.
    """
    try:
        import osmnx as ox
        bbox = CITY_BBOX
        parks = ox.features_from_bbox(
            bbox=(bbox["north"], bbox["south"], bbox["east"], bbox["west"]),
            tags={"leisure": ["park", "garden", "nature_reserve"],
                  "landuse": ["grass", "forest", "meadow"]}
        )
        print(f"  [OK] Downloaded {len(parks)} green space features from OSM")
        return {"green_spaces": parks}
    except Exception as e:
        print(f"  [WARN] Could not load green spaces: {e}")
        return {}


def extract_water_features(osm_path: Path) -> dict:
    """
    Extract water bodies (lakes, rivers, canals).
    Computes: water_area_frac, dist_to_water per grid cell.
    """
    try:
        import osmnx as ox
        bbox = CITY_BBOX
        water = ox.features_from_bbox(
            bbox=(bbox["north"], bbox["south"], bbox["east"], bbox["west"]),
            tags={"natural": "water", "waterway": True}
        )
        print(f"  [OK] Downloaded {len(water)} water features from OSM")
        return {"water": water}
    except Exception as e:
        print(f"  [WARN] Could not load water features: {e}")
        return {}


def compute_grid_features(grid_gdf, buildings_gdf=None, roads_gdf=None,
                           parks_gdf=None, water_gdf=None) -> dict:
    """
    Spatial join all OSM features to grid cells and compute metrics.
    
    Returns dict of feature arrays indexed by grid cell.
    """
    import geopandas as gpd
    from shapely.ops import nearest_points

    features = {}
    n_cells = len(grid_gdf)
    cell_area_km2 = 0.5 * 0.5  # 500m × 500m = 0.25 km²

    # Building features
    if buildings_gdf is not None and len(buildings_gdf) > 0:
        joined = gpd.sjoin(buildings_gdf, grid_gdf, how="inner", predicate="intersects")
        building_counts = joined.groupby("index_right").size()
        features["building_density"] = np.array([
            building_counts.get(i, 0) / cell_area_km2 for i in range(n_cells)
        ])

        # Building height (if available)
        if "height" in buildings_gdf.columns:
            height_means = joined.groupby("index_right")["height"].mean()
            features["building_height_mean"] = np.array([
                height_means.get(i, 5.0) for i in range(n_cells)  # default 5m
            ])
        else:
            features["building_height_mean"] = np.full(n_cells, 5.0)
    else:
        features["building_density"] = np.zeros(n_cells)
        features["building_height_mean"] = np.full(n_cells, 5.0)

    # Road density
    if roads_gdf is not None and len(roads_gdf) > 0:
        joined = gpd.sjoin(roads_gdf, grid_gdf, how="inner", predicate="intersects")
        road_lengths = joined.groupby("index_right").geometry.apply(
            lambda g: g.length.sum()
        )
        features["road_density"] = np.array([
            road_lengths.get(i, 0) / cell_area_km2 for i in range(n_cells)
        ])
    else:
        features["road_density"] = np.zeros(n_cells)

    # Park area fraction
    if parks_gdf is not None and len(parks_gdf) > 0:
        for i, cell in grid_gdf.iterrows():
            clipped = parks_gdf.clip(cell.geometry)
            park_area = clipped.geometry.area.sum() if len(clipped) > 0 else 0
            cell_area = cell.geometry.area
            features.setdefault("park_area_frac", []).append(
                min(park_area / cell_area, 1.0) if cell_area > 0 else 0
            )
        features["park_area_frac"] = np.array(features["park_area_frac"])
    else:
        features["park_area_frac"] = np.zeros(n_cells)

    # Water features
    if water_gdf is not None and len(water_gdf) > 0:
        water_union = water_gdf.geometry.union_all()
        dists = grid_gdf.geometry.centroid.distance(water_union)
        features["dist_to_water"] = dists.values
        features["water_area_frac"] = np.zeros(n_cells)
        for i, cell in grid_gdf.iterrows():
            clipped = water_gdf.clip(cell.geometry)
            if len(clipped) > 0:
                features["water_area_frac"][i] = min(
                    clipped.geometry.area.sum() / cell.geometry.area, 1.0
                )
    else:
        features["dist_to_water"] = np.full(n_cells, 5000.0)
        features["water_area_frac"] = np.zeros(n_cells)

    return features


def run():
    """Run OSM feature extraction pipeline."""
    print("[Step 05] Extracting OSM features...")

    osm_dir = RAW_DIR / "osm"
    osm_path = osm_dir / "phoenix.gpkg" if osm_dir.exists() else Path(".")

    buildings = extract_buildings(osm_path)
    roads = extract_roads(osm_path)
    green = extract_green_spaces(osm_path)
    water = extract_water_features(osm_path)

    print("[Step 05] Done.")
    return {**buildings, **roads, **green, **water}


if __name__ == "__main__":
    run()
