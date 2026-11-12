"""Regenerate synthetic format variants of the names-only regional lineup."""

import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
VARIANTS = ("region_dash", "region_colon", "plain_parentheses", "no_callsign")


def format_name(name, variant):
    """Change presentation only; never infer metadata from channel names."""
    parts = name.split(" | ")
    if len(parts) not in (2, 3) or parts[0] not in {"US", "UK", "CA", "QC"}:
        raise ValueError(f"Unexpected fixture format: {name!r}")
    region, channel = parts[:2]
    callsign = parts[2] if len(parts) == 3 else None
    if variant == "region_dash":
        return " - ".join(parts)
    if variant == "region_colon":
        return f"{region}: {channel}" + (f" ({callsign})" if callsign else "")
    if variant == "plain_parentheses":
        return channel + (f" ({callsign})" if callsign else "")
    if variant == "no_callsign":
        return channel
    raise ValueError(f"Unknown fixture variant: {variant}")


def make_variants(source):
    return {variant: {group: [format_name(name, variant) for name in names]
                      for group, names in source.items()} for variant in VARIANTS}


def main():
    source = json.loads((FIXTURES / "regional_lineup.json").read_text(encoding="utf-8"))
    for variant, groups in make_variants(source).items():
        path = FIXTURES / f"regional_lineup.{variant}.json"
        path.write_text(json.dumps(groups, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
