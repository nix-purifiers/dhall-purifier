import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from .common import command, environment, inputs, inspect, load, relative, syntax_tree


def capture(root, companion, roots=(), extra=(), update=False):
    if companion.exists() and not update:
        load(root, companion)
        return
    previous = json.loads(companion.read_text()) if companion.exists() else {}
    roots = [
        relative(root / name, root)
        for name in (roots or previous.get("roots", ["package.dhall"]))
    ]
    extra = list(extra or previous.get("extraInputs", []))
    with tempfile.TemporaryDirectory(prefix="dhall-capture-") as temporary:
        state = Path(temporary)
        env = dict(
            environment(),
            XDG_CACHE_HOME=str(state / "cache"),
            XDG_DATA_HOME=str(state / "data"),
        )
        syntax_tree(root, roots, env)
        command(
            [
                os.environ["DHALL_PURIFIER_ORIGINAL_DHALL"],
                "freeze",
                "--transitive",
                *[str(root / f) for f in roots],
            ],
            cwd=root,
            env=env,
        )
        project = syntax_tree(root, roots, env)
        # Native resolver validates the selected import graph and integrity checks.
        for file in roots:
            inspect(root / file, env)
        entries = {}
        for records in project.values():
            for record in records:
                if record["type"] != "remote" or record["mode"] == "Location":
                    continue
                digest = record["hash"]
                if not isinstance(digest, str) or not re.fullmatch(
                    "[a-f0-9]{64}", digest
                ):
                    raise ValueError("Freeze remote Dhall imports before capture")
                source = command(
                    [os.environ["DHALL_PURIFIER_ORIGINAL_DHALL"], "--alpha", "--plain"],
                    input=record["expression"],
                    cwd=root,
                    env=env,
                )
                binary = subprocess.run(
                    [os.environ["DHALL_PURIFIER_ORIGINAL_DHALL"], "encode"],
                    input=source.encode(),
                    capture_output=True,
                    env=env,
                    check=True,
                ).stdout
                sri = (
                    "sha256-"
                    + base64.b64encode(hashlib.sha256(binary).digest()).decode()
                )
                entry = {
                    "path": "cache/1220" + digest,
                    "url": record["url"],
                    "mirrors": [],
                    "hash": sri,
                    "dhall": {
                        "hash": digest,
                        "mode": record["mode"],
                        "expression": record["expression"],
                    },
                }
                if digest in entries and entries[digest]["hash"] != sri:
                    raise ValueError(
                        "Native normalized imports disagree on their semantic cache contents"
                    )
                entries.setdefault(digest, entry)
        data = {
            "version": 1,
            "purifier": "dhall",
            "sdk": os.environ["DHALL_PURIFIER_SDK_VERSION"],
            "compiler": os.environ["DHALL_PURIFIER_COMPILER_VERSION"],
            "roots": roots,
            "project": project,
            "extraInputs": extra,
            "inputs": inputs(root, extra),
            "entries": [entries[k] for k in sorted(entries)],
        }
        companion.parent.mkdir(parents=True, exist_ok=True)
        target = companion.with_name(companion.name + ".tmp")
        target.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
        target.replace(companion)
