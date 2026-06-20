"""
Step 04: Extract ERA5 Weather Variables

Loads ERA5-Land reanalysis data, computes daily aggregations,
and interpolates to the 500m analysis grid.
"""

import numpy as np
from pathlib import Path

from pipeline.config import (
    RAW_DIR, PROCESSED_DIR, ERA5_VARIABLES,
    CITY_BBOX, DATE_START, DATE_END
)


def load_era5_netcdf(filepath: Path) -> dict:
    """
    Load ERA5 NetCDF and extract key variables.
    Returns dict of {variable_name: xarray.DataArray}.
    """
    try:
        import xarray as xr
    except ImportError:
        print("  [SKIP] xarray not installed")
        return {}

    ds = xr.open_dataset(filepath)
    bbox = CITY_BBOX
    ds = ds.sel(
        latitude=slice(bbox["north"], bbox["south"]),
        longitude=slice(bbox["west"], bbox["east"])
    )
    return {var: ds[var] for var in ds.data_vars if var in ERA5_VARIABLES}


def compute_daily_aggregates(hourly_data: dict) -> dict:
    """
    Compute daily aggregations from hourly ERA5 data.
    
    Returns:
        air_temp_max: Daily max 2m temperature (°C)
        wind_speed_mean: Daily mean wind speed (m/s)
        solar_radiation: Daily total downward solar radiation (W/m²)
        dewpoint_mean: Daily mean dewpoint (°C)
    """
    daily = {}

    if "2m_temperature" in hourly_data:
        t2m = hourly_data["2m_temperature"]
        daily["air_temp_max"] = (t2m - 273.15).resample(time="1D").max()
        daily["air_temp_mean"] = (t2m - 273.15).resample(time="1D").mean()

    if "2m_dewpoint_temperature" in hourly_data:
        d2m = hourly_data["2m_dewpoint_temperature"]
        daily["dewpoint_mean"] = (d2m - 273.15).resample(time="1D").mean()

    if "10m_u_component_of_wind" in hourly_data and "10m_v_component_of_wind" in hourly_data:
        u10 = hourly_data["10m_u_component_of_wind"]
        v10 = hourly_data["10m_v_component_of_wind"]
        wind_speed = np.sqrt(u10**2 + v10**2)
        daily["wind_speed_mean"] = wind_speed.resample(time="1D").mean()

    if "surface_solar_radiation_downwards" in hourly_data:
        ssrd = hourly_data["surface_solar_radiation_downwards"]
        daily["solar_radiation"] = ssrd.resample(time="1D").sum() / 3600  # J/m² → W/m²

    return daily


def interpolate_to_grid(era5_daily: dict, grid_centroids: np.ndarray) -> dict:
    """
    Bilinear interpolation of ERA5 grid (0.1°) to analysis grid centroids.
    
    Args:
        era5_daily: dict of daily xarray DataArrays
        grid_centroids: array of (lon, lat) for each grid cell
    
    Returns:
        dict of {variable: array of values per grid cell} averaged over analysis period
    """
    try:
        from scipy.interpolate import RegularGridInterpolator
    except ImportError:
        print("  [SKIP] scipy not installed")
        return {}

    result = {}
    for var_name, da in era5_daily.items():
        # Average over entire analysis period
        mean_field = da.mean(dim="time").values

        lat = da.latitude.values
        lon = da.longitude.values

        interp = RegularGridInterpolator(
            (lat[::-1], lon),  # lat must be ascending
            mean_field[::-1],
            method="linear",
            bounds_error=False,
            fill_value=None,
        )

        # Interpolate to grid centroids
        points = np.column_stack([grid_centroids[:, 1], grid_centroids[:, 0]])  # (lat, lon)
        result[var_name] = interp(points)

    return result


def run():
    """Run ERA5 extraction pipeline."""
    print("[Step 04] Extracting ERA5 weather data...")

    era5_dir = RAW_DIR / "era5"
    nc_files = list(era5_dir.glob("*.nc")) if era5_dir.exists() else []

    if not nc_files:
        print("  [WARN] No ERA5 NetCDF files found — use synthetic data")
        return

    # Load and aggregate
    hourly = load_era5_netcdf(nc_files[0])
    daily = compute_daily_aggregates(hourly)

    print(f"  [OK] Extracted {len(daily)} daily variables")
    for name in daily:
        print(f"    - {name}")

    print("[Step 04] Done.")


if __name__ == "__main__":
    run()
