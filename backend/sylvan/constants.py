"""Shared constants: band layout of a data chip and fixed processing parameters."""

# Sentinel-2 L2A bands used by every model (10 m native or resampled to 10 m by Earth Engine).
S2_BANDS: tuple[str, ...] = ("B2", "B3", "B4", "B8", "B11", "B12")
BAND_INDEX: dict[str, int] = {name: i for i, name in enumerate(S2_BANDS)}

# Band order of the multi-band GeoTIFF ("chip") written by the acquisition step.
# Reflectances are stored as int16 = surface reflectance x 10000 (Sentinel-2 native scaling).
CHIP_BANDS: tuple[str, ...] = (
    *(f"before_{b}" for b in S2_BANDS),
    *(f"after_{b}" for b in S2_BANDS),
    "n_before",       # number of cloud-free observations behind the "before" composite
    "n_after",        # number of cloud-free observations behind the "after" composite
    "treecover2000",  # Hansen GFC tree cover in 2000 (%)
    "lossyear",       # Hansen GFC loss year (0 = no loss, 1..N = 2001..2000+N)
    "landcover",      # ESA WorldCover class (10 = tree cover, 40 = cropland, ...)
)

REFLECTANCE_SCALE = 10_000.0
PIXEL_SIZE_M = 10
TILE_SIZE_PX = 512          # download tile edge; keeps each Earth Engine request < 48 MB
MODEL_DIVISOR = 16          # U-Net input sizes are padded to a multiple of 2**4

WORLDCOVER_CLASSES: dict[int, str] = {
    0: "No data", 10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland",
    50: "Built-up", 60: "Bare / sparse vegetation", 70: "Snow and ice", 80: "Water",
    90: "Herbaceous wetland", 95: "Mangroves", 100: "Moss and lichen",
}
