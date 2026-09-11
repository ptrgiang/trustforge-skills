import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert "required" in payload, "missing required field"
