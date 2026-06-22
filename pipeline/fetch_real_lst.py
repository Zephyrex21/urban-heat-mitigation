"""
Fetch REAL Land Surface Temperature from Landsat Collection 2 Level-2,
via Microsoft's free Planetary Computer STAC API, and validate the
app's synthetic data against it.

This is NOT part of the synthetic demo pipeline — it talks to a live
satellite data catalog over the open internet, so it must be run from a
machine with normal (unrestricted) internet access. No API key, account,
or payment is required; Planetary Computer's STAC catalog is free and
public.

What it does:
    1. Searches Landsat 8/9 Collection 2 Level-2 for the most recent,
       least-cloudy scene covering the target city.
    2. Reads just the thermal band (ST_B10 / "lwir11"), windowed to the
       city's bounding box — no full-scene download needed.
    3. Calibrates digital numbers to real surface temperature in °C,
       using the official USGS scale/offset (same formula already used
       in 02_preprocess_lst.py for consistency).
    4. Computes the zonal mean per grid cell, using the SAME grid this
       city's synthetic data already uses — so it lines up cell-for-cell.
    5. Compares the real measurement against the synthetic estimate for
       every cell and reports RMSE / MAE / correlation.
    6. Saves both the real per-cell values and the comparison metadata,
       which the API then serves at GET /api/v1/validation?city=<id>.

Usage:
    pip install pystac-client planetary-computer rasterstats
    python -m pipeline.fetch_real_lst              # defaults to new_delhi
    python -m pipeline.fetch_real_lst mumbai        # or any other city
"""

import json
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds

from pipeline.config import CITIES, PROCESSED_DIR, LANDSAT_SCALE_FACTOR, LANDSAT_OFFSET

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"


def _search_best_scene(catalog, bbox_list, cloud_cover_max=30):
    """
    Search for the least-cloudy Landsat 8/9 scene over the bbox.
    Tries the app's labeled hot season first (Apr-Jun of the current
    year), then falls back to the last 2 years of any season if nothing
    clear enough is found — heavy cloud cover during monsoon months can
    occasionally rule out the narrow window.
    """
    today = datetime.utcnow().date()
    this_year = today.year

    windows = [
        (f"{this_year}-04-01", today.isoformat()),
        ((today - timedelta(days=730)).isoformat(), today.isoformat()),
    ]

    for start, end in windows:
        search = catalog.search(
            collections=["landsat-c2-l2"],
            bbox=bbox_list,
            datetime=f"{start}/{end}",
            query={
                "eo:cloud_cover": {"lt": cloud_cover_max},
                "platform": {"in": ["landsat-8", "landsat-9"]},
            },
        )
        items = list(search.item_collection())
        if items:
            return min(items, key=lambda it: it.properties.get("eo:cloud_cover", 100))

    return None


class FetchError(Exception):
    """Raised when a single city's fetch fails — lets batch runs skip and continue."""
    pass


