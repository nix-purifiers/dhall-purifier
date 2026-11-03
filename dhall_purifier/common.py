import hashlib
import json
import os
from pathlib import Path
import subprocess


def environment():
    return {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("DHALL_") and k not in ("XDG_CACHE_HOME", "XDG_DATA_HOME")
    }


def command(args, **kwargs):
    result = subprocess.run(args, text=True, capture_output=True, **kwargs)
    if result.returncode:
        raise ValueError(result.stdout + result.stderr)
    return result.stdout


def relative(path, root):
    path = Path(path).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Dhall project imports must stay inside the project tree")
    return str(path.relative_to(root))


def inspect(file, env, syntax=False):
    return json.loads(
        command(
            [
                os.environ["DHALL_PURIFIER_INSPECTOR"],
                *(["--syntax"] if syntax else []),
                str(file),
            ],
            env=env,
        )
    )


def syntax_tree(root, roots, env):
    pending = list(roots)
    result = {}
    while pending:
        name = pending.pop()
        if name in result:
            continue
        file = (root / name).resolve()
        name = relative(file, root)
        if not file.is_file():
            raise ValueError("Missing Dhall project source " + name)
        records = inspect(file, env, True)["imports"]
        result[name] = [
            json.loads(x)
            for x in sorted(set(json.dumps(r, sort_keys=True) for r in records))
        ]
        for record in records:
            if record["type"] == "environment":
                raise ValueError(
                    "Environment imports are unsupported in the initial Dhall integration"
                )
            if record["type"] == "remote" and record["headers"]:
                raise ValueError("Remote imports with custom headers are unsupported")
            if record["type"] == "local":
                target = Path(record["path"])
                if not target.is_absolute():
                    target = file.parent / target
                child = relative(target, root)
                if record["mode"] == "Code" and target.is_file():
                    pending.append(child)
    return dict(sorted(result.items()))


def inputs(root, names):
    result = {}
    for name in sorted(set(names)):
        file = root / name
        if (
            Path(name).is_absolute()
            or ".." in Path(name).parts
            or not file.is_file()
            or file.is_symlink()
        ):
            raise ValueError("Selection inputs must be regular project files")
        result[name] = {"sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
    return result


def load(root, companion):
    data = json.loads(companion.read_text())
    if data.get("version") != 1 or data.get("purifier") != "dhall":
        raise ValueError("Unsupported Dhall lock")
    if data["sdk"] != os.environ["DHALL_PURIFIER_SDK_VERSION"]:
        raise ValueError("Dhall frontend SDK changed; update the lock")
    if inputs(root, data["extraInputs"]) != data["inputs"]:
        raise ValueError("Selection inputs changed; update the lock")
    if syntax_tree(root, data["roots"], environment()) != data["project"]:
        raise ValueError("Dhall import declarations changed; update the lock")
    return data
