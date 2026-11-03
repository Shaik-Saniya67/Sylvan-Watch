"""One-off dataset audit for training/evaluation. Does not modify chips or labels."""
from collections import Counter

import numpy as np
from _common import DEFAULT_SITES

from sylvan.config import get_settings
from sylvan.ml.dataset import load_sites, load_split
from sylvan.ml.labels import hansen_labels, pair_labels


def main() -> None:
    settings = get_settings()
    sites = load_sites(DEFAULT_SITES)
    print("storage", settings.storage_dir.resolve())
    print("tree_cover_threshold", settings.tree_cover_threshold)
    print("hansen_asset", settings.hansen_asset)
    for split in ("train", "val", "test"):
        pairs = load_split(settings, sites, split)
        print(f"\n=== {split} n_chips={len(pairs)} ===")
        by_site: dict[str, list] = {}
        for pair in pairs:
            by_site.setdefault(pair.meta.get("site"), []).append(pair)
        for site, plist in by_site.items():
            shapes = Counter(p.shape for p in plist)
            years = Counter((p.meta.get("before_year"), p.meta.get("after_year")) for p in plist)
            ly_hist: Counter[int] = Counter()
            domain_px = loss_px = valid_px = forest_px = ly_in_window = 0
            for p in plist:
                valid_px += int(p.valid.sum())
                loss, domain = pair_labels(p, settings.tree_cover_threshold)
                domain_px += int(domain.sum())
                loss_px += int(loss.sum())
                _, forest = hansen_labels(
                    p.treecover,
                    p.lossyear,
                    int(p.meta["before_year"]),
                    int(p.meta["after_year"]),
                    settings.tree_cover_threshold,
                )
                forest_px += int(forest.sum())
                vals, counts = np.unique(p.lossyear, return_counts=True)
                for value, count in zip(vals, counts, strict=True):
                    ly_hist[int(value)] += int(count)
                ly_in_window += int(((p.lossyear >= 20) & (p.lossyear <= 23)).sum())
            print(f"  {site}: chips={len(plist)} shapes={dict(shapes)} years={dict(years)}")
            rate = None if not domain_px else loss_px / domain_px
            print(
                f"    valid_px={valid_px} forest_at_before={forest_px} "
                f"domain={domain_px} loss={loss_px} loss_rate={rate}"
            )
            print(f"    lossyear 20-23 pixels (any canopy)={ly_in_window}")
            print(f"    lossyear top={ly_hist.most_common(12)}")
            print(f"    sample meta={plist[0].meta}")


if __name__ == "__main__":
    main()
