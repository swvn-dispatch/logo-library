"""Build a Dispatcharr plugin ZIP without modifying the source manifest."""

import argparse
import json
from pathlib import Path
import zipfile


def package(source, output_dir, version=None):
    source = Path(source)
    manifest = json.loads((source / "plugin.json").read_text(encoding="utf-8"))
    version = version or manifest["version"]
    if not version or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_" for c in version):
        raise ValueError("Invalid package version")
    manifest["version"] = version
    slug = manifest["name"].lower().replace(" ", "_")
    if not slug.replace("_", "").isalnum():
        raise ValueError("Invalid plugin name")
    output = Path(output_dir) / f"{slug.replace('_', '-')}-{version}.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if not path.is_file() or path.is_symlink() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            relative = path.relative_to(source)
            name = f"{slug}/{relative.as_posix()}"
            if relative.as_posix() == "plugin.json":
                archive.writestr(name, json.dumps(manifest, indent=2) + "\n")
            else:
                archive.write(path, name)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version")
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    print(package("src", args.output_dir, args.version))
