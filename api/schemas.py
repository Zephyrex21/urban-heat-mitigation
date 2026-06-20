"""
Pydantic schemas for API request/response models.
"""

from pydantic import BaseModel, Field
from typing import Optional


# ─── Grid ────────────────────────────────────────────────────────

class GridCellProperties(BaseModel):
    grid_id: str
    lst_mean: float
    lst_max: float
    tier: str
    delta_above_mean: float
    priority_score: float
    frac_impervious: float
    frac_vegetation: float
    frac_bare_soil: float
    frac_water: float
    ndvi_mean: float
    ndbi_mean: float
    building_density: float
    building_height_mean: float
    road_density: float
    park_area_frac: float
    tree_canopy_frac: float
    dist_to_water: float
    water_area_frac: float
    air_temp_max: float
    wind_speed_mean: float
    solar_radiation: float


# ─── Hotspots ────────────────────────────────────────────────────

class CityStats(BaseModel):
    mean_lst: float
    std_lst: float
    total_cells: int
    hotspot_cells: int
    hotspot_pct: float


class HotspotCluster(BaseModel):
    cluster_id: int
    cell_count: int
    area_km2: float
    mean_lst: float
    max_lst: float
    delta_above_mean: float
    primary_driver: str
    priority_score: float
    centroid: list[float]  # [lon, lat]
    grid_ids: list[str]


class HotspotResponse(BaseModel):
    city_stats: CityStats
    clusters: list[HotspotCluster]


# ─── Drivers ─────────────────────────────────────────────────────

class FeatureImportance(BaseModel):
    feature: str
    importance: float
    direction: str  # "positive" or "negative"


class ShapValue(BaseModel):
    feature: str
    value: float
    shap: float


class CellExplanation(BaseModel):
    grid_id: str
    predicted_lst: float
    base_value: float
    shap_values: list[ShapValue]


class DriversResponse(BaseModel):
    global_importance: list[FeatureImportance]
    cell_explanation: Optional[CellExplanation] = None


# ─── Scenarios ───────────────────────────────────────────────────

class InterventionInput(BaseModel):
    type: str = Field(..., description="Intervention type key")
    intensity: float = Field(..., ge=0, le=1, description="Intensity 0-1")


class ScenarioRequest(BaseModel):
    target_cells: Optional[list[str]] = Field(
        None, description="Grid IDs to target (None = all hotspots)"
    )
    interventions: list[InterventionInput]


class ScenarioSummary(BaseModel):
    cells_modified: int
    mean_cooling_c: float
    max_cooling_c: float
    hotspots_before: int
    hotspots_after: int
    hotspot_reduction_pct: float
    cost_estimate_m: float
    cost_efficiency_c_per_m: float


class CellResult(BaseModel):
    grid_id: str
    lst_before: float
    lst_after: float
    delta_t: float
    tier_before: str
    tier_after: str


class ScenarioResponse(BaseModel):
    summary: ScenarioSummary
    cell_results: list[CellResult]


class PresetScenario(BaseModel):
    scenario_id: str
    name: str
    description: str
    interventions: dict[str, float]
    mean_cooling_c: float
    max_cooling_c: float
    hotspots_before: int
    hotspots_after: int
    hotspot_reduction_pct: float
    cost_estimate_m: float
    cost_efficiency: float


# ─── Overview ────────────────────────────────────────────────────

class OverviewResponse(BaseModel):
    city: str
    analysis_period: str
    grid_cells: int
    mean_lst_c: float
    max_lst_c: float
    min_lst_c: float
    std_lst_c: float
    uhi_intensity_c: float
    hotspot_area_km2: float
    hotspot_count: int
    top_driver: str
    best_intervention: str
    max_potential_cooling_c: float
    tier_distribution: dict[str, int]
