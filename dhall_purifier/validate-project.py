import json
import os
from pathlib import Path
import sys

from common import environment, syntax_tree

inspector, root, expected = sys.argv[1:]
os.environ["DHALL_PURIFIER_INSPECTOR"] = inspector
lock = json.loads(Path(expected).read_text())
if syntax_tree(Path(root).resolve(), lock["roots"], environment()) != lock["project"]:
    raise SystemExit("Dhall import declarations changed; update the lock")
