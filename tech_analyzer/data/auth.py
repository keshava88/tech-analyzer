"""
Upstox OAuth2 flow and access token management.

Token is cached at ~/.tech_analyzer/upstox_token.json and reused until it
is more than 20 hours old (Upstox tokens are valid until end of trading day).

Typical usage:
    python -m tech_analyzer --auth        # one-time setup
    token = load_token()                  # subsequent calls
"""
import json
import webbrowser
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import upstox_client

TOKEN_FILE = Path.home() / ".tech_analyzer" / "upstox_token.json"
TOKEN_MAX_AGE_HOURS = 20  # conservative — Upstox tokens expire at end of day


def load_token() -> str | None:
    """Return a cached access token if one exists and is fresh, else None."""
    if not TOKEN_FILE.exists():
        return None
    try:
        data = json.loads(TOKEN_FILE.read_text())
        saved_at = datetime.fromisoformat(data["saved_at"])
        if datetime.now() - saved_at < timedelta(hours=TOKEN_MAX_AGE_HOURS):
            return data["access_token"]
    except (KeyError, ValueError):
        pass
    return None


def save_token(access_token: str, user_name: str = "") -> None:
    """Persist access token to disk."""
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps({
        "access_token": access_token,
        "user_name": user_name,
        "saved_at": datetime.now().isoformat(),
    }))


def _exchange_code(code: str, api_key: str, api_secret: str, redirect_uri: str) -> upstox_client.TokenResponse:
    """Exchange an authorization code for an access token via the Upstox SDK."""
    configuration = upstox_client.Configuration()
    api_client = upstox_client.ApiClient(configuration)
    login_api = upstox_client.LoginApi(api_client)
    return login_api.token(
        "2.0",
        code=code,
        client_id=api_key,
        client_secret=api_secret,
        redirect_uri=redirect_uri,
        grant_type="authorization_code",
    )


def run_oauth_flow(api_key: str, api_secret: str, redirect_uri: str) -> str:
    """
    Run the full OAuth2 flow:
    1. Open the Upstox login URL in the default browser.
    2. Start a one-shot local HTTP server to capture the callback code.
    3. Exchange the code for an access token.
    4. Save and return the access token.
    """
    received_code: list[str] = []  # mutable container for the closure

    class _CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            params = parse_qs(urlparse(self.path).query)
            if "code" in params:
                received_code.append(params["code"][0])
                body = b"<html><body><h2>Login successful. You may close this tab.</h2></body></html>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing code parameter.")

        def log_message(self, *args):  # silence default request logging
            pass

    # Parse port from redirect_uri (e.g. http://localhost:8000/callback → 8000)
    parsed = urlparse(redirect_uri)
    port = parsed.port or 8000

    auth_url = (
        f"https://api.upstox.com/v2/login/authorization/dialog"
        f"?response_type=code&client_id={api_key}&redirect_uri={redirect_uri}"
    )

    print(f"\nOpening Upstox login in your browser...")
    print(f"If the browser does not open, visit:\n  {auth_url}\n")
    webbrowser.open(auth_url)

    print(f"Waiting for callback on port {port} ...")
    server = HTTPServer(("127.0.0.1", port), _CallbackHandler)
    server.timeout = 120  # give up after 2 minutes
    while not received_code:
        server.handle_request()
        if not received_code and server.timeout is not None:
            # handle_request timed out
            break
    server.server_close()

    if not received_code:
        raise RuntimeError("No authorization code received from Upstox callback.")

    print("Authorization code received. Exchanging for access token...")
    response = _exchange_code(received_code[0], api_key, api_secret, redirect_uri)

    access_token = response.access_token
    user_name = getattr(response, "user_name", "") or ""
    save_token(access_token, user_name)

    print(f"Access token saved to {TOKEN_FILE}")
    if user_name:
        print(f"Logged in as: {user_name}")

    return access_token
