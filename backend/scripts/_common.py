"""Shared CLI helpers."""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
DEFAULT_SITES = Path(__file__).resolve().parents[1] / "configs" / "sites.json"
