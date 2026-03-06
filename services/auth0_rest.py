"""Auth0 JWT validation for Flask-based REST services."""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

import jwt
from flask import Flask, Request, g, jsonify, request

_LOG = logging.getLogger(__name__)


def _truthy_env(name: str, default: bool = False) -> bool:
    raw = (os.environ.get(name, "") or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "y", "on"}


def _split_csv_or_space(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    values = [part.strip() for part in re.split(r"[,\s]+", raw) if part.strip()]
    return tuple(values)


def _normalize_auth0_domain(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    value = re.sub(r"^https?://", "", value, flags=re.IGNORECASE)
    return value.strip().strip("/")


@dataclass(frozen=True)
class AuthError(Exception):
    status_code: int
    code: str
    description: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "description": self.description}


class Auth0JWTValidator:
    """Validate Auth0-issued JWT access tokens against JWKS."""

    def __init__(
        self,
        *,
        domain: str,
        audience: str,
        algorithms: Sequence[str] = ("RS256",),
        required_scopes: Iterable[str] = (),
        jwks_client: object | None = None,
    ) -> None:
        normalized_domain = _normalize_auth0_domain(domain)
        if not normalized_domain:
            raise ValueError("AUTH0_DOMAIN is required when auth is enabled.")
        if not (audience or "").strip():
            raise ValueError("AUTH0_API_AUDIENCE is required when auth is enabled.")

        self.domain = normalized_domain
        self.audience = audience.strip()
        self.algorithms = tuple(algorithms) or ("RS256",)
        self.required_scopes = tuple(scope for scope in required_scopes if scope)
        self.issuer = f"https://{self.domain}/"
        self.jwks_url = f"{self.issuer}.well-known/jwks.json"
        self._jwks_client = jwks_client or jwt.PyJWKClient(self.jwks_url)

    @staticmethod
    def get_token_auth_header(req: Request) -> str:
        auth = req.headers.get("Authorization", None)
        if not auth:
            raise AuthError(
                status_code=401,
                code="authorization_header_missing",
                description="Authorization header is expected",
            )

        parts = auth.split()
        if parts[0].lower() != "bearer":
            raise AuthError(
                status_code=401,
                code="invalid_header",
                description="Authorization header must start with Bearer",
            )
        if len(parts) == 1:
            raise AuthError(status_code=401, code="invalid_header", description="Token not found")
        if len(parts) > 2:
            raise AuthError(
                status_code=401,
                code="invalid_header",
                description="Authorization header must be Bearer token",
            )
        return parts[1]

    def decode_token(self, token: str) -> Mapping[str, object]:
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=list(self.algorithms),
                audience=self.audience,
                issuer=self.issuer,
            )
            return payload
        except jwt.ExpiredSignatureError as ex:
            raise AuthError(status_code=401, code="token_expired", description="Token is expired") from ex
        except jwt.InvalidAudienceError as ex:
            raise AuthError(status_code=401, code="invalid_audience", description="Incorrect audience") from ex
        except jwt.InvalidIssuerError as ex:
            raise AuthError(status_code=401, code="invalid_issuer", description="Incorrect issuer") from ex
        except Exception as ex:
            raise AuthError(
                status_code=401,
                code="invalid_header",
                description="Unable to parse authentication token",
            ) from ex

    def _assert_scopes(self, payload: Mapping[str, object]) -> None:
        if not self.required_scopes:
            return
        scope_str = str(payload.get("scope", "") or "")
        granted = set(scope_str.split())
        missing = [scope for scope in self.required_scopes if scope not in granted]
        if missing:
            raise AuthError(
                status_code=403,
                code="insufficient_scope",
                description=f"Missing required scope(s): {' '.join(missing)}",
            )

    def validate_request(self, req: Request) -> Mapping[str, object]:
        token = self.get_token_auth_header(req)
        payload = self.decode_token(token)
        self._assert_scopes(payload)
        return payload


def install_auth0_bearer_auth(
    app: Flask,
    *,
    domain: str,
    audience: str,
    algorithms: Sequence[str] = ("RS256",),
    required_scopes: Iterable[str] = (),
    exempt_paths: Sequence[str] = (),
    exempt_prefixes: Sequence[str] = (),
) -> Auth0JWTValidator:
    validator = Auth0JWTValidator(
        domain=domain,
        audience=audience,
        algorithms=algorithms,
        required_scopes=required_scopes,
    )
    exact = set(exempt_paths)
    prefixes = tuple(exempt_prefixes)

    @app.errorhandler(AuthError)
    def _handle_auth_error(ex: AuthError):
        response = jsonify(ex.to_dict())
        response.status_code = ex.status_code
        return response

    @app.before_request
    def _check_auth():
        if request.method == "OPTIONS":
            return None
        path = request.path or "/"
        if path in exact:
            return None
        if prefixes and any(path.startswith(prefix) for prefix in prefixes):
            return None
        g.auth_payload = validator.validate_request(request)
        return None

    _LOG.info(
        "Auth0 REST auth enabled (issuer=%s audience=%s algorithms=%s)",
        validator.issuer,
        validator.audience,
        ",".join(validator.algorithms),
    )
    return validator


def maybe_enable_auth0_rest_auth(app: Flask) -> bool:
    """Enable Auth0 JWT auth for a Flask app when ANON_AUTH_ENABLED=1."""
    if not _truthy_env("ANON_AUTH_ENABLED", default=False):
        return False

    domain = os.environ.get("AUTH0_DOMAIN", "")
    audience = os.environ.get("AUTH0_API_AUDIENCE", "")
    algorithms = _split_csv_or_space(os.environ.get("ANON_AUTH_JWT_ALGORITHMS", "RS256"))
    required_scopes = _split_csv_or_space(os.environ.get("ANON_AUTH_REQUIRED_SCOPES", ""))

    exempt_paths = _split_csv_or_space(os.environ.get("ANON_AUTH_EXEMPT_PATHS", ""))
    exempt_prefixes = _split_csv_or_space(os.environ.get("ANON_AUTH_EXEMPT_PREFIXES", ""))

    install_auth0_bearer_auth(
        app,
        domain=domain,
        audience=audience,
        algorithms=algorithms or ("RS256",),
        required_scopes=required_scopes,
        exempt_paths=exempt_paths,
        exempt_prefixes=exempt_prefixes,
    )
    return True
