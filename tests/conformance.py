"""Native Dhall, JSON, LSP, mutable sources and native distribution consumers."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

import editor

repo = Path(__file__).resolve().parent.parent
cli = (
    Path(
        subprocess.check_output(
            ["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"],
            text=True,
        ).strip()
    )
    / "bin"
)


def call(root, *args, env=None, expected=0, input=None):
    result = subprocess.run(
        [str(cli / args[0]), *args[1:]],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        input=input,
    )
    assert result.returncode == expected, (args, result)
    return result


with tempfile.TemporaryDirectory(prefix="dhall proof with spaces ") as temporary:
    temp = Path(temporary)
    root = temp / "project"
    shutil.copytree(
        repo / "examples/minimal",
        root,
        ignore=shutil.ignore_patterns(".dhall-purifier"),
    )
    poison = temp / "poison"
    poison.mkdir()
    env = dict(os.environ, XDG_CACHE_HOME=str(poison), XDG_DATA_HOME=str(poison))
    assert (
        json.loads(
            call(root, "dhall-to-json", "--file", "package.dhall", env=env).stdout
        )["answer"]
        == 42
    )
    profiles = list((root / ".dhall-purifier").glob("*/environment-profile"))
    assert profiles
    profile = json.loads(profiles[0].resolve().read_text())
    manifest = json.loads((Path(profile["output"]) / "manifest.json").read_text())
    package = Path(next(iter(manifest["packages"].values())))
    cachefile = next((root / ".dhall-purifier").glob("*/cache/dhall/1220*"))
    assert cachefile.is_symlink() and str(cachefile.resolve()).startswith("/nix/store/")
    assert (package / "source.dhall").is_file() and (package / "binary.dhall").is_file()
    expression = root / "package.dhall"
    original = expression.read_text()
    for source, answer in [(original.replace("20, 22", "20, 23"), 43), (original, 42)]:
        expression.write_text(source)
        assert (
            json.loads(
                call(root, "dhall-to-json", "--file", "package.dhall", env=env).stdout
            )["answer"]
            == answer
        )
    editor.check(cli, root, env)
    # A warmed ambient cache must not authorize another HTTP import.
    unknown = "https://raw.githubusercontent.com/dhall-lang/dhall-lang/v20.1.0/Prelude/Natural/show"
    original_dhall = subprocess.check_output(
        [
            "nix",
            "eval",
            "--impure",
            "--raw",
            "--expr",
            "let f=builtins.getFlake "
            + json.dumps(str(repo))
            + ";p=import f.inputs.nixpkgs {};in p.lib.getExe p.dhall",
        ],
        text=True,
    ).strip()
    warmed = subprocess.run(
        [original_dhall, "freeze"],
        input=unknown + "\n",
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert list((poison / "dhall").glob("1220*"))
    result = call(root, "dhall", input=warmed.stdout, expected=1, env=env)
    assert "HTTP" in result.stderr, result
    expression.write_text(original.replace("/Natural/sum", "/Natural/show"))
    stale = call(root, "dhall-to-json", "--file", "package.dhall", expected=1)
    assert "import declarations changed" in stale.stderr, stale
    expression.write_text(original)
    subdir = root / "subdir"
    subdir.mkdir()
    assert (
        json.loads(call(subdir, "dhall-to-json", "--file", str(expression)).stdout)[
            "answer"
        ]
        == 42
    )
    companion = temp / "external.json"
    (root / "dhall-purifier.lock.json").rename(companion)
    external = dict(
        env, DHALL_PURIFIER_PROJECT=str(root), DHALL_PURIFIER_LOCK=str(companion)
    )
    assert (
        json.loads(
            call(
                subdir, "dhall-to-json", "--file", str(expression), env=external
            ).stdout
        )["answer"]
        == 42
    )
    refs = subprocess.check_output(
        ["nix-store", "--query", "--requisites", str(profiles[0].resolve())], text=True
    )
    assert str(cli.parent) in refs and str(package) in refs
    archive = Path(
        call(root, "dhall-purifier", "bundle", "--lock", str(companion)).stdout.strip()
    )
    ordinary = temp / "ordinary"
    ordinary.mkdir()
    with tarfile.open(archive) as tar:
        tar.extractall(ordinary, filter="data")
    assert (
        json.loads(call(ordinary, "dhall-to-json", "--file", "source.dhall").stdout)[
            "answer"
        ]
        == 42
    )
    native_cache = dict(os.environ, XDG_CACHE_HOME=str(ordinary / ".cache"))
    binary = call(ordinary, "dhall-to-json", "--file", "binary.dhall", env=native_cache)
    assert (
        json.loads(binary.stdout)["answer"] == 42 and "ordinary impure" in binary.stderr
    )
    fake = temp / "fake-gh"
    fake.write_text(
        "#!/usr/bin/env python3\nimport pathlib,sys,shutil\nassert sys.argv[1:4]==['release','upload','v0.1.0']\nfor f in sys.argv[4:-1]:shutil.copyfile(f,pathlib.Path(__file__).parent/('uploaded-'+pathlib.Path(f).name))\n"
    )
    fake.chmod(0o755)
    call(
        root,
        "dhall-purifier",
        "publish",
        "--lock",
        str(companion),
        "--tag",
        "v0.1.0",
        env=dict(os.environ, DHALL_PURIFIER_GH=str(fake)),
    )
    assert (temp / "uploaded-dhall-package.tar.gz").read_bytes() == archive.read_bytes()
    assert (temp / "uploaded-source.dhall").read_bytes() == (
        archive.parent / "source.dhall"
    ).read_bytes()
    fallback = temp / "fallback"
    fallback.mkdir()
    version = call(fallback, "dhall", "--version")
    assert "ordinary impure" in version.stderr and "1.42.3" in version.stdout
    fake_tool = temp / "fake-tool"
    fake_tool.write_text(
        "#!/bin/sh\nprintf native-out\nprintf native-err >&2\nexit 7\n"
    )
    fake_tool.chmod(0o755)
    programs = temp / "programs.json"
    programs.write_text(json.dumps({"dhall": str(fake_tool)}))
    e = dict(
        os.environ,
        PYTHONPATH=str(cli.parent / "lib/dhall-purifier"),
        DHALL_PURIFIER_PROGRAMS=str(programs),
    )
    result = subprocess.run(
        ["python3", "-m", "dhall_purifier.cli", "--native=dhall"],
        cwd=fallback,
        env=e,
        text=True,
        capture_output=True,
    )
    assert (
        result.returncode == 7
        and result.stdout == "native-out"
        and result.stderr.endswith("native-err")
    ), result
print(
    "Native Dhall/JSON/LSP, edits, cache isolation, native package consumers and publication passed"
)
