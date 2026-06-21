"""
Configuration for the Urban Heat MVP pipeline.
All constants, AOI bounds, CRS settings, and file paths.
"""

import os
from pathlib import Path

# ─── Project Paths ───────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SCENARIOS_DIR = DATA_DIR / "scenarios"
MODEL_DIR = PROJECT_ROOT / "models" / "artifacts"

# Create directories
for d in [RAW_DIR, PROCESSED_DIR, SCENARIOS_DIR, MODEL_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ─── Target City: Phoenix, AZ (legacy default — kept for the unused
#     real-data extraction scripts 01_download.py..07_feature_engineering.py,
#     which are not part of the active synthetic-data demo pipeline) ──
CITY_NAME = "Phoenix, AZ"
CITY_BBOX = {
    "west": -112.35,
    "south": 33.28,
    "east": -111.78,
    "north": 33.72,
}

# CRS
CRS_WGS84 = "EPSG:4326"
CRS_UTM = "EPSG:32612"  # UTM Zone 12N (Phoenix) — legacy default, see above


def utm_epsg_for(lon: float, lat: float) -> str:
    """Compute the correct UTM zone EPSG code for any lon/lat, so each
    city's grid is projected into its own local UTM zone instead of
    reusing Phoenix's fixed zone 12N (which would distort distances
    for cities elsewhere in the world)."""
    zone = int((lon + 180) / 6) + 1
    return f"EPSG:{32600 + zone if lat >= 0 else 32700 + zone}"


# ─── Multi-City Registry ─────────────────────────────────────────
# Each entry drives synthetic data generation for that city: its grid
# extent (bbox), a rough "where's the water" reference line used by
# the same proximity-to-water model as the original Phoenix script
# (water_axis "lat"/"lon" + water_value = the coordinate of a river/
# coast line), and climate parameters that shift the synthetic LST
# baseline so cities actually look climatically different from each
# other instead of all converging on Phoenix's desert profile.
CITIES = {
    "new_delhi": {
        "name": "New Delhi", "state": "Delhi", "country": "India",
        "bbox": {"west": 76.95, "south": 28.40, "east": 77.45, "north": 28.85},
        "center": (77.20, 28.61),
        "water_axis": "lon", "water_value": 77.25,  # Yamuna river
        "coastal": False,
        "base_temp_c": 33.0, "air_temp_baseline": 44.0, "veg_shift": -0.05,
        "season_label": "Apr–Jun 2026",
    },
    "mumbai": {
        "name": "Mumbai", "state": "Maharashtra", "country": "India",
        "bbox": {"west": 72.77, "south": 18.89, "east": 72.98, "north": 19.27},
        "center": (72.88, 19.08),
        "water_axis": "lon", "water_value": 72.78,  # Arabian Sea coast
        "coastal": True,
        "base_temp_c": 27.0, "air_temp_baseline": 34.0, "veg_shift": 0.0,
        "season_label": "Mar–May 2026",
    },
    "bengaluru": {
        "name": "Bengaluru", "state": "Karnataka", "country": "India",
        "bbox": {"west": 77.45, "south": 12.85, "east": 77.75, "north": 13.14},
        "center": (77.59, 12.97),
        "water_axis": "lat", "water_value": 12.97,  # lakes (Bellandur etc.)
        "coastal": False,
        "base_temp_c": 23.0, "air_temp_baseline": 33.0, "veg_shift": 0.08,
        "season_label": "Mar–May 2026",
    },
    "chennai": {
        "name": "Chennai", "state": "Tamil Nadu", "country": "India",
        "bbox": {"west": 80.15, "south": 12.90, "east": 80.32, "north": 13.23},
        "center": (80.27, 13.08),
        "water_axis": "lon", "water_value": 80.30,  # Bay of Bengal coast
        "coastal": True,
        "base_temp_c": 29.0, "air_temp_baseline": 38.0, "veg_shift": -0.02,
        "season_label": "Apr–Jun 2026",
    },
    "kolkata": {
        "name": "Kolkata", "state": "West Bengal", "country": "India",
        "bbox": {"west": 88.25, "south": 22.45, "east": 88.45, "north": 22.65},
        "center": (88.36, 22.57),
        "water_axis": "lon", "water_value": 88.35,  # Hooghly river
        "coastal": False,
        "base_temp_c": 29.0, "air_temp_baseline": 36.0, "veg_shift": 0.03,
        "season_label": "Apr–Jun 2026",
    },
    "hyderabad": {
        "name": "Hyderabad", "state": "Telangana", "country": "India",
        "bbox": {"west": 78.30, "south": 17.25, "east": 78.60, "north": 17.55},
        "center": (78.49, 17.39),
        "water_axis": "lon", "water_value": 78.47,  # Hussain Sagar
        "coastal": False,
        "base_temp_c": 28.0, "air_temp_baseline": 40.0, "veg_shift": -0.02,
        "season_label": "Apr–Jun 2026",
    },
    "pune": {
        "name": "Pune", "state": "Maharashtra", "country": "India",
        "bbox": {"west": 73.75, "south": 18.45, "east": 73.95, "north": 18.65},
        "center": (73.86, 18.52),
        "water_axis": "lat", "water_value": 18.52,  # Mula-Mutha rivers
        "coastal": False,
        "base_temp_c": 25.0, "air_temp_baseline": 36.0, "veg_shift": 0.03,
        "season_label": "Mar–May 2026",
    },
    "ahmedabad": {
        "name": "Ahmedabad", "state": "Gujarat", "country": "India",
        "bbox": {"west": 72.45, "south": 22.95, "east": 72.70, "north": 23.15},
        "center": (72.58, 23.02),
        "water_axis": "lon", "water_value": 72.58,  # Sabarmati river
        "coastal": False,
        "base_temp_c": 32.0, "air_temp_baseline": 43.0, "veg_shift": -0.08,
        "season_label": "Apr–Jun 2026",
    },
    "jaipur": {
        "name": "Jaipur", "state": "Rajasthan", "country": "India",
        "bbox": {"west": 75.70, "south": 26.80, "east": 75.90, "north": 27.00},
        "center": (75.79, 26.91),
        "water_axis": "lat", "water_value": 26.92,
        "coastal": False,
        "base_temp_c": 31.0, "air_temp_baseline": 42.0, "veg_shift": -0.10,
        "season_label": "Apr–Jun 2026",
    },
    "lucknow": {
        "name": "Lucknow", "state": "Uttar Pradesh", "country": "India",
        "bbox": {"west": 80.85, "south": 26.75, "east": 81.05, "north": 26.95},
        "center": (80.95, 26.85),
        "water_axis": "lat", "water_value": 26.85,  # Gomti river
        "coastal": False,
        "base_temp_c": 30.0, "air_temp_baseline": 42.0, "veg_shift": 0.0,
        "season_label": "Apr–Jun 2026",
    },
    "surat": {
        "name": "Surat", "state": "Gujarat", "country": "India",
        "bbox": {"west": 72.75, "south": 21.10, "east": 72.95, "north": 21.30},
        "center": (72.83, 21.17),
        "water_axis": "lon", "water_value": 72.83,  # Tapi river estuary
        "coastal": True,
        "base_temp_c": 29.0, "air_temp_baseline": 37.0, "veg_shift": -0.03,
        "season_label": "Apr–Jun 2026",
    },
    "kochi": {
        "name": "Kochi", "state": "Kerala", "country": "India",
        "bbox": {"west": 76.20, "south": 9.90, "east": 76.40, "north": 10.10},
        "center": (76.27, 9.93),
        "water_axis": "lon", "water_value": 76.22,  # backwaters / Arabian Sea
        "coastal": True,
        "base_temp_c": 27.0, "air_temp_baseline": 33.0, "veg_shift": 0.10,
        "season_label": "Mar–May 2026",
    },
    "chandigarh": {
        "name": "Chandigarh", "state": "Chandigarh", "country": "India",
        "bbox": {"west": 76.70, "south": 30.65, "east": 76.85, "north": 30.80},
        "center": (76.78, 30.73),
        "water_axis": "lat", "water_value": 30.72,  # Sukhna Lake
        "coastal": False,
        "base_temp_c": 29.0, "air_temp_baseline": 40.0, "veg_shift": 0.08,
        "season_label": "Apr–Jun 2026",
    },
    "nagpur": {
        # Sourced: IMD/climate normals put Nagpur's May average daily high
        # around 44°C, among the hottest of any major Indian city.
        "name": "Nagpur", "state": "Maharashtra", "country": "India",
        "bbox": {"west": 78.95, "south": 21.05, "east": 79.23, "north": 21.25},
        "center": (79.09, 21.15),
        "water_axis": "lat", "water_value": 21.15,  # Nag river
        "coastal": False,
        "base_temp_c": 33.0, "air_temp_baseline": 44.0, "veg_shift": -0.02,
        "season_label": "Apr–Jun 2026",
    },
    "patna": {
        # Sourced: ~40°C average daily high in May (pre-monsoon peak).
        "name": "Patna", "state": "Bihar", "country": "India",
        "bbox": {"west": 84.95, "south": 25.55, "east": 85.30, "north": 25.70},
        "center": (85.14, 25.60),
        "water_axis": "lat", "water_value": 25.62,  # Ganges river
        "coastal": False,
        "base_temp_c": 30.0, "air_temp_baseline": 40.0, "veg_shift": -0.05,
        "season_label": "Apr–Jun 2026",
    },
    "bhopal": {
        # Sourced: ~41-42°C average daily high in May.
        "name": "Bhopal", "state": "Madhya Pradesh", "country": "India",
        "bbox": {"west": 77.30, "south": 23.15, "east": 77.55, "north": 23.35},
        "center": (77.41, 23.26),
        "water_axis": "lon", "water_value": 77.38,  # Upper/Lower Lakes
        "coastal": False,
        "base_temp_c": 31.0, "air_temp_baseline": 42.0, "veg_shift": 0.05,
        "season_label": "Apr–Jun 2026",
    },
    "visakhapatnam": {
        # Sourced: coastal city, ~35-36°C average daily high in May —
        # notably milder than inland cities thanks to the sea breeze,
        # despite high humidity.
        "name": "Visakhapatnam", "state": "Andhra Pradesh", "country": "India",
        "bbox": {"west": 83.10, "south": 17.60, "east": 83.35, "north": 17.80},
        "center": (83.22, 17.69),
        "water_axis": "lon", "water_value": 83.32,  # Bay of Bengal coast
        "coastal": True,
        "base_temp_c": 27.0, "air_temp_baseline": 36.0, "veg_shift": 0.04,
        "season_label": "Apr–Jun 2026",
    },
    "guwahati": {
        # Sourced: northeastern climate — monsoon arrives earlier here, so
        # the pre-monsoon heat is far milder than the rest of India
        # (~30-32°C average daily high), despite high humidity.
        "name": "Guwahati", "state": "Assam", "country": "India",
        "bbox": {"west": 91.60, "south": 26.05, "east": 91.85, "north": 26.25},
        "center": (91.74, 26.14),
        "water_axis": "lat", "water_value": 26.18,  # Brahmaputra river
        "coastal": False,
        "base_temp_c": 23.0, "air_temp_baseline": 31.0, "veg_shift": 0.10,
        "season_label": "Mar–May 2026",
    },
    "vijayawada": {
        # Sourced: ~41°C average daily high in May.
        "name": "Vijayawada", "state": "Andhra Pradesh", "country": "India",
        "bbox": {"west": 80.55, "south": 16.42, "east": 80.75, "north": 16.58},
        "center": (80.65, 16.51),
        "water_axis": "lat", "water_value": 16.50,  # Krishna river
        "coastal": False,
        "base_temp_c": 30.0, "air_temp_baseline": 41.0, "veg_shift": -0.03,
        "season_label": "Apr–Jun 2026",
    },
    "coimbatore": {
        # Sourced: ~36-37°C average daily high in April (hottest month) —
        # milder than most inland Tamil Nadu cities due to elevation and
        # proximity to the Western Ghats ("Kovai breeze").
        "name": "Coimbatore", "state": "Tamil Nadu", "country": "India",
        "bbox": {"west": 76.85, "south": 10.93, "east": 77.08, "north": 11.10},
        "center": (76.96, 11.02),
        "water_axis": "lat", "water_value": 10.99,  # Noyyal river
        "coastal": False,
        "base_temp_c": 24.0, "air_temp_baseline": 36.0, "veg_shift": 0.06,
        "season_label": "Mar–May 2026",
    },
}

DEFAULT_CITY = "new_delhi"


def is_valid_city(city_id: str) -> bool:
    return city_id in CITIES


def list_cities() -> list:
    """Return cities sorted alphabetically by display name, for the
    /api/v1/cities endpoint and the frontend's city picker."""
    return [
        {"id": cid, **{k: v for k, v in c.items() if k not in ("water_axis", "water_value")}}
        for cid, c in sorted(CITIES.items(), key=lambda kv: kv[1]["name"])
    ]

# ─── Grid Settings ───────────────────────────────────────────────
GRID_CELL_SIZE_M = 500  # meters
GRID_BUFFER_M = 100     # buffer around AOI

# ─── Analysis Period ─────────────────────────────────────────────
ANALYSIS_YEAR = 2026
ANALYSIS_MONTHS = [4, 5, 6]  # Apr, May, Jun (pre-monsoon hot season, India)
DATE_START = "2026-04-01"
DATE_END = "2026-06-30"

# ─── Landsat 8 Settings ─────────────────────────────────────────
LANDSAT_COLLECTION = "landsat-c2l2-st"
LANDSAT_LST_BAND = "ST_B10"
LANDSAT_SCALE_FACTOR = 0.00341802
LANDSAT_OFFSET = 149.0
MAX_CLOUD_COVER = 20  # percent

# ─── Sentinel-2 Settings ────────────────────────────────────────
SENTINEL2_BANDS = ["B02", "B03", "B04", "B08", "B11", "B12"]
LULC_CLASSES = {
    0: "Impervious",
    1: "Vegetation",
    2: "Bare Soil",
    3: "Water",
    4: "Building",
    5: "Shadow",
}
LULC_COLORS = {
    0: "#888888",
    1: "#2E7D32",
    2: "#D4A574",
    3: "#1565C0",
    4: "#F44336",
    5: "#424242",
}

# ─── ERA5 Variables ──────────────────────────────────────────────
ERA5_VARIABLES = [
    "2m_temperature",
    "2m_dewpoint_temperature",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "surface_solar_radiation_downwards",
]

# ─── Hotspot Thresholds ─────────────────────────────────────────
HOTSPOT_TIERS = {
    "critical": 2.0,   # > mean + 2*std
    "high": 1.0,        # > mean + 1*std
    "moderate": 0.0,    # > mean
    "normal": -1.0,     # > mean - 1*std
    "cool": float("-inf"),
}

TIER_COLORS = {
    "critical": "#FF1744",
    "high": "#FF9100",
    "moderate": "#FFD600",
    "normal": "#00C853",
    "cool": "#2979FF",
}

# ─── Intervention Parameters ────────────────────────────────────
INTERVENTIONS = {
    "tree_cover": {
        "label": "Tree Cover",
        "emoji": "🌳",
        "feature_mods": {
            "frac_vegetation": 0.30,
            "ndvi_mean": 0.15,
            "tree_canopy_frac": 0.30,
            "frac_impervious": -0.15,
        },
        "cost_per_km2_million": 2.5,
    },
    "green_roofs": {
        "label": "Green Roofs",
        "emoji": "🌿",
        "feature_mods": {
            "frac_vegetation": 0.15,
            "ndbi_mean": -0.08,
            "frac_impervious": -0.10,
        },
        "cost_per_km2_million": 4.0,
    },
    "cool_roofs": {
        "label": "Cool Roofs",
        "emoji": "🏢",
        "feature_mods": {
            "ndbi_mean": -0.12,
            "solar_radiation": -0.15,  # fractional reduction
        },
        "cost_per_km2_million": 1.5,
    },
    "water_bodies": {
        "label": "Water Bodies",
        "emoji": "💧",
        "feature_mods": {
            "water_area_frac": 0.05,
            "dist_to_water": -200,  # absolute reduction in meters
        },
        "cost_per_km2_million": 6.0,
    },
    "albedo_improvement": {
        "label": "Albedo Improvement",
        "emoji": "⬜",
        "feature_mods": {
            "ndbi_mean": -0.06,
            "solar_radiation": -0.10,
        },
        "cost_per_km2_million": 1.0,
    },
}

# ─── Output Files (legacy single-city paths, unused real-data scripts) ──
GRID_FILE = PROCESSED_DIR / "grid.geojson"
FEATURES_FILE = PROCESSED_DIR / "features.parquet"
LST_COMPOSITE_FILE = PROCESSED_DIR / "lst_composite.tif"
LULC_FILE = PROCESSED_DIR / "lulc_classified.tif"
MODEL_FILE = MODEL_DIR / "xgb_lst_model.json"
SCALER_FILE = MODEL_DIR / "scaler.joblib"
SHAP_FILE = MODEL_DIR / "shap_values.parquet"
SCENARIO_RESULTS_FILE = SCENARIOS_DIR / "scenario_results.parquet"

# ─── Per-City Paths (active multi-city synthetic demo pipeline) ────
# Model artifacts (MODEL_FILE/SCALER_FILE/SHAP_FILE above) are SHARED
# across all cities — one model trained on combined data from every
# city. Only grid/features/presets are per-city.

def city_processed_dir(city_id: str) -> Path:
    d = PROCESSED_DIR / city_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def city_scenarios_dir(city_id: str) -> Path:
    d = SCENARIOS_DIR / city_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def city_grid_file(city_id: str) -> Path:
    return city_processed_dir(city_id) / "grid.geojson"


def city_features_file(city_id: str) -> Path:
    return city_processed_dir(city_id) / "features.parquet"


def city_presets_file(city_id: str) -> Path:
    return city_scenarios_dir(city_id) / "presets.json"
