import httpx
import jwt
from fastapi import HTTPException
from models import ApiUser
from settings import settings


async def decode_optional_token(token: str | None) -> ApiUser | None:
    if token is None:
        return None

    if not token.strip():
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        unverified_claims = jwt.decode(token, options={"verify_signature": False})
        issuer = unverified_claims.get("iss")
    except (jwt.PyJWTError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    if issuer not in settings.allowed_issuers:
        raise HTTPException(
            status_code=401,
            detail="Invalid token issuer",
        )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            link = f"{issuer.rstrip('/')}/.well-known/openid-configuration"
            discovery_response = await client.get(link)
            discovery_response.raise_for_status()
            discovery = discovery_response.json()
            if not isinstance(discovery, dict) or discovery.get("issuer") != issuer:
                raise ValueError(
                    "OIDC discovery document issuer does not match configuration"
                )

            jwks_uri = discovery.get("jwks_uri")
            if not isinstance(jwks_uri, str) or not jwks_uri.startswith("https://"):
                raise ValueError("OIDC discovery document has no valid JWKS URI")

            jwks_response = await client.get(jwks_uri)
            jwks_response.raise_for_status()
            jwks = jwks_response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Token verification is temporarily unavailable",
        ) from exc

    signing_keys = jwks.get("keys") if isinstance(jwks, dict) else None
    if not isinstance(signing_keys, list) or not signing_keys:
        raise HTTPException(
            status_code=503,
            detail="Token verification is temporarily unavailable",
        )

    try:
        header = jwt.get_unverified_header(token)
        key_id = header.get("kid")
        matching_keys = [
            key
            for key in signing_keys
            if isinstance(key, dict)
            and key.get("kid") == key_id
            and key.get("use", "sig") == "sig"
            and key.get("alg") == header.get("alg")
        ]
        if len(matching_keys) != 1:
            raise jwt.InvalidTokenError("No matching signing key")
    except (jwt.PyJWTError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    try:
        signing_key = jwt.PyJWK(matching_keys[0]).key
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Token verification is temporarily unavailable",
        ) from exc

    try:
        algos = [item["alg"] for item in matching_keys]
        decoded_token = jwt.decode(
            token,
            key=signing_key,
            algorithms=algos,
            issuer=issuer,
            options={"verify_aud": False},
        )

        return ApiUser(
            firstName=decoded_token.get("given_name"),
            lastName=decoded_token.get("family_name"),
            email=decoded_token.get("email"),
            is_authenticated=True,
            can_create_artifact=True,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc
