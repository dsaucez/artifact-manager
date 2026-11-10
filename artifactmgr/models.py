from pydantic import BaseModel, EmailStr, Field, constr


class ApiUser(BaseModel):
    is_authenticated: bool = False
    can_create_artifact: bool = True
    firstName: str
    lastName: str
    email: EmailStr
    orcId: str | None = None
    organization: str | None = None
    token: str | None = None


class ArtifactCreateRequest(BaseModel):
    name: constr(strip_whitespace=True, min_length=1)
    description: constr(strip_whitespace=True, min_length=1)
    keywords: list[str] = Field(default_factory=list)
    scientificDomains: list[str] = Field(default_factory=list)
    scientificSubdomains: list[str] = Field(default_factory=list)
