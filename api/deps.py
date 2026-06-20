"""
Shared FastAPI dependencies.
"""

from fastapi import Query, HTTPException

from pipeline.config import CITIES, DEFAULT_CITY


def get_city_id(city: str = Query(DEFAULT_CITY, description="City identifier, e.g. 'new_delhi'")) -> str:
    """Validate the ?city= query param against the known city registry."""
    if city not in CITIES:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown city '{city}'. Available: {', '.join(sorted(CITIES))}",
        )
    return city
