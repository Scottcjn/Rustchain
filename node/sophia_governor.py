import os
import hmac

def _is_admin(req) -> bool:
    """
    Checks if the request is authorized with the admin key.
    Fix: Use hmac.compare_digest to prevent timing attacks.
    """
    required = os.getenv("RC_ADMIN_KEY", "").strip()
    if not required:
        return False
    provided = (req.headers.get("X-Admin-Key") or req.headers.get("X-API-Key") or "").strip()
    # Use hmac.compare_digest for constant-time comparison
    return bool(provided and hmac.compare_digest(provided, required))

def register_sophia_governor_endpoints(app):
    # Dummy implementation for local verification/structure
    pass
