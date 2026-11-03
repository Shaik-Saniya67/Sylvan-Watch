"""Chip files: decode Earth Engine downloads and write/read the project's multi-band GeoTIFF format."""
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.io import MemoryFile
from rasterio.transform import Affine

from sylvan.config import Settings
from sylvan.constants import CHIP_BANDS
from sylvan.data import gee_client
from sylvan.data.gee_client import ChipRequest
from sylvan.geo.aoi import BBox
from sylvan.geo.tiling import Tile, grid_for_bbox

MIN_TILE_PX = 128   # edge tiles smaller than this are skipped for training sites


def decode_download(content: bytes) -> tuple[np.ndarray, Affine, CRS]:
    """Decode an Earth Engine GEO_TIFF response (single multi-band tif, or a zip of per-band tifs)."""
    if content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = {n: archive.read(n) for n in archive.namelist() if n.endswith(".tif")}
        layers, transform, crs = [], None, None
        for band in CHIP_BANDS:
            name = next((n for n in members if n.endswith(f".{band}.tif")), None)
            if name is None:
                raise ValueError(f"Download archive is missing band '{band}'.")
            with MemoryFile(members[name]) as mem, mem.open() as src:
                layers.append(src.read(1))
                transform, crs = src.transform, src.crs
        return np.stack(layers), transform, crs
    with MemoryFile(content) as mem, mem.open() as src:
        return src.read(), src.transform, src.crs


def write_chip(path: Path, data: np.ndarray, transform: Affine, crs: CRS, tags: dict[str, str]) -> None:
    """Write int16 chip with band descriptions and provenance tags."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff", height=data.shape[1], width=data.shape[2], count=data.shape[0],
                       dtype="int16", crs=crs, transform=transform, compress="deflate") as dst:
        dst.write(data.astype(np.int16))
        for i, name in enumerate(CHIP_BANDS, start=1):
            dst.set_band_description(i, name)
        dst.update_tags(**tags)


def provenance_tags(settings: Settings, request: ChipRequest, extra: dict | None = None) -> dict[str, str]:
    return {
        "before_year": str(request.before_year), "after_year": str(request.after_year),
        "season_months": json.dumps(request.season_months),
        "s2_asset": settings.s2_asset, "hansen_asset": settings.hansen_asset,
        "worldcover_asset": settings.worldcover_asset,
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        **{k: str(v) for k, v in (extra or {}).items()},
    }


def fetch_chips(
    settings: Settings, bbox: BBox, request: ChipRequest, out_dir: Path, prefix: str,
    extra_tags: dict | None = None, on_tile=None, skip_small: bool = False,
) -> list[tuple[Tile, Path]]:
    """Download every tile of `bbox` into `out_dir` (existing files are reused). Returns (tile, path) pairs."""
    grid = grid_for_bbox(bbox)
    tiles = grid.tiles()
    if skip_small:
        tiles = [t for t in tiles if min(t.height, t.width) >= MIN_TILE_PX]
    image = gee_client.build_chip_image(settings, request, (bbox.west, bbox.south, bbox.east, bbox.north))
    results = []
    for i, tile in enumerate(tiles, start=1):
        path = out_dir / f"{prefix}_r{tile.row_off}_c{tile.col_off}.tif"
        if not path.exists():
            content = gee_client.download_tile(settings, image, tile, grid.epsg)
            data, transform, crs = decode_download(content)
            if data.shape != (len(CHIP_BANDS), tile.height, tile.width):
                raise ValueError(f"Unexpected download shape {data.shape} for tile {tile}.")
            write_chip(path, data, transform, crs, provenance_tags(settings, request, extra_tags))
        results.append((tile, path))
        if on_tile:
            on_tile(i, len(tiles))
    return results
