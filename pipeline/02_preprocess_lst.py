"""
Step 02: Preprocess Landsat 8 & ECOSTRESS LST

Calibrates raw thermal bands to LST in °C, composites multiple scenes,
and produces a single fused LST raster.
"""

import numpy as np
from pathlib import Path

from pipeline.config import (
    RAW_DIR, PROCESSED_DIR,
    LANDSAT_SCALE_FACTOR, LANDSAT_OFFSET,
    LST_COMPOSITE_FILE, CRS_UTM
)


def calibrate_landsat_lst(input_path: Path, output_path: Path):
    """
    Convert Landsat 8 ST_B10 digital numbers to LST in Celsius.
    
    Formula:
        LST_K = DN * 0.00341802 + 149.0
        LST_C = LST_K - 273.15
    """
    try:
        import rasterio
        from rasterio.warp import calculate_default_transform, reproject, Resampling
    except ImportError:
        print("  [SKIP] rasterio not installed — use synthetic data instead")
        return None

    with rasterio.open(input_path) as src:
        data = src.read(1).astype(np.float32)
        profile = src.profile.copy()

    # Apply calibration
    lst_kelvin = data * LANDSAT_SCALE_FACTOR + LANDSAT_OFFSET
    lst_celsius = lst_kelvin - 273.15

    # Mask invalid values
    lst_celsius[lst_celsius < -50] = np.nan
    lst_celsius[lst_celsius > 80] = np.nan

    profile.update(dtype="float32", nodata=np.nan)
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(lst_celsius, 1)

    print(f"  [OK] LST range: {np.nanmin(lst_celsius):.1f}°C to {np.nanmax(lst_celsius):.1f}°C")
    return output_path


def composite_lst_scenes(scene_paths: list[Path], output_path: Path):
    """
    Create a pixel-wise median composite from multiple LST scenes.
    Reduces noise and fills cloud gaps.
    """
    try:
        import rasterio
    except ImportError:
        print("  [SKIP] rasterio not installed")
        return None

    arrays = []
    profile = None
    for p in scene_paths:
        with rasterio.open(p) as src:
            arrays.append(src.read(1))
            if profile is None:
                profile = src.profile.copy()

    stack = np.stack(arrays, axis=0)
    composite = np.nanmedian(stack, axis=0)

    profile.update(dtype="float32", count=1)
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(composite.astype(np.float32), 1)

    print(f"  [OK] Composite from {len(arrays)} scenes → {output_path.name}")
    return output_path


def fuse_landsat_ecostress(landsat_path: Path, ecostress_path: Path, output_path: Path,
                            weight_landsat: float = 0.6):
    """
    Weighted average fusion of Landsat and ECOSTRESS LST.
    ECOSTRESS provides higher temporal resolution, Landsat provides spatial consistency.
    """
    try:
        import rasterio
        from rasterio.warp import reproject, Resampling
    except ImportError:
        print("  [SKIP] rasterio not installed")
        return None

    with rasterio.open(landsat_path) as src_l:
        landsat = src_l.read(1).astype(np.float32)
        profile = src_l.profile.copy()

    with rasterio.open(ecostress_path) as src_e:
        eco_raw = src_e.read(1).astype(np.float32)
        # Resample ECOSTRESS (70m) to Landsat grid (30m)
        ecostress = np.empty_like(landsat)
        reproject(
            eco_raw, ecostress,
            src_transform=src_e.transform,
            src_crs=src_e.crs,
            dst_transform=src_l.transform,
            dst_crs=src_l.crs,
            resampling=Resampling.bilinear,
        )

    # Weighted fusion
    w_l = weight_landsat
    w_e = 1.0 - w_l
    fused = np.where(
        np.isnan(landsat), ecostress,
        np.where(np.isnan(ecostress), landsat,
                 w_l * landsat + w_e * ecostress)
    )

    profile.update(dtype="float32")
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(fused, 1)

    print(f"  [OK] Fused LST → {output_path.name}")
    return output_path


def run():
    """Run LST preprocessing pipeline."""
    print("[Step 02] Preprocessing LST...")
    
    landsat_dir = RAW_DIR / "landsat"
    ecostress_dir = RAW_DIR / "ecostress"

    # Find all Landsat scenes
    landsat_scenes = sorted(landsat_dir.glob("*.tif")) if landsat_dir.exists() else []
    ecostress_scenes = sorted(ecostress_dir.glob("*.tif")) if ecostress_dir.exists() else []

    if not landsat_scenes:
        print("  [WARN] No Landsat scenes found — use synthetic data")
        return

    # Calibrate each scene
    calibrated = []
    for scene in landsat_scenes:
        out = PROCESSED_DIR / f"lst_cal_{scene.stem}.tif"
        result = calibrate_landsat_lst(scene, out)
        if result:
            calibrated.append(result)

    # Composite Landsat
    if calibrated:
        landsat_composite = PROCESSED_DIR / "lst_landsat_composite.tif"
        composite_lst_scenes(calibrated, landsat_composite)

        # Fuse with ECOSTRESS if available
        if ecostress_scenes:
            eco_composite = PROCESSED_DIR / "lst_ecostress_composite.tif"
            composite_lst_scenes(
                [PROCESSED_DIR / f"lst_eco_{s.stem}.tif" for s in ecostress_scenes
                 if (PROCESSED_DIR / f"lst_eco_{s.stem}.tif").exists()],
                eco_composite
            )
            fuse_landsat_ecostress(landsat_composite, eco_composite, LST_COMPOSITE_FILE)
        else:
            # Just use Landsat composite
            import shutil
            shutil.copy(landsat_composite, LST_COMPOSITE_FILE)
            print("  [INFO] No ECOSTRESS data — using Landsat only")

    print("[Step 02] Done.")


if __name__ == "__main__":
    run()