def fetch_real_lst(city_id: str = "new_delhi", cloud_cover_max: int = 30):
    try:
        import pystac_client
        import planetary_computer
        from rasterstats import zonal_stats
    except ImportError:
        print("Missing packages. Run:")
        print("  pip install pystac-client planetary-computer rasterstats")
        raise FetchError("missing satellite packages")

    if city_id not in CITIES:
        print(f"Unknown city_id '{city_id}'. Available: {', '.join(CITIES.keys())}")
        raise FetchError(f"unknown city_id '{city_id}'")

    city = CITIES[city_id]
    bbox = city["bbox"]
    bbox_list = [bbox["west"], bbox["south"], bbox["east"], bbox["north"]]

    grid_path = PROCESSED_DIR / city_id / "grid.geojson"
    features_path = PROCESSED_DIR / city_id / "features.parquet"
    if not grid_path.exists():
        print(f"No grid found at {grid_path}.")
        print(f"Run `python -m pipeline.generate_synthetic {city_id}` first.")
        raise FetchError(f"no grid for '{city_id}'")

    print(f"Searching Landsat Collection 2 Level-2 for {city['name']}, {city['state']}...")

    catalog = pystac_client.Client.open(STAC_URL, modifier=planetary_computer.sign_inplace)
    item = _search_best_scene(catalog, bbox_list, cloud_cover_max)

    if item is None:
        print(f"No scenes found under {cloud_cover_max}% cloud cover in the last 2 years.")
        print("Try increasing cloud_cover_max, or check your internet connection.")
        raise FetchError(f"no suitable scene for '{city_id}'")

    print(f"  Selected scene : {item.id}")
    print(f"  Date           : {item.properties['datetime']}")
    print(f"  Cloud cover    : {item.properties.get('eo:cloud_cover')}%")
    print(f"  Platform       : {item.properties.get('platform')}")

    asset = item.assets.get("lwir11") or item.assets.get("ST_B10")
    if asset is None:
        print("Surface temperature band not found on this scene.")
        raise FetchError(f"no thermal band asset for '{city_id}'")

    print("Reading thermal band (windowed to city bbox only — no full download)...")
    with rasterio.open(asset.href) as src:
        west, south, east, north = transform_bounds("EPSG:4326", src.crs, *bbox_list)
        window = from_bounds(west, south, east, north, transform=src.transform)
        # boundless=True guarantees the returned array always has exactly the
        # requested window's shape/geography, padding with fill_value for any
        # part outside the scene's actual footprint. Without this, a window
        # that partially exceeds the scene gets silently clipped by rasterio,
        # but win_transform still describes the ORIGINAL (larger) window —
        # an array/geography mismatch that corrupts every pixel lookup after it.
        dn = src.read(1, window=window, boundless=True, fill_value=0).astype(np.float32)
        win_transform = src.window_transform(window)
        raster_crs = src.crs

    if dn.size == 0:
        print("Windowed read returned no data — bbox may not be covered by this scene.")
        raise FetchError(f"empty window read for '{city_id}'")

    # Official USGS calibration: DN -> Kelvin -> Celsius
    lst_kelvin = dn * LANDSAT_SCALE_FACTOR + LANDSAT_OFFSET
    lst_celsius = lst_kelvin - 273.15
    lst_celsius[(lst_celsius < -20) | (lst_celsius > 70)] = np.nan  # mask obvious bad pixels

    valid_pct = 100 * np.sum(~np.isnan(lst_celsius)) / lst_celsius.size
    print(f"  Real LST range : {np.nanmin(lst_celsius):.1f}°C to {np.nanmax(lst_celsius):.1f}°C "
          f"({valid_pct:.0f}% valid pixels)")

    # --- Sanity check: confirm the windowed array is actually aligned with
    # geography the way we expect, before trusting any zonal stats from it.
    # We independently sample the raster at the city's known center point
    # two different ways and confirm they agree. If they don't, something
    # in the windowing/CRS handling is flipped or offset.
    import pyproj
    from rasterio.transform import rowcol as _rowcol

    to_raster_crs = pyproj.Transformer.from_crs("EPSG:4326", raster_crs, always_xy=True)
    center_lon, center_lat = city["center"]
    cx, cy = to_raster_crs.transform(center_lon, center_lat)
    win_west, win_south, win_east, win_north = rasterio.transform.array_bounds(
        dn.shape[0], dn.shape[1], win_transform
    )
    print(f"\n  [diagnostic] Window bounds (raster CRS): "
          f"({win_west:.0f}, {win_south:.0f}) to ({win_east:.0f}, {win_north:.0f})")
    print(f"  [diagnostic] City center in raster CRS  : ({cx:.0f}, {cy:.0f})")

    if win_west <= cx <= win_east and win_south <= cy <= win_north:
        r, c = _rowcol(win_transform, cx, cy)
        if 0 <= r < dn.shape[0] and 0 <= c < dn.shape[1]:
            center_val = lst_celsius[r, c]
            print(f"  [diagnostic] LST directly under city center (row={r}, col={c}): "
                  f"{center_val:.1f}°C")
        else:
            print("  [diagnostic] City center falls outside the windowed array bounds (unexpected).")
    else:
        print("  [diagnostic] City center falls outside the computed window — bbox/center mismatch in config.py.")
    print()

    # Zonal mean per grid cell, using this city's existing grid
    grid = gpd.read_file(grid_path)
    grid_in_raster_crs = grid.to_crs(raster_crs)

    stats = zonal_stats(
        grid_in_raster_crs.geometry,
        lst_celsius,
        affine=win_transform,
        stats=["mean", "count"],
        nodata=np.nan,
    )
    grid["lst_satellite_c"] = [s["mean"] for s in stats]
    cells_covered = int(sum(1 for s in stats if s["mean"] is not None))

    # Cross-check: find whichever grid cell contains the city center and
    # compare its zonal_stats mean against the direct pixel sample above.
    # These should be close (same physical location, two methods). A large
    # mismatch points squarely at a bug in the zonal_stats/grid alignment
    # step rather than the raw raster read.
    try:
        from shapely.geometry import Point
        center_point = Point(*city["center"])
        containing = grid[grid.geometry.contains(center_point)]
        if len(containing) > 0:
            cell_val = containing.iloc[0]["lst_satellite_c"]
            print(f"  [diagnostic] Zonal-stats value for the cell at city center: "
                  f"{cell_val:.1f}°C  (compare to the direct pixel sample above — "
                  f"should be within ~1-2°C of each other)\n")
    except Exception as diag_err:
        print(f"  [diagnostic] Cross-check skipped: {diag_err}\n")

    # Compare against the synthetic estimate already shown in the app
    validation = None
    if features_path.exists():
        features = pd.read_parquet(features_path)
        merged = (
            grid[["grid_id", "lst_satellite_c"]]
            .merge(features[["grid_id", "lst_mean"]], on="grid_id", how="inner")
            .dropna()
        )
        if len(merged) >= 10:
            diff = merged["lst_satellite_c"] - merged["lst_mean"]
            rmse = float(np.sqrt((diff ** 2).mean()))
            mae = float(diff.abs().mean())
            corr = float(merged["lst_satellite_c"].corr(merged["lst_mean"]))
            validation = {"rmse_c": round(rmse, 2), "mae_c": round(mae, 2), "correlation": round(corr, 3)}
            print("\nValidation — synthetic estimate vs real satellite measurement:")
            print(f"  RMSE        : {rmse:.2f}°C")
            print(f"  MAE         : {mae:.2f}°C")
            print(f"  Correlation : {corr:.3f}")

    # Save per-cell real values
    out_dir = PROCESSED_DIR / city_id
    out_path = out_dir / "landsat_validation.geojson"
    grid[["grid_id", "lst_satellite_c", "geometry"]].to_file(out_path, driver="GeoJSON")

    meta = {
        "city_id": city_id,
        "source": "Landsat Collection 2 Level-2 Surface Temperature (USGS/NASA, via Microsoft Planetary Computer)",
        "scene_id": item.id,
        "scene_datetime": item.properties["datetime"],
        "cloud_cover_pct": item.properties.get("eo:cloud_cover"),
        "platform": item.properties.get("platform"),
        "cells_covered": cells_covered,
        "total_cells": len(grid),
        "validation": validation,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
    }
    meta_path = out_dir / "landsat_validation_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2))

    print(f"\nSaved: {out_path}")
    print(f"Saved: {meta_path}")
    print("Done.\n")
    return meta


