"""Native freeze, local-source edits, remote code/text/bytes and tracked inputs."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

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


def call(root, *args, expected=0):
    result = subprocess.run(
        [str(cli / args[0]), *args[1:]], cwd=root, text=True, capture_output=True
    )
    assert result.returncode == expected, (args, result)
    return result


with tempfile.TemporaryDirectory(prefix="dhall-native-capture-") as temporary:
    root = Path(temporary)
    shutil.copytree(
        repo / "examples/minimal",
        root,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".dhall-purifier"),
    )
    companion = root / "dhall-purifier.lock.json"
    original = companion.read_bytes()
    call(root, "dhall-purifier", "lock")
    assert companion.read_bytes() == original
    (root / "number.dhall").write_text("20\n")
    (root / "package.dhall").write_text(
        (root / "package.dhall")
        .read_text()
        .replace("[ 20, 22 ]", "[ ./number.dhall, 22 ]")
    )
    (root / "selection.txt").write_text("Tracked selector\n")
    url = "https://raw.githubusercontent.com/dhall-lang/dhall-lang/v20.1.0/README.md"
    (root / "text.dhall").write_text(url + " as Text\n")
    (root / "bytes.dhall").write_text(url + " as Bytes\n")
    call(
        root,
        "dhall-purifier",
        "lock",
        "--update",
        "--file",
        "package.dhall",
        "--file",
        "text.dhall",
        "--file",
        "bytes.dhall",
        "--input",
        "selection.txt",
    )
    data = json.loads(companion.read_text())
    assert (
        data["extraInputs"] == ["selection.txt"] and "number.dhall" in data["project"]
    )
    assert {e["dhall"]["mode"] for e in data["entries"]} == {
        "Code",
        "RawText",
        "RawBytes",
    }
    assert all(e["dhall"]["hash"] in e["dhall"]["expression"] for e in data["entries"])
    call(root, "dhall-purifier", "prefetch")
    assert (
        json.loads(call(root, "dhall-to-json", "--file", "package.dhall").stdout)[
            "answer"
        ]
        == 42
    )
    assert "Dhall" in json.loads(
        call(root, "dhall-to-json", "--file", "text.dhall").stdout
    )
    assert '0x"' in call(root, "dhall", "--file", "bytes.dhall").stdout
    (root / "number.dhall").write_text("21\n")
    assert (
        json.loads(call(root, "dhall-to-json", "--file", "package.dhall").stdout)[
            "answer"
        ]
        == 43
    )
    call(root, "dhall-purifier", "lock")
    assert json.loads(companion.read_text()) == data
    (root / "number.dhall").write_text("20\n")
    assert (
        json.loads(call(root, "dhall-to-json", "--file", "package.dhall").stdout)[
            "answer"
        ]
        == 42
    )
    (root / "selection.txt").write_text("Changed selector\n")
    assert (
        "Selection inputs changed"
        in call(root, "dhall-purifier", "prefetch", expected=1).stderr
    )
    (root / "selection.txt").write_text("Tracked selector\n")
    (root / "number.dhall").write_text("env:SHOULD_NOT_BE_IMPORTED\n")
    assert (
        "Environment imports"
        in call(root, "dhall-purifier", "prefetch", expected=1).stderr
    )
    (root / "number.dhall").write_text("20\n")
    data["entries"][0]["dhall"]["hash"] = "0" * 64
    data["entries"][0]["path"] = "cache/1220" + "0" * 64
    companion.write_text(json.dumps(data))
    failed = call(root, "dhall-purifier", "prefetch", expected=1)
    assert "dependency failed" in failed.stderr or "exit code" in failed.stderr, failed
print("Native Dhall freeze, local edits, raw imports and selection binding passed")
