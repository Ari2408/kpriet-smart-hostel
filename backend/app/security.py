import os
import json
import base64
import hmac
import hashlib
import time
import bcrypt
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from .database import get_db

# Load local .env if available
load_dotenv()

# Production JWT Security Enforcement
INSECURE_DEFAULT_SECRET = "kpriet-smart-hostel-jwt-secret-key-2026-production"
KNOWN_PLACEHOLDERS = {
    INSECURE_DEFAULT_SECRET,
    "change-this-to-a-secure-random-32-byte-hex-key-in-production",
    "secret",
    "password",
    "123456",
}

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
_raw_jwt_secret = os.getenv("JWT_SECRET_KEY", "").strip()

if ENVIRONMENT in ("production", "prod"):
    if not _raw_jwt_secret or _raw_jwt_secret in KNOWN_PLACEHOLDERS or len(_raw_jwt_secret) < 32:
        raise RuntimeError(
            "CRITICAL SECURITY CONFIGURATION ERROR: Application started in PRODUCTION mode (ENVIRONMENT='production'), "
            "but JWT_SECRET_KEY is either missing, insecure, or shorter than 32 characters! "
            "For institutional data integrity, set a unique high-entropy 32+ byte cryptographic secret "
            "(e.g. `openssl rand -hex 32`) in Render environment variables before launching."
        )
    SECRET_KEY = _raw_jwt_secret
else:
    # Safe fallback for local offline development & testing
    SECRET_KEY = _raw_jwt_secret if _raw_jwt_secret else INSECURE_DEFAULT_SECRET

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 60 * 60 * 24 * 7 # 7 days

security_bearer = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

def _b64decode(data_str: str) -> bytes:
    padding = "=" * ((4 - len(data_str) % 4) % 4)
    return base64.urlsafe_b64decode(data_str + padding)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[int] = None) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = data.copy()
    exp = int(time.time()) + (expires_delta or ACCESS_TOKEN_EXPIRE_SECONDS)
    payload["exp"] = exp
    payload["iat"] = int(time.time())

    encoded_header = _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")

    signature = hmac.new(SECRET_KEY.encode("utf-8"), signature_input, hashlib.sha256).digest()
    encoded_signature = _b64encode(signature)

    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"

def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format")
        
        encoded_header, encoded_payload, encoded_signature = parts
        signature_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
        expected_sig = _b64encode(hmac.new(SECRET_KEY.encode("utf-8"), signature_input, hashlib.sha256).digest())

        if not hmac.compare_digest(encoded_signature, expected_sig):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Signature verification failed")

        payload = json.loads(_b64decode(encoded_payload).decode("utf-8"))
        if payload.get("exp", 0) < time.time():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")

        return payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Token error: {str(e)}")

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication credentials required")
    
    payload = decode_access_token(credentials.credentials)
    return payload

def require_staff(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    role = current_user.get("role")
    if role not in ["staff", "admin", "warden"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to authorized staff only"
        )
    return current_user

def require_student(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    role = current_user.get("role")
    if role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to students only"
        )
    return current_user
