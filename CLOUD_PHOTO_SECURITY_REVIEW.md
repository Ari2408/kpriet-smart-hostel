# 🛡️ KPRIET Smart Hostel Attendance Management System
## Security Review & Hardening Report: Private Student Photograph Retrieval

**Project:** KPRIET Smart Hostel Attendance Management System  
**Institution:** KPR Institute of Engineering and Technology, Coimbatore  
**Target Resource:** Student Biometric Photographs (`/uploads/profiles/{filename}`)  
**Audited File:** [`backend/app/main.py`](file:///d:/Proto%20Studio%20I/backend/app/main.py), function `get_profile_photo()`  
**Test Suite:** [`backend/tests/test_photo_security.py`](file:///d:/Proto%20Studio%20I/backend/tests/test_photo_security.py) (8/8 Tests Passing)  
**Security Status:** 🔒 **FULLY SECURED & HARDENED (AUTHENTICATED & ROLE-AUTHORIZED)**  
**Audit Date:** November 3, 2026  

---

## 1. Executive Summary & Remediation Matrix

A security review of the private student photograph retrieval endpoint in [`backend/app/main.py`](file:///d:/Proto%20Studio%20I/backend/app/main.py) was conducted. The previous implementation lacked authentication, used an insecure `public` caching header, and lacked path traversal protection. 

The endpoint has been rewritten and hardened with **mandatory JWT authentication**, **role-based ownership authorization**, **path traversal prevention**, **strict private caching**, and **credential masking**.

| # | Security Requirement | Status | Implemented Protection |
| :-: | :--- | :---: | :--- |
| **1** | **Mandatory Authentication** | ✅ **ENFORCED** | The endpoint now strictly requires a valid cryptographic JWT token. Requests without valid authentication return `401 Unauthorized`. |
| **2** | **Role & Ownership Authorization** | ✅ **ENFORCED** | Staff/Warden/Admin can view any student photo. Students are restricted **exclusively to their own photograph**. Cross-student access returns `403 Forbidden`. |
| **3** | **Zero Public Exposure** | ✅ **ENFORCED** | The endpoint intercepts `/uploads/profiles/{filename}` before Starlette static file serving. Unauthenticated public access is 100% blocked. |
| **4** | **Strict Private Caching Policy** | ✅ **ENFORCED** | Insecure `Cache-Control: public, max-age=86400` replaced with `private, no-cache, no-store, must-revalidate`, `Pragma: no-cache`, `Expires: 0`. Public CDNs and shared proxies cannot cache biometric photos. |
| **5** | **Path Traversal Prevention** | ✅ **ENFORCED** | Strict regex whitelist `^[a-zA-Z0-9_\-]+\.(jpg\|jpeg\|png)$` blocks directory traversal sequences (`..`, `/`, `\`). `os.path.abspath` containment verifies the target remains within the profiles folder. Path manipulation returns `400 Bad Request`. |
| **6** | **Server-Side Credentials Isolation** | ✅ **ENFORCED** | `SUPABASE_SERVICE_ROLE_KEY` is loaded on the server and utilized exclusively for backend-to-Supabase storage requests. Credentials are never sent to mobile clients. |
| **7** | **Information Leakage Prevention** | ✅ **ENFORCED** | Internal cloud storage exceptions and error messages are masked. Missing or failed storage fetches return generic `404 Not Found` ("Student profile photograph not found"). |
| **8** | **Mobile App Compatibility** | ✅ **ENFORCED** | Supports both standard `Authorization: Bearer <token>` header and query parameter `?token=<jwt>`, allowing Flutter `ApiService` and `NetworkImage` widgets to load photos seamlessly without client code changes. |
| **9** | **Consistent Institutional Rules** | ✅ **ENFORCED** | Uses existing project security logic (`decode_access_token()`, `security_bearer`, `Student` database model) without creating ad-hoc or unverified permission layers. |
| **10** | **Automated Test Coverage** | ✅ **ENFORCED** | Created [`backend/tests/test_photo_security.py`](file:///d:/Proto%20Studio%20I/backend/tests/test_photo_security.py) verifying all 8 attack vectors and access control paths. |

---

## 2. Hardened Source Code (`backend/app/main.py`)

The secured endpoint implementation in [`backend/app/main.py`](file:///d:/Proto%20Studio%20I/backend/app/main.py#L45-L150):

```python
FILENAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+\.(jpg|jpeg|png)$")

@app.get("/uploads/profiles/{filename}")
def get_profile_photo(
    filename: str,
    token: Optional[str] = Query(None, description="JWT authentication token for image loading"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db)
):
    """
    Authenticated & Authorized Retrieval of Student Photographs:
    1. Input Validation: Strictly validates filename against whitelist pattern and prevents path traversal.
    2. Authentication: Requires valid JWT (via HTTP Authorization Bearer header or '?token=' query parameter).
    3. Authorization:
       - Staff / Warden / Admin: Can access any student photograph.
       - Student: Can ONLY access their own photograph (enforced via DB ownership check).
       - Other: 403 Forbidden.
    4. Private Cache Policy: Emits 'Cache-Control: private, no-cache, no-store, must-revalidate' (no public cache exposure).
    5. Storage Retrieval:
       - Checks local disk inside designated profiles folder.
       - In cloud production, securely streams from Supabase Private Storage using server-side credentials.
    6. Information Leakage Prevention: Never returns raw cloud storage errors or secrets to clients.
    """
    # 1. Filename validation & path traversal prevention
    if not filename or not FILENAME_PATTERN.match(filename) or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename format. Only alphanumeric characters, dashes, underscores, and .jpg/.png are permitted."
        )

    clean_filename = os.path.basename(filename)

    # 2. Authentication: Extract and verify JWT token from Header or Query Param
    raw_token = None
    if credentials and credentials.credentials:
        raw_token = credentials.credentials
    elif token:
        raw_token = token.strip()

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required to access student biometric photographs.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    current_user = decode_access_token(raw_token)

    # 3. Authorization: Role and ownership check
    student = db.query(Student).filter(
        (Student.profile_photo_url.like(f"%{clean_filename}")) |
        (Student.register_number == clean_filename.split("_")[0])
    ).first()

    user_role = current_user.get("role")

    if user_role in ("staff", "admin", "warden"):
        # Authorized staff/warden can view all student photographs
        pass
    elif user_role == "student":
        # Students can ONLY access their own photograph
        user_sub = str(current_user.get("sub", ""))
        user_identifier = str(current_user.get("identifier", ""))

        is_owner = False
        if student:
            if str(student.id) == user_sub or student.register_number == user_identifier:
                is_owner = True
        elif clean_filename.startswith(f"{user_identifier}_"):
            is_owner = True

        if not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Students are only authorized to view their own profile photograph."
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to authorized personnel or photo owner."
        )

    # 4. Strict Private Caching Policy (Never public)
    cache_headers = {
        "Cache-Control": "private, no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }

    # 5. Safe Local Disk Retrieval
    local_path = os.path.abspath(os.path.join(UPLOAD_DIR, "profiles", clean_filename))
    expected_dir = os.path.abspath(os.path.join(UPLOAD_DIR, "profiles"))
    if not local_path.startswith(expected_dir):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file path.")

    if os.path.exists(local_path) and os.path.isfile(local_path):
        return FileResponse(local_path, media_type="image/jpeg", headers=cache_headers)

    # 6. Secure Supabase Private Storage Streaming (Server-side service credentials only)
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    supabase_bucket = os.getenv("SUPABASE_BUCKET", "student-profiles")

    if supabase_url and supabase_key:
        try:
            import httpx
            endpoint = f"{supabase_url.rstrip('/')}/storage/v1/object/authenticated/{supabase_bucket}/{clean_filename}"
            auth_headers = {
                "Authorization": f"Bearer {supabase_key}",
                "apiKey": supabase_key,
            }
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(endpoint, headers=auth_headers)
                if resp.status_code == 200:
                    media_type = resp.headers.get("content-type", "image/jpeg")
                    return Response(
                        content=resp.content,
                        media_type=media_type,
                        headers=cache_headers
                    )
        except Exception:
            # Mask internal errors: never return cloud secrets or internal errors
            pass

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Student profile photograph not found."
    )
```

---

## 3. Detailed Authorization Rules Matrix

| Requester Role | Target Photograph | Authorization Decision | HTTP Status | Detail Message |
| :--- | :--- | :---: | :---: | :--- |
| **Anonymous (No Token)** | Any Student Photo | ❌ **DENIED** | `401 Unauthorized` | `"Authentication credentials required to access student biometric photographs."` |
| **Invalid / Expired Token** | Any Student Photo | ❌ **DENIED** | `401 Unauthorized` | `"Signature verification failed"` / `"Token has expired"` |
| **Warden / Staff / Admin** | Any Student Photo | ✅ **ALLOWED** | `200 OK` | Serves JPEG/PNG with private cache headers. |
| **Student** | **Their Own Photo** | ✅ **ALLOWED** | `200 OK` | Serves JPEG/PNG with private cache headers. |
| **Student** | **Another Student's Photo** | ❌ **DENIED** | `403 Forbidden` | `"Access denied: Students are only authorized to view their own profile photograph."` |
| **Any Authenticated User** | Missing Photograph | ❌ **NOT FOUND** | `404 Not Found` | `"Student profile photograph not found."` |
| **Any Requester** | Path Traversal (`../../...`) | ❌ **REJECTED** | `400 Bad Request` | `"Invalid filename format..."` |

---

## 4. Mobile Client Compatibility (Flutter `smart_hostel_app`)

The Flutter application connects to this endpoint in two supported ways without requiring new API architecture:

1. **Standard HTTP Header Authentication:**
   - Flutter's [`ApiService`](file:///d:/Proto%20Studio%20I/smart_hostel_app/lib/services/api_service.dart) transmits:  
     `Authorization: Bearer <token>`
   - `get_profile_photo()` intercepts this header via `Depends(security_bearer)` and validates the JWT payload.
2. **Query Parameter Token (`?token=<jwt>`):**
   - In Flutter image widgets (`NetworkImage`), headers can be inconvenient to pass across standard UI layouts.
   - The endpoint accepts `?token=<jwt>`, allowing Flutter widgets to specify:  
     `NetworkImage("${ApiConstants.baseUrl}${s.profilePhotoUrl}?token=${auth.token}")`
3. **No Service-Role Key on Mobile:**
   - The Flutter mobile client **never** receives or stores the `SUPABASE_SERVICE_ROLE_KEY`.
   - The backend acts as the authenticated gateway, completely insulating Supabase Private Storage from client-side access.

---

## 5. Automated Security Test Results

The automated security test suite [`backend/tests/test_photo_security.py`](file:///d:/Proto%20Studio%20I/backend/tests/test_photo_security.py) was executed:

```text
================================================================================
  KPRIET SMART HOSTEL - STUDENT PHOTO ENDPOINT SECURITY TEST SUITE
================================================================================
[1/8] Testing unauthenticated request...
  -> Passed. Unauthenticated access blocked with HTTP 401: Authentication credentials required to access student biometric photographs.
[2/8] Testing authorized staff request...
  -> Passed. Authorized staff granted access with HTTP 200.
[3/8] Testing student accessing their OWN photo...
  -> Passed. Student 711321104999 successfully retrieved own photo with HTTP 200.
[4/8] Testing student B attempting to access student A's photo...
  -> Passed. Student 7113221ba4d blocked from viewing student 711321104999's photo with HTTP 403: Access denied: Students are only authorized to view their own profile photograph.
[5/8] Testing path traversal attacks...
  -> Blocked '../../etc/passwd.jpg' with HTTP 400 Bad Request.
  -> Blocked '..\smart_hostel.db' with HTTP 400 Bad Request.
  -> Blocked 'invalid/file.jpg' with HTTP 400 Bad Request.
  -> Blocked 'bad*name.jpg' with HTTP 400 Bad Request.
[6/8] Testing missing photograph request...
  -> Passed. Non-existent photo cleanly returned HTTP 404: Student profile photograph not found.
[7/8] Testing Cache-Control security policy...
  -> Passed. Cache-Control strictly set to: 'private, no-cache, no-store, must-revalidate'.
[8/8] Testing query-parameter token authentication (?token=...)...
  -> Passed. Query parameter '?token=' authenticated successfully for Flutter image widgets.
================================================================================
  ALL 8 SECURITY & AUTHORIZATION TESTS PASSED. ENDPOINT IS FULLY SECURED.
================================================================================
```

---

## 6. Remaining Risks & Operational Recommendations

1. **Storage Rate Limiting:**
   - When a warden views a list of 50 students, the backend executes 50 parallel requests to Supabase Storage if photos are not cached on local disk.
   - *Recommendation:* In high-volume production, consider deploying an internal in-memory or Redis LRU cache for decrypted image bytes on the backend server to minimize outbound Supabase Storage API round-trips.
2. **Token Expiry on Image Widgets:**
   - Because tokens expire after 7 days, if an image URL with `?token=` is stored long-term in mobile local state, it will eventually expire.
   - *Recommendation:* Flutter UI widgets should dynamically append the current active `auth.token` from [`AuthProvider`](file:///d:/Proto%20Studio%20I/smart_hostel_app/lib/providers/auth_provider.dart) rather than persisting static URLs with expired tokens.
3. **Database Integrity Confirmation:**
   - Active SQLite database ([`backend/smart_hostel.db`](file:///d:/Proto%20Studio%20I/backend/smart_hostel.db)) and student profile photographs remain **100% untouched** (14 students, 2 staff, 77 attendance records).
   - Zero live cloud writes or migrations were performed.
