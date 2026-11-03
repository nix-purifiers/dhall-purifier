"""Rebuild the actual compiled native semantic cache packages."""

import json
from pathlib import Path
import subprocess

repo = Path(__file__).resolve().parent.parent
system = subprocess.check_output(
    ["nix", "eval", "--impure", "--raw", "--expr", "builtins.currentSystem"], text=True
).strip()
output = subprocess.check_output(
    [
        "nix",
        "build",
        "--no-link",
        "--print-out-paths",
        str(repo) + "#checks." + system + ".environment",
    ],
    text=True,
).strip()
manifest = json.loads((Path(output) / "manifest.json").read_text())
assert len(manifest["packages"]) == 1
for library in manifest["packages"].values():
    drv = subprocess.check_output(
        ["nix-store", "-q", "--deriver", library], text=True
    ).strip()
    subprocess.run(["nix-store", "--realise", drv, "--check"], check=True)

print("Compiled Dhall native semantic cache packages rebuilt identically")
