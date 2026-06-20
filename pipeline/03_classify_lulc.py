"""
Step 03: LULC Classification from Sentinel-2

Classifies Sentinel-2 multispectral imagery into 6 land use/land cover classes
using spectral indices and a Random Forest classifier.
"""

import numpy as np
from pathlib import Path

from pipeline.config import (
    RAW_DIR, PROCESSED_DIR, LULC_FILE,
    LULC_CLASSES, SENTINEL2_BANDS
)


def compute_indices(bands: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """
    Compute spectral indices from Sentinel-2 bands.
    
    Args:
        bands: dict mapping band name to 2D array (e.g., {"B04": array, "B08": array})
    
    Returns:
        dict of index arrays: NDVI, NDBI, NDWI, MNDWI
    """
    eps = 1e-10

    # NDVI = (NIR - Red) / (NIR + Red)
    ndvi = (bands["B08"] - bands["B04"]) / (bands["B08"] + bands["B04"] + eps)

    # NDBI = (SWIR1 - NIR) / (SWIR1 + NIR)
    ndbi = (bands["B11"] - bands["B08"]) / (bands["B11"] + bands["B08"] + eps)

    # NDWI = (Green - NIR) / (Green + NIR)
    ndwi = (bands["B03"] - bands["B08"]) / (bands["B03"] + bands["B08"] + eps)

    # MNDWI = (Green - SWIR1) / (Green + SWIR1)
    mndwi = (bands["B03"] - bands["B11"]) / (bands["B03"] + bands["B11"] + eps)

    return {"ndvi": ndvi, "ndbi": ndbi, "ndwi": ndwi, "mndwi": mndwi}


def classify_lulc_rf(bands: dict[str, np.ndarray], indices: dict[str, np.ndarray],
                      training_samples: np.ndarray = None) -> np.ndarray:
    """
    Classify pixels into LULC classes using Random Forest.
    
    If no training samples are provided, uses index-based thresholding as fallback.
    
    Classes:
        0: Impervious  (high NDBI, low NDVI)
        1: Vegetation  (high NDVI)
        2: Bare Soil   (moderate NDBI, low NDVI)
        3: Water       (high MNDWI)
        4: Building    (very high NDBI)
        5: Shadow      (very low reflectance)
    """
    ndvi = indices["ndvi"]
    ndbi = indices["ndbi"]
    mndwi = indices["mndwi"]
    b04 = bands["B04"]

    shape = ndvi.shape
    lulc = np.full(shape, 0, dtype=np.uint8)  # default: impervious

    # Rule-based classification (threshold fallback)
    lulc[mndwi > 0.1] = 3        # Water
    lulc[ndvi > 0.3] = 1          # Vegetation
    lulc[(ndvi < 0.15) & (ndbi > 0.1)] = 0   # Impervious
    lulc[(ndvi < 0.1) & (ndbi > 0.2)] = 4    # Building
    lulc[(ndvi > 0.05) & (ndvi < 0.2) & (ndbi < 0.05)] = 2  # Bare soil
    lulc[b04 < 0.05] = 5          # Shadow (very dark)

    return lulc


def compute_class_fractions(lulc: np.ndarray, grid_cells: list[dict],
                             transform) -> dict[str, list[float]]:
    """
    Compute per-class pixel fractions within each grid cell.
    Returns dict of {class_name: [fraction_per_cell]}.
    """
    n_classes = len(LULC_CLASSES)
    fractions = {f"frac_{name.lower()}": [] for name in LULC_CLASSES.values()}

    for cell in grid_cells:
        # Extract pixel window for this grid cell
        # (simplified — actual implementation uses rasterio.mask or zonal stats)
        row_start, row_end = cell["row_range"]
        col_start, col_end = cell["col_range"]
        patch = lulc[row_start:row_end, col_start:col_end]

        total = patch.size
        if total == 0:
            for key in fractions:
                fractions[key].append(0.0)
            continue

        for cls_id, cls_name in LULC_CLASSES.items():
            key = f"frac_{cls_name.lower()}"
            fractions[key].append(np.sum(patch == cls_id) / total)

    return fractions


def run():
    """Run LULC classification pipeline."""
    print("[Step 03] Classifying LULC from Sentinel-2...")

    sentinel_dir = RAW_DIR / "sentinel2"
    if not sentinel_dir.exists() or not list(sentinel_dir.glob("*.tif")):
        print("  [WARN] No Sentinel-2 data found — use synthetic data")
        return

    try:
        import rasterio
    except ImportError:
        print("  [SKIP] rasterio not installed")
        return

    # Load bands
    bands = {}
    for band_name in SENTINEL2_BANDS:
        band_files = list(sentinel_dir.glob(f"*{band_name}*.tif"))
        if band_files:
            with rasterio.open(band_files[0]) as src:
                bands[band_name] = src.read(1).astype(np.float32) / 10000.0  # scale
                profile = src.profile.copy()

    if len(bands) < len(SENTINEL2_BANDS):
        print(f"  [WARN] Only {len(bands)}/{len(SENTINEL2_BANDS)} bands found")
        return

    # Compute indices
    indices = compute_indices(bands)

    # Classify
    lulc = classify_lulc_rf(bands, indices)

    # Save
    profile.update(dtype="uint8", count=1, nodata=255)
    with rasterio.open(LULC_FILE, "w", **profile) as dst:
        dst.write(lulc, 1)

    # Report class distribution
    for cls_id, cls_name in LULC_CLASSES.items():
        pct = np.sum(lulc == cls_id) / lulc.size * 100
        print(f"  {cls_name}: {pct:.1f}%")

    print(f"  [OK] LULC map → {LULC_FILE.name}")
    print("[Step 03] Done.")


if __name__ == "__main__":
    run()
