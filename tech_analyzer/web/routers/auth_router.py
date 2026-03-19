"""OAuth2 callback handler — receives Upstox redirect and exchanges code for token."""
import logging
import os

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from tech_analyzer.data.auth import save_token, _exchange_code

router = APIRouter(tags=["auth"])
log = logging.getLogger(__name__)

# Holds the auth result so /api/auth/status can report it
_auth_state: dict = {"pending": False, "done": False, "error": ""}


@router.get("/callback")
def oauth_callback(code: str | None = None, error: str | None = None):
    """Upstox redirects here after login with ?code=... or ?error=..."""
    if error:
        _auth_state.update({"pending": False, "done": False, "error": error})
        log.error("OAuth error from Upstox: %s", error)
        return HTMLResponse("<h2>Login failed: " + error + "</h2>", status_code=400)

    if not code:
        return HTMLResponse("<h2>Missing code parameter.</h2>", status_code=400)

    try:
        api_key    = os.environ.get("UPSTOX_API_KEY", "")
        api_secret = os.environ.get("UPSTOX_API_SECRET", "")
        redirect   = os.environ.get("UPSTOX_REDIRECT_URI", "http://127.0.0.1:8000/callback")

        response = _exchange_code(code, api_key, api_secret, redirect)
        token = response.access_token
        user  = getattr(response, "user_name", "") or ""
        save_token(token, user)

        _auth_state.update({"pending": False, "done": True, "error": ""})
        log.info("Upstox auth successful — token saved (user: %s)", user or "unknown")

        return HTMLResponse(
            f"<html><body style='font-family:sans-serif;padding:40px'>"
            f"<h2>✅ Login successful{f' — {user}' if user else ''}.</h2>"
            f"<p>You can close this tab and return to the dashboard.</p>"
            f"</body></html>"
        )
    except Exception as e:
        _auth_state.update({"pending": False, "done": False, "error": str(e)})
        log.error("Token exchange failed: %s", e)
        return HTMLResponse(f"<h2>Token exchange failed: {e}</h2>", status_code=500)


@router.get("/api/auth/status")
def auth_status():
    from tech_analyzer.data.auth import load_token
    token = load_token()
    return {"authenticated": token is not None, **_auth_state}


@router.get("/api/auth/url")
def auth_url():
    """Return the Upstox login URL so the UI or user can open it."""
    api_key  = os.environ.get("UPSTOX_API_KEY", "")
    redirect = os.environ.get("UPSTOX_REDIRECT_URI", "http://127.0.0.1:8000/callback")
    url = (
        f"https://api.upstox.com/v2/login/authorization/dialog"
        f"?response_type=code&client_id={api_key}&redirect_uri={redirect}"
    )
    return {"url": url}
