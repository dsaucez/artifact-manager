import datetime
import json

# from datetime import timedelta, timezone
from logging import Logger
from typing import Union

import httpx
import humanize
from dateutil import parser
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel


class ApiUser(BaseModel):
    is_authenticated: bool = False


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
            # date_parsed = parser.parse(str(date_str)) + timedelta(milliseconds=100)
            # date_parsed = date_parsed - timedelta(milliseconds=100)
            # date_parsed = date_parsed.astimezone(timezone.utc)
        except Exception as exc:
            Logger.warning(
                "artifact_tags: could not normalize %r to UTC; returning it unchanged",
                date_str,
            )
            return date_str
    else:
        return None
    return date_parsed


def humanize_bytes(size: int):
    return humanize.naturalsize(size, binary=True)


app = FastAPI(version="v0.0.1")
app.mount("/static", StaticFiles(directory="server/static"), name="static")

env = Environment(loader=FileSystemLoader("templates"))
env.filters["normalize_date_to_utc"] = normalize_date_to_utc
env.filters["humanize_bytes"] = humanize_bytes
env.filters["json_pretty"] = json_pretty


# Dummy
api_user = ApiUser()


## == Artifact list ============================================================
async def search_objects(search=None, page_index: int = 0, page_size: int = 20) -> dict:
    params = {
        "paginate": True,
        "pageIndex": page_index,
        "pageSize": page_size,
    }

    if search:
        params["nameQuery"] = search

    url_params = "&".join([f"{k}={v}" for k, v in params.items()])

    url = f"https://mrs-backend.slices-staging.slices-be.eu/v0.2/digital-objects/search/datasets?{url_params}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


@app.get("/artifacts/", response_class=HTMLResponse)
async def list_artifacts(
    search: str | None = None, page_index: int = 0, debug: bool = False
):

    template = env.get_template("artifacts/artifact_list.html")

    data = await search_objects(search=search, page_index=page_index)

    # Pagination
    current_page_index = data["currentPageIndex"]
    max_index = int(data["total"] / data["maxPerPage"])
    first = current_page_index * data["maxPerPage"]
    last = min(first + data["maxPerPage"], data["total"])
    item_range = f"{first + 1}  &mdash; {last}"
    prev_page = current_page_index if current_page_index > 0 else None
    next_page = current_page_index + 2 if current_page_index < max_index else None

    # Info for rendering
    infos = {
        "app_version": app.version,
        "now": datetime.datetime.now(),
        "message": "This is a test",
        "api_user": api_user,
        "artifacts": data,
        "debug": debug,
        "item_range": item_range,
        "prev_page": prev_page,
        "next_page": next_page,
        "search": search,
    }

    html_content = template.render(infos)
    return html_content


## == Artifact detail ==========================================================
async def get_digital_object(internal_id) -> dict:
    url = f"https://mrs-backend.slices-staging.slices-be.eu/v0.2/digital-objects/{internal_id}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


@app.get("/artifacts/{internal_id}", response_class=HTMLResponse)
async def get_artifact(internal_id: int, debug: bool = False):
    template = env.get_template("artifacts/artifact_detail.html")

    data = await get_digital_object(internal_id=internal_id)

    infos = {
        "app_version": app.version,
        "now": datetime.datetime.now(),
        "message": "This is a test detail",
        "api_user": api_user,
        "artifact": data,
        "show_authors": True,
        "debug": debug,
        "visibility": "public",  # public, author, project,
        "artifact": data,
    }

    html_content = template.render(infos)

    return html_content