def fetch_many(city_ids, cloud_cover_max: int = 30, pause_seconds: float = 1.0):
    """
    Run fetch_real_lst for several cities in one go, continuing past any
    individual failures (cloud cover, no scene found, network hiccup, etc.)
    and printing a summary table at the end.
    """
    import time

    results = []
    for i, city_id in enumerate(city_ids, 1):
        print(f"\n{'=' * 60}")
        print(f"[{i}/{len(city_ids)}] {city_id}")
        print('=' * 60)
        try:
            meta = fetch_real_lst(city_id, cloud_cover_max=cloud_cover_max)
            results.append({"city_id": city_id, "status": "ok", "meta": meta})
        except FetchError as e:
            print(f"  SKIPPED: {e}")
            results.append({"city_id": city_id, "status": "skipped", "error": str(e)})
        except Exception as e:
            print(f"  FAILED: {e}")
            results.append({"city_id": city_id, "status": "failed", "error": str(e)})

        if i < len(city_ids):
            time.sleep(pause_seconds)  # be polite to the free public API

    print(f"\n\n{'=' * 60}")
    print("BATCH SUMMARY")
    print('=' * 60)
    for r in results:
        if r["status"] == "ok":
            v = r["meta"].get("validation")
            tag = f"RMSE {v['rmse_c']}°C, corr {v['correlation']}" if v else "no comparison data"
            print(f"  OK       {r['city_id']:<16} {tag}")
        else:
            print(f"  {r['status'].upper():<9}{r['city_id']:<16} {r.get('error', '')}")

    ok_count = sum(1 for r in results if r["status"] == "ok")
    print(f"\n{ok_count}/{len(city_ids)} cities completed successfully.")
    return results


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "all":
        fetch_many(list(CITIES.keys()))
    elif len(sys.argv) > 1 and "," in sys.argv[1]:
        fetch_many([c.strip() for c in sys.argv[1].split(",")])
    else:
        target_city = sys.argv[1] if len(sys.argv) > 1 else "new_delhi"
        try:
            fetch_real_lst(target_city)
        except FetchError as e:
            print(f"\nFailed: {e}")
            sys.exit(1)
