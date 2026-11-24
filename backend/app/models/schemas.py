from datetime import date
from math import isfinite
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AdvisoryRequest(StrictModel):
    location: str = Field(min_length=1, max_length=100)
    crop: str = Field(min_length=1, max_length=40)
    question: str = Field(min_length=1, max_length=500)


class SatelliteAnalyzeRequest(StrictModel):
    location: str | None = Field(default=None, min_length=1, max_length=100)
    date_from: date
    date_to: date
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    geometry: dict[str, Any] | None = None

    @field_validator("location")
    @classmethod
    def location_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Location must not be blank.")
        return value

    @model_validator(mode="after")
    def validate_date_window(self) -> "SatelliteAnalyzeRequest":
        if self.date_from > self.date_to:
            raise ValueError("date_from must be on or before date_to.")
        if (self.date_to - self.date_from).days > 90:
            raise ValueError("The satellite date range cannot exceed 90 days.")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Provide both latitude and longitude.")
        if self.geometry is None and self.location is None and self.latitude is None:
            raise ValueError("Provide a demo location, coordinates, or a GeoJSON area.")
        if self.geometry is not None:
            geometry_type = self.geometry.get("type")
            coordinates = self.geometry.get("coordinates")
            if geometry_type == "Point":
                if not isinstance(coordinates, (list, tuple)) or len(coordinates) != 2:
                    raise ValueError("Point geometry must contain [longitude, latitude].")
                _validate_point(coordinates[0], coordinates[1])
            elif geometry_type == "Polygon":
                if not isinstance(coordinates, (list, tuple)) or len(coordinates) != 1:
                    raise ValueError("Use a GeoJSON Polygon with one exterior ring.")
                ring = coordinates[0]
                if not isinstance(ring, (list, tuple)) or len(ring) < 4:
                    raise ValueError("The polygon exterior ring needs at least four positions.")
                points: list[tuple[float, float]] = []
                for point in ring:
                    if not isinstance(point, (list, tuple)) or len(point) < 2:
                        raise ValueError("Polygon positions must contain [longitude, latitude].")
                    _validate_point(point[0], point[1])
                    points.append((float(point[0]), float(point[1])))
                if points[0] != points[-1]:
                    raise ValueError("The polygon ring must end at its first position.")
                if max(x for x, _ in points) - min(x for x, _ in points) > 0.05 or max(y for _, y in points) - min(y for _, y in points) > 0.05:
                    raise ValueError("The field polygon must fit within a 0.05-degree bounding box.")
                if max(x for x, _ in points) == min(x for x, _ in points) or max(y for _, y in points) == min(y for _, y in points):
                    raise ValueError("The field polygon must enclose an area.")
            else:
                raise ValueError("Geometry must be a GeoJSON Point or Polygon.")
        return self


def _validate_point(longitude: Any, latitude: Any) -> None:
    try:
        lon, lat = float(longitude), float(latitude)
    except (TypeError, ValueError) as exc:
        raise ValueError("GeoJSON coordinates must be numeric.") from exc
    if not isfinite(lon) or not isfinite(lat) or not -180 <= lon <= 180 or not -90 <= lat <= 90:
        raise ValueError("GeoJSON coordinates must be within longitude [-180, 180] and latitude [-90, 90].")
