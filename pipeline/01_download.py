"""
Step 01: Data Acquisition Helpers

Downloads raw satellite and ancillary data for the Phoenix AOI.
In a real deployment, these pull from EarthExplorer, AppEEARS, CDS, and Geofabrik.
For the hackathon, we provide instructions + fallback to synthetic data.
"""

import os
from pathlib import Path
from pipeline.config import (
    RAW_DIR, CITY_BBOX, DATE_START, DATE_END,
    MAX_CLOUD_COVER, CITY_NAME
)


def download_landsat(output_dir: Path = RAW_DIR / "landsat"):
    """
    Download Landsat 8 Collection 2 Level 2 ST_B10 scenes.
    
    In production: Use USGS M2M API or landsatxplore.
    For hackathon: Use Google Earth Engine (GEE) Python API.
    
    GEE snippet:
        import ee
        ee.Initialize()
        
        aoi = ee.Geometry.Rectangle([west, south, east, north])
        collection = (ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
            .filterBounds(aoi)
            .filterDate('2023-06-01', '2023-08-31')
            .filter(ee.Filter.lt('CLOUD_COVER', 20))
            .select('ST_B10'))
        
        composite = collection.median().clip(aoi)
        
        task = ee.batch.Export.image.toDrive(
            image=composite,
            description='phoenix_lst_landsat',
            scale=30,
            region=aoi,
            crs='EPSG:32612'
        )
        task.start()
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[Landsat 8] Target: {output_dir}")
    print(f"  AOI: {CITY_BBOX}")
    print(f"  Date range: {DATE_START} to {DATE_END}")
    print(f"  Max cloud cover: {MAX_CLOUD_COVER}%")
    print("  → Use GEE or USGS EarthExplorer to download ST_B10 scenes")
    print("  → Fallback: run `python -m pipeline.generate_synthetic`")


def download_ecostress(output_dir: Path = RAW_DIR / "ecostress"):
    """
    Download ECOSTRESS LST (ECO2LSTE.001) from NASA AppEEARS.
    
    Steps:
    1. Go to https://appeears.earthdatacloud.nasa.gov/
    2. Create area sample for Phoenix bbox
    3. Select ECO2LSTE.001 product, LST layer
    4. Set dates: Jun-Aug 2023
    5. Download as GeoTIFF
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[ECOSTRESS] Target: {output_dir}")
    print(f"  → Use NASA AppEEARS: https://appeears.earthdatacloud.nasa.gov/")
    print(f"  → Product: ECO2LSTE.001, dates: {DATE_START} to {DATE_END}")


def download_sentinel2(output_dir: Path = RAW_DIR / "sentinel2"):
    """
    Download Sentinel-2 L2A bands for LULC classification.
    
    GEE snippet:
        collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(aoi)
            .filterDate('2023-06-01', '2023-08-31')
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
            .select(['B2','B3','B4','B8','B11','B12']))
        
        composite = collection.median().clip(aoi)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[Sentinel-2] Target: {output_dir}")
    print(f"  → Bands: B02, B03, B04, B08, B11, B12")
    print(f"  → Use GEE or Copernicus Open Access Hub")


def download_era5(output_dir: Path = RAW_DIR / "era5"):
    """
    Download ERA5-Land hourly data via CDS API.
    
    Requires: cdsapi package + CDS API key
    
    import cdsapi
    c = cdsapi.Client()
    c.retrieve('reanalysis-era5-land', {
        'variable': ['2m_temperature', '2m_dewpoint_temperature',
                     '10m_u_component_of_wind', '10m_v_component_of_wind',
                     'surface_solar_radiation_downwards'],
        'year': '2023',
        'month': ['06', '07', '08'],
        'day': [str(i).zfill(2) for i in range(1, 32)],
        'time': [f'{h:02d}:00' for h in range(24)],
        'area': [north, west, south, east],
        'format': 'netcdf',
    }, 'era5_phoenix_summer2023.nc')
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[ERA5] Target: {output_dir}")
    print(f"  → Use CDS API: https://cds.climate.copernicus.eu/")


def download_osm(output_dir: Path = RAW_DIR / "osm"):
    """
    Download OpenStreetMap PBF extract for Phoenix metro area.
    
    Source: Geofabrik (https://download.geofabrik.de/)
    Direct link: arizona-latest.osm.pbf → clip to Phoenix bbox
    
    Alternative: Use osmnx Python package for on-the-fly download:
        import osmnx as ox
        buildings = ox.features_from_bbox(north, south, east, west, tags={'building': True})
        roads = ox.features_from_bbox(north, south, east, west, tags={'highway': True})
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[OSM] Target: {output_dir}")
    print(f"  → Download from Geofabrik or use osmnx package")


def download_all():
    """Run all download helpers."""
    print(f"=" * 60)
    print(f"  Data Acquisition for {CITY_NAME}")
    print(f"=" * 60)
    download_landsat()
    print()
    download_ecostress()
    print()
    download_sentinel2()
    print()
    download_era5()
    print()
    download_osm()
    print()
    print("=" * 60)
    print("  All download instructions printed.")
    print("  For demo: run `python -m pipeline.generate_synthetic`")
    print("=" * 60)


if __name__ == "__main__":
    download_all()
