"""Google ID-token signature and claim verification for the **isolated** URANO beta.

This module only verifies identity. No public OAuth routes, session issuance,
credentials, or deployment are enabled here. The caller must obtain the JWKS
from Google's trusted endpoint over HTTPS and supply a fresh, one-time nonce
bound to an authorization-code+PKCE flow. Never trust a JWKS from a browser.
"""
from __future__ import annotations

import base64
import binascii
import hmac
import json
import time
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

_GOOGLE_ISSUERS = frozenset(("https://accounts.google.com", "accounts.google.com"))
_MAX_TOKEN_BYTES = 16000
_SKEW_SECONDS = 60


class GoogleIdentityDenied(ValueError):
    """Unverified, malformed, expired or wrong-client Google identity."""


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str


def _no_duplicate_keys(items):
    result = {}
    for key, value in items:
        if key in result:
            raise GoogleIdentityDenied("Duplicate JSON claim or header")
        result[key] = value
    return result


def _json_object(data: bytes) -> dict:
    try:
        result = json.loads(data.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeError, json.JSONDecodeError, TypeError) as exc:
        raise GoogleIdentityDenied("Invalid JWT JSON") from exc
    if not isinstance(result, dict):
        raise GoogleIdentityDenied("JWT must contain JSON objects")
    return result


def _b64url(value: str) -> bytes:
    if not isinstance(value, str) or not value or len(value) > _MAX_TOKEN_BYTES:
        raise GoogleIdentityDenied("Invalid JWT encoding")
    if any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for char in value):
        raise GoogleIdentityDenied("Invalid JWT alphabet")
    try:
        return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except (ValueError, binascii.Error) as exc:
        raise GoogleIdentityDenied("Invalid JWT encoding") from exc


def _rsa_key(jwk: dict):
    if (not isinstance(jwk, dict) or jwk.get("kty") != "RSA"
            or jwk.get("use", "sig") != "sig"
            or jwk.get("alg", "RS256") != "RS256"):
        raise GoogleIdentityDenied("Invalid Google signing key")
    modulus, exponent = _b64url(jwk.get("n")), _b64url(jwk.get("e"))
    if not 256 <= len(modulus) <= 1024 or len(exponent) > 8:
        raise GoogleIdentityDenied("Invalid RSA key size")
    numbers = rsa.RSAPublicNumbers(int.from_bytes(exponent, "big"), int.from_bytes(modulus, "big"))
    try:
        key = numbers.public_key()
    except ValueError as exc:
        raise GoogleIdentityDenied("Invalid RSA public key") from exc
    if key.key_size < 2048:
        raise GoogleIdentityDenied("RSA key too small")
    return key


def verify_google_id_token(token: str, *, client_id: str, expected_nonce: str,
                           jwks: dict, now: int | None = None) -> GoogleIdentity:
    """Verify a Google RS256 ID token against externally trusted Google JWKS.

    `expected_nonce` MUST be random, unguessable, server-bound, and consumed once
    by the higher-level OAuth callback; this routine does not manage pending
    authorization attempts or the PKCE exchange.
    """
    if (not isinstance(token, str) or len(token) > _MAX_TOKEN_BYTES
            or not isinstance(client_id, str) or not client_id
            or not isinstance(expected_nonce, str) or len(expected_nonce) < 16):
        raise GoogleIdentityDenied("Missing or invalid verification context")
    parts = token.split(".")
    if len(parts) != 3:
        raise GoogleIdentityDenied("Malformed ID token")
    header = _json_object(_b64url(parts[0]))
    claims = _json_object(_b64url(parts[1]))
    if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
        raise GoogleIdentityDenied("Unexpected ID token signature algorithm")
    kid = header["kid"]
    if not kid or len(kid) > 256 or not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
        raise GoogleIdentityDenied("Invalid key set")
    keys = [item for item in jwks["keys"] if isinstance(item, dict) and item.get("kid") == kid]
    if len(keys) != 1:
        raise GoogleIdentityDenied("Signing key not found or ambiguous")
    key = _rsa_key(keys[0])
    try:
        key.verify(_b64url(parts[2]), (parts[0] + "." + parts[1]).encode("ascii"),
                   padding.PKCS1v15(), hashes.SHA256())
    except (InvalidSignature, ValueError) as exc:
        raise GoogleIdentityDenied("Invalid token signature") from exc

    audience = claims.get("aud")
    if isinstance(audience, str):
        matches = audience == client_id
    elif isinstance(audience, list) and audience and all(isinstance(x, str) for x in audience):
        matches = client_id in audience and claims.get("azp") == client_id
    else:
        matches = False
    if (claims.get("iss") not in _GOOGLE_ISSUERS or not matches
            or ("azp" in claims and claims["azp"] != client_id)):
        raise GoogleIdentityDenied("Unexpected token issuer or audience")
    current = int(time.time()) if now is None else now
    exp, iat = claims.get("exp"), claims.get("iat")
    if (type(exp) is not int or type(iat) is not int
            or exp <= current - _SKEW_SECONDS or iat > current + _SKEW_SECONDS
            or exp <= iat):
        raise GoogleIdentityDenied("Invalid token lifetime")
    if (not isinstance(claims.get("nonce"), str)
            or not hmac.compare_digest(claims["nonce"], expected_nonce)):
        raise GoogleIdentityDenied("Invalid login nonce")
    sub, email = claims.get("sub"), claims.get("email")
    if (not isinstance(sub, str) or not 1 <= len(sub) <= 255
            or not sub.isascii() or not isinstance(email, str)
            or not 3 <= len(email) <= 254 or claims.get("email_verified") is not True):
        raise GoogleIdentityDenied("Unverified Google account identity")
    return GoogleIdentity(sub=sub, email=email.lower())
