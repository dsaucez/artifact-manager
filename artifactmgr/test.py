import json
from datetime import timedelta, timezone
from logging import Logger
from typing import Union

from dateutil import parser
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel


class ApiUser(BaseModel):
    is_authenticated: bool = False


def normalize_date_to_utc(date_str: str) -> Union[None, str]:
    if len(date_str) > 0:
        try:
            date_parsed = parser.parse(str(date_str)) + timedelta(milliseconds=100)
            date_parsed = date_parsed - timedelta(milliseconds=100)
            date_parsed = date_parsed.astimezone(timezone.utc)
        except Exception as exc:
            Logger.warning(
                "artifact_tags: could not normalize %r to UTC; returning it unchanged",
                date_str,
            )
            return date_str
    else:
        return None
    return date_parsed


env = Environment(loader=FileSystemLoader("templates"))
env.filters["normalize_date_to_utc"] = normalize_date_to_utc


template = env.get_template("artifacts/artifact_list.html")
with open("artifacts.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Dummy
api_user = ApiUser()

# External environment
search = None

# Pagination
current_page_index = data["currentPageIndex"]
max_index = int(data["total"] / data["maxPerPage"])
first = current_page_index * data["maxPerPage"]
last = min(first + data["maxPerPage"], data["total"])
item_range = f"{first + 1}  - {last}"
prev_page = current_page_index if current_page_index > 0 else None
next_page = current_page_index + 2 if current_page_index < max_index else None

# Info for rendering
infos = {
    "message": "This is a test",
    "api_user": api_user,
    "artifacts": data,
    "debug": True,
    "item_range": item_range,
    "prev_page": prev_page,
    "next_page": next_page,
    "search": search,
}

html = template.render(infos)
with open("artifacts.html", "w", encoding="utf-8") as f:
    f.write(html)
