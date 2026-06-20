"""
Step 06: Build Analysis Grid

Creates a 500m × 500m fishnet grid over the Phoenix AOI.
Each cell gets a unique ID and centroid coordinates.
"""

import numpy as np
from pathlib import Path

from pipeline.config import (
    CITY_BBOX, GRID_CELL_SIZE_M, CRS_WGS84, CRS_UTM, GRID_FILE
)


def create_fishnet(bbox: dict, cell_size_m: float, crs_utm: str, crs_wgs84: str) -> "gpd.GeoDataFrame":
    """
    Create a fishnet (regular grid) of square cells over the given bounding box.
    
    Args:
        bbox: dict with west, south, east, north in WGS84
        cell_size_m: cell size in meters
        crs_utm: projected CRS for metric distances
        crs_wgs84: geographic CRS for output
    
    Returns:
        GeoDataFrame with grid cells, grid_id, and centroid coords
    """
    import geopandas as gpd
    from shapely.geometry import box, Polygon
    from pyproj import Transformer

    # Transform bbox to UTM
    transformer_to_utm = Transformer.from_crs(crs_wgs84, crs_utm, always_xy=True)
    transformer_to_wgs = Transformer.from_crs(crs_utm, crs_wgs84, always_xy=True)

    west_utm, south_utm = transformer_to_utm.transform(bbox["west"], bbox["south"])
    east_utm, north_utm = transformer_to_utm.transform(bbox["east"], bbox["north"])

    # Generate grid cells in UTM
    cells = []
    grid_ids = []
    idx = 0

    x = west_utm
    while x < east_utm:
        y = south_utm
        while y < north_utm:
            cell = box(x, y, x + cell_size_m, y + cell_size_m)
            cells.append(cell)
            grid_ids.append(f"cell_{idx:04d}")
            idx += 1
            y += cell_size_m
        x += cell_size_m

    # Create GeoDataFrame in UTM
    grid = gpd.GeoDataFrame(
        {"grid_id": grid_ids},
        geometry=cells,
        crs=crs_utm,
    )

    # Transform back to WGS84 for storage/display
    grid = grid.to_crs(crs_wgs84)

    # Add centroid coordinates
    centroids = grid.geometry.centroid
    grid["centroid_lon"] = centroids.x
    grid["centroid_lat"] = centroids.y

    # Add cell area in km²
    grid_utm = grid.to_crs(crs_utm)
    grid["area_km2"] = grid_utm.geometry.area / 1e6

    print(f"  [OK] Created {len(grid)} grid cells ({cell_size_m}m × {cell_size_m}m)")
    print(f"  Grid extent: {grid.total_bounds}")

    return grid


def run():
    """Build the analysis grid and save to GeoJSON."""
    print("[Step 06] Building analysis grid...")

    try:
        import geopandas as gpd
    except ImportError:
        print("  [SKIP] geopandas not installed")
        return

    grid = create_fishnet(CITY_BBOX, GRID_CELL_SIZE_M, CRS_UTM, CRS_WGS84)

    # Save
    grid.to_file(GRID_FILE, driver="GeoJSON")
    print(f"  [OK] Grid saved → {GRID_FILE.name}")
    print(f"  Total cells: {len(grid)}")
    print("[Step 06] Done.")

    return grid


if __name__ == "__main__":
    run()
