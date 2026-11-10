import datetime
import json
from logging import getLogger
from typing import Union

import humanize


def now() -> str:
    """Return the current UTC time in ISO 8601 format with microseconds."""
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )


def json_pretty(value) -> str:
    """Serialize a value to indented JSON for debug display."""
    try:
        if hasattr(value, "as_dict"):
            value = value.as_dict()
        elif hasattr(value, "__iter__") and not isinstance(value, (str, dict)):
            value = list(value)
        return json.dumps(value, indent=2, default=str)
    except (TypeError, ValueError):
        return str(value)


def normalize_date_to_utc(date_str: str) -> Union[None, str]:
    if len(date_str) > 0:
        try:
            dt = datetime.datetime.fromisoformat(date_str)
            date_parsed = dt.strftime("%b. %-d, %Y %-I:%M%p (%Z)")
        except Exception:
            getLogger(__name__).warning(
                "artifact_tags: could not normalize %r to UTC; returning it unchanged",
                date_str,
            )
            return date_str
    else:
        return None
    return date_parsed


def humanize_bytes(size: int):
    return humanize.naturalsize(size, binary=True)
