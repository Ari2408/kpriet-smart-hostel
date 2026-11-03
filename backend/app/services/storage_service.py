import os
import re
import uuid
import base64
from typing import Optional, Tuple
from pathlib import Path

# Base upload directory for local caching / development fallback
SERVICE_DIR = Path(__file__).resolve().parent
APP_DIR = SERVICE_DIR.parent
UPLOAD_DIR = APP_DIR / "uploads" / "profiles"

FILENAME_REGEX = re.compile(r"^[a-zA-Z0-9_\-]+\.(jpg|jpeg|png)$")

def generate_unique_photo_filename(register_number: str) -> str:
    """
    Generates a secure, deterministic-prefixed, unique filename for a student photograph.
    Format: {clean_register_number}_{unique_hex}.jpg
    Matches the canonical pattern: ^[a-zA-Z0-9_\\-]+\\.(jpg|jpeg|png)$
    """
    clean_reg = re.sub(r"[^a-zA-Z0-9_\-]", "", str(register_number).strip())
    if not clean_reg:
        clean_reg = "student"
    unique_token = uuid.uuid4().hex[:8]
    return f"{clean_reg}_{unique_token}.jpg"

def upload_photo_to_supabase(
    filename: str,
    image_bytes: bytes,
    content_type: str = "image/jpeg"
) -> Tuple[bool, str]:
    """
    Uploads student photograph to Supabase Private Storage via REST API using
    server-side service-role key.
    - Never exposes service-role key to mobile clients.
    - Uses x-upsert: false to guarantee no accidental overwrites.
    """
    try:
        import httpx
    except ImportError:
        return False, "httpx library not available for cloud storage"

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SUPABASE_KEY")
    )
    supabase_bucket = os.getenv("SUPABASE_BUCKET", "student-profiles")

    if not supabase_url or not supabase_key:
        return False, "Missing Supabase configuration (SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY)"

    endpoint = f"{supabase_url.rstrip('/')}/storage/v1/object/{supabase_bucket}/{filename}"
    headers = {
        "Authorization": f"Bearer {supabase_key}",
        "apiKey": supabase_key,
        "Content-Type": content_type,
        "x-upsert": "false",
    }

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(endpoint, headers=headers, content=image_bytes)
            if resp.status_code in (200, 201):
                return True, "UPLOAD_SUCCESS"
            return False, f"Supabase storage error: HTTP {resp.status_code}"
    except Exception as e:
        return False, f"Cloud storage connection exception: {str(e)}"

def save_profile_photo(register_number: str, image_base64: str) -> Optional[str]:
    """
    Saves a student profile photograph:
    - In PRODUCTION:
      * Uploads image bytes directly to Supabase Private Storage ('student-profiles').
      * Only returns the stable relative reference ('/uploads/profiles/{filename}')
        if the upload succeeds.
      * If upload fails, returns None so broken URLs are never stored in PostgreSQL.
    - In DEVELOPMENT:
      * Saves to local disk inside 'backend/app/uploads/profiles/'.
      * Attempts cloud upload if Supabase credentials are configured.
      * Returns '/uploads/profiles/{filename}' on success.
    """
    if not image_base64 or not image_base64.strip():
        return None

    # Clean base64 header if present
    raw_b64 = image_base64.strip()
    if "base64," in raw_b64:
        raw_b64 = raw_b64.split("base64,")[1]

    try:
        image_bytes = base64.b64decode(raw_b64)
    except Exception:
        return None

    if len(image_bytes) == 0:
        return None

    filename = generate_unique_photo_filename(register_number)
    is_production = os.getenv("ENVIRONMENT", "development").strip().lower() in ("production", "prod")

    if is_production:
        # 1. Cloud upload is MANDATORY in production
        upload_ok, error_msg = upload_photo_to_supabase(filename, image_bytes)
        if not upload_ok:
            # Mask internal details from logs
            print(f"[Storage Service] Cloud upload failed in production for {register_number}: {error_msg}")
            return None

        # 2. Local copy as non-critical cache if possible
        try:
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            local_path = UPLOAD_DIR / filename
            with open(local_path, "wb") as f:
                f.write(image_bytes)
        except Exception:
            pass

        return f"/uploads/profiles/{filename}"

    else:
        # Development mode: local disk primary
        try:
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            local_path = UPLOAD_DIR / filename
            with open(local_path, "wb") as f:
                f.write(image_bytes)
        except Exception as e:
            print(f"[Storage Service] Local file save failed: {e}")
            return None

        # Also attempt Supabase upload in development if credentials exist
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
        if supabase_url and supabase_key:
            try:
                upload_photo_to_supabase(filename, image_bytes)
            except Exception:
                pass

        return f"/uploads/profiles/{filename}"

def delete_profile_photo(filename_or_url: str) -> bool:
    """
    Safely purges student photo from local disk and cloud storage if present.
    """
    if not filename_or_url:
        return False

    clean_filename = os.path.basename(filename_or_url)
    if not FILENAME_REGEX.match(clean_filename):
        return False

    # 1. Purge from local disk
    try:
        local_path = UPLOAD_DIR / clean_filename
        if local_path.exists() and local_path.is_file():
            local_path.unlink()
    except Exception:
        pass

    # 2. Purge from Supabase Storage if configured
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SUPABASE_KEY")
    )
    supabase_bucket = os.getenv("SUPABASE_BUCKET", "student-profiles")

    if supabase_url and supabase_key:
        try:
            import httpx
            endpoint = f"{supabase_url.rstrip('/')}/storage/v1/object/{supabase_bucket}"
            headers = {
                "Authorization": f"Bearer {supabase_key}",
                "apiKey": supabase_key,
                "Content-Type": "application/json",
            }
            payload = {"prefixes": [clean_filename]}
            with httpx.Client(timeout=10.0) as client:
                client.request("DELETE", endpoint, headers=headers, json=payload)
        except Exception:
            pass

    return True
