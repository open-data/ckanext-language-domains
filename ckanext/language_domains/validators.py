import json

from typing import Any


def load_json_string(value: Any):
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    return json.loads(value)