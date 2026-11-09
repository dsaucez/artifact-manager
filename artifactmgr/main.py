import datetime
import json
from logging import Logger
from typing import Annotated, Union
from uuid import uuid4

import httpx
import humanize
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, EmailStr, Field, constr


class ApiUser(BaseModel):
    is_authenticated: bool = False
    can_create_artifact: bool = True
    firstName: str
    lastName: str
    email: EmailStr
    orcId: str | None = None
    organization: str | None = None


class ArtifactCreateRequest(BaseModel):
    name: constr(strip_whitespace=True, min_length=1)
    description: constr(strip_whitespace=True, min_length=1)
    keywords: list[str] = Field(default_factory=list)
    scientificDomains: list[str] = Field(default_factory=list)
    scientificSubdomains: list[str] = Field(default_factory=list)


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


@app.get("/")
async def root():
    return RedirectResponse(url="/artifacts", status_code=307)


env = Environment(loader=FileSystemLoader("templates"))
env.filters["normalize_date_to_utc"] = normalize_date_to_utc
env.filters["humanize_bytes"] = humanize_bytes
env.filters["json_pretty"] = json_pretty


# Dummy
api_user = ApiUser(
    firstName="Damien",
    lastName="SAUCEZ",
    email="Damien.Saucez@inria.fr",
    orcId=None,
    organization="Inria",
)


## == Artifact list ============================================================
async def search_objects(search=None, page_index: int = 0, page_size: int = 20) -> dict:
    params = {
        "paginate": True,
        "pageIndex": page_index,
        "pageSize": page_size,
        "advancedQuery": 'Keywords ^$ "post5g-blueprint-artifact"',
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
        # "message": "This is a test",
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
        # "message": "This is a test detail",
        "api_user": api_user,
        "show_authors": True,
        "debug": debug,
        "visibility": "public",  # public, author, project,
        "artifact": data,
    }

    html_content = template.render(infos)

    return html_content


@app.get("/artifacts/create/", response_class=HTMLResponse)
async def create_artifact(debug: bool = False):
    template = env.get_template("artifacts/artifact_create.html")

    infos = {
        "app_version": app.version,
        "now": datetime.datetime.now(),
        # "message": "This is a test create",
        "api_user": api_user,
        "show_authors": True,
        "debug": debug,
        "visibility": "public",  # public, author, project,
    }

    html_content = template.render(infos)

    return html_content


@app.post("/artifacts/create/")
async def submit_artifact(
    name: Annotated[str, Form()],
    description: Annotated[str, Form()],
    keywords: Annotated[list[str], Form()] = [],
    scientificDomains: Annotated[list[str], Form()] = [],
    scientificSubdomains: Annotated[list[str], Form()] = [],
    file: UploadFile | None = File(default=None),
):
    form_data = ArtifactCreateRequest(
        name=name,
        description=description,
        keywords=keywords,
        scientificDomains=scientificDomains,
        scientificSubdomains=scientificSubdomains,
    )
    artifact: dict[str, object] = {
        "name": form_data.name,
        "description": form_data.description,
    }

    for field in ("keywords", "scientificDomains", "scientificSubdomains"):
        artifact[field] = [
            value.strip() for value in getattr(form_data, field) if value.strip()
        ]

    artifact["file"] = (
        {
            "filename": file.filename,
            "content_type": file.content_type,
            "size": file.size,
        }
        if isinstance(file, UploadFile) and file.filename
        else None
    )

    print(file)
    body = json.loads("""
    {"$type": "Dataset", "identifier": "test-url-edit", "systemCreationDate": null, "internalIdentifier": null, "alternateIdentifier": null, "downloadUrl": null, "creators": [{"email": "Damien.Saucez@inria.fr", "firstName": "Damien", "lastName": "SAUCEZ", "orcId": null, "organization": "INRIA;INRIA", "phone": null, "position": null, "website": null}], "name": "", "description": "", "resourceType": "Dataset", "subjects": [], "keywords": [], "createdAt": "2026-11-09T12:49:15.719774Z", "version": "1.0", "metadataProfile": null, "contributors": [], "accessType": "Remote", "accessMode": "Free", "requiredObjects": [], "relatedObjects": [], "primaryLanguages": [], "otherLanguages": [], "contact": null, "publicContact": null, "rights": "", "rightsUri": null, "accessRights": "", "license": "BSD-3-Clause", "licenseUri": null, "copyrightsHolder": "Damien SAUCEZ", "confidentialityDeclaration": null, "specialPermissions": null, "restrictions": null, "citationRequirements": null, "conditions": null, "disclaimer": null, "provenance": null, "createdBy": null, "numberOfVisits": 0, "numberOfDownloads": 0, "paymentModel": null, "pricing": null, "scientificDomains": ["networks"], "scientificSubdomains": ["network protocols"], "address": null, "dateTimeStart": "2026-11-09T12:49:15.719774Z", "dateTimeEnd": "2026-11-09T12:49:15.719774Z", "locations": [], "byteSize": 0, "duration": null, "format": "", "medium": "", "compressionFormat": null, "fileMetadata": "", "dataStandard": null, "encodingFormat": null, "statistics": null}
    """)

    body["creators"] = [
        {
            "email": api_user.email,
            "firstName": api_user.firstName,
            "lastName": api_user.lastName,
            "orcId": api_user.orcId,
            "organization": api_user.organization,
        }
    ]
    body["identifier"] = uuid4()
    body["name"] = artifact["name"]
    body["description"] = artifact["description"]
    body["keywords"] = artifact["keywords"]
    body["scientificDomains"] = artifact["scientificDomains"]
    body["scientificSubdomains"] = artifact["scientificSubdomains"]

    body["keywords"].append("post5g-blueprint-artifact")

    if file:
        body["byteSize"] = file.size
        body["format"] = file.content_type

    return body
