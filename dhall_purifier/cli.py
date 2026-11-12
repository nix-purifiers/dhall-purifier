import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from .capture import capture
from .common import load
from .runtime import prepare


def locate(project=None, companion=None):
    root = Path(
        project or os.environ.get("DHALL_PURIFIER_PROJECT", Path.cwd())
    ).resolve()
    external = companion or os.environ.get("DHALL_PURIFIER_LOCK")
    if external:
        return root, Path(external).resolve()
    if project or os.environ.get("DHALL_PURIFIER_PROJECT"):
        return root, root / "dhall-purifier.lock.json"
    for directory in [root, *root.parents]:
        if (directory / "dhall-purifier.lock.json").exists():
            return directory, directory / "dhall-purifier.lock.json"
    return root, root / "dhall-purifier.lock.json"


def main():
    args = sys.argv[1:]
    if args and args[0].startswith("--native="):
        name = args[0].split("=", 1)[1]
        root, companion = locate()
        if not companion.exists():
            programs = json.loads(
                Path(os.environ["DHALL_PURIFIER_PROGRAMS"]).read_text()
            )
            executable = programs[name]
            print(
                "dhall-purifier: no lockfile; using ordinary impure " + name,
                file=sys.stderr,
            )
            os.execv(executable, [executable, *args[1:]])
        manifest, env = prepare(root, companion)
        executable = manifest["programs"][name]
        os.execve(executable, [executable, *args[1:]], env)
    parser = argparse.ArgumentParser(description="Lock native Dhall imports")
    parser.add_argument(
        "action", choices=["lock", "prefetch", "exec", "bundle", "publish"]
    )
    parser.add_argument("--project", type=Path)
    parser.add_argument("--lock", type=Path)
    parser.add_argument("--file", action="append", default=[])
    parser.add_argument("--input", action="append", default=[])
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--tag")
    opts, remaining = parser.parse_known_args(args)
    root, companion = locate(opts.project, opts.lock)
    if opts.action == "lock":
        if remaining:
            parser.error("Unexpected arguments: " + " ".join(remaining))
        capture(root, companion, opts.file, opts.input, opts.update)
    elif opts.action in ("prefetch", "exec"):
        manifest, env = prepare(root, companion)
        if opts.action == "exec":
            if remaining and remaining[0] == "--":
                remaining = remaining[1:]
            if not remaining:
                parser.error("exec requires a command")
            env.update(
                DHALL_PURIFIER_PROJECT=str(root), DHALL_PURIFIER_LOCK=str(companion)
            )
            env["PATH"] = (
                str(Path(os.environ["DHALL_PURIFIER_SDK"]) / "bin")
                + os.pathsep
                + env["PATH"]
            )
            os.execvpe(remaining[0], remaining, env)
    else:
        load(root, companion)
        expression = (
            "import "
            + json.dumps(
                os.environ["DHALL_PURIFIER_SDK"] + "/lib/dhall-purifier/pkgs/build-dhall-project/release.nix"
            )
            + " {root="
            + json.dumps(str(root))
            + ";lockFile="
            + json.dumps(str(companion))
            + ";}"
        )
        result = subprocess.run(
            [
                "nix",
                "build",
                "--impure",
                "--expr",
                expression,
                "--no-link",
                "--print-out-paths",
            ],
            text=True,
            capture_output=True,
        )
        if result.returncode:
            raise ValueError(result.stdout + result.stderr)
        artifact = Path(result.stdout.strip()) / "dhall-package.tar.gz"
        if opts.action == "bundle":
            print(artifact)
        else:
            if not opts.tag:
                parser.error("publish requires --tag")
            subprocess.run(
                [
                    os.environ.get("DHALL_PURIFIER_GH", "gh"),
                    "release",
                    "upload",
                    opts.tag,
                    str(artifact),
                    str(artifact.parent / "source.dhall"),
                    "--clobber",
                ],
                cwd=root,
                check=True,
            )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print("dhall-purifier: " + str(error), file=sys.stderr)
        raise SystemExit(1)
