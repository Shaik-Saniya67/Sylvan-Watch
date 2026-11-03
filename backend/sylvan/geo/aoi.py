"""Area-of-interest validation and UTM projection helpers."""
import math
from dataclasses import dataclass

from pyproj import Transformer


class InvalidAOI(ValueError):
    """Raised when a requested bounding box is malformed or too large."""


@dataclass(frozen=True)
class BBox:
    """Axis-aligned bounding box in WGS84 degrees."""

    west: float
    south: float
    east: float
    north: float

    def validate(self, max_side_km: float) -> "BBox":
        if not (-180 <= self.west < self.east <= 180 and -85 <= self.south < self.north <= 85):
            raise InvalidAOI("Bounding box must satisfy west < east and south < north within valid ranges.")
        width_km, height_km = self.size_km()
        if max(width_km, height_km) > max_side_km:
            raise InvalidAOI(
                f"Area is {width_km:.1f} x {height_km:.1f} km; the limit is {max_side_km:.0f} km per side."
            )
        return self

    @property
    def center(self) -> tuple[float, float]:
        return (self.west + self.east) / 2, (self.south + self.north) / 2

    def size_km(self) -> tuple[float, float]:
        """Approximate width and height in km (equirectangular, adequate for validation)."""
        lat = math.radians(self.center[1])
        return (self.east - self.west) * 111.32 * math.cos(lat), (self.north - self.south) * 110.57


def utm_epsg(lon: float, lat: float) -> int:
    """EPSG code of the UTM zone containing a lon/lat point."""
    zone = int((lon + 180) // 6) + 1
    return (32600 if lat >= 0 else 32700) + zone


def to_utm_bounds(bbox: BBox, epsg: int) -> tuple[float, float, float, float]:
    """Project all four corners to UTM and return (xmin, ymin, xmax, ymax)."""
    transformer = Transformer.from_crs(4326, epsg, always_xy=True)
    corners = [(bbox.west, bbox.south), (bbox.west, bbox.north), (bbox.east, bbox.south), (bbox.east, bbox.north)]
    xs, ys = zip(*(transformer.transform(lon, lat) for lon, lat in corners), strict=True)
    return min(xs), min(ys), max(xs), max(ys)
