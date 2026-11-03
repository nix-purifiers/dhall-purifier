import hashlib
import json
import os
from pathlib import Path
import subprocess

from .common import environment, load


def prepare(root, companion):
    data = load(root, companion)
    generation = hashlib.sha256(
        companion.read_bytes() + os.environ["DHALL_PURIFIER_SDK"].encode()
    ).hexdigest()[:20]
    state = root / ".dhall-purifier" / generation
    state.mkdir(parents=True, exist_ok=True)
    expression = (
        "import "
        + json.dumps(
            os.environ["DHALL_PURIFIER_SDK"] + "/lib/dhall-purifier/nix/realize.nix"
        )
        + " {root="
        + json.dumps(str(root))
        + ";lockFile="
        + json.dumps(str(companion))
        + ";sdk="
        + json.dumps(os.environ["DHALL_PURIFIER_SDK"])
        + ";}"
    )
    built = subprocess.run(
        [
            "nix",
            "build",
            "--impure",
            "--expr",
            expression,
            "--out-link",
            str(state / "environment-profile"),
            "--print-out-paths",
        ],
        text=True,
        capture_output=True,
    )
    if built.returncode:
        raise ValueError(built.stdout + built.stderr)
    profile = json.loads(Path(built.stdout.strip()).read_text())
    output = Path(profile["output"])
    manifest = json.loads((output / "manifest.json").read_text())
    if manifest["sdk"] != data["sdk"] or manifest["version"] != data["compiler"]:
        raise ValueError("Dhall compiler or frontend SDK differs from the lock")
    cache = state / "cache/dhall"
    cache.mkdir(parents=True, exist_ok=True)
    for file in (Path(manifest["cache"]) / "dhall").iterdir():
        target = cache / file.name
        expected = file.resolve()
        if target.is_symlink() and target.resolve() == expected:
            continue
        if target.exists() or target.is_symlink():
            target.unlink()
        try:
            target.symlink_to(expected)
        except FileExistsError:
            if not target.is_symlink() or target.resolve() != expected:
                raise
    env = dict(
        environment(),
        XDG_CACHE_HOME=str(state / "cache"),
        XDG_DATA_HOME=str(state / "data"),
    )
    return manifest, env
