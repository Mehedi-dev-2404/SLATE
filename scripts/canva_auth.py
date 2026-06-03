import hashlib
import base64
import os
import secrets
import urllib.parse
import httpx
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

CLIENT_ID = "OC-AZ6OdDKa2WYo"
REDIRECT_URI = "http://127.0.0.1:8080/callback"
SCOPES = "design:content:write design:content:read profile:read design:meta:read"

# Generate PKCE code verifier and challenge
code_verifier = secrets.token_urlsafe(64)
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode()).digest()
).rstrip(b"=").decode()

auth_code = None

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        params = parse_qs(urlparse(self.path).query)
        auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Auth complete. Return to terminal.")

    def log_message(self, *args):
        pass

auth_url = (
    f"https://www.canva.com/api/oauth/authorize"
    f"?code_challenge_method=s256"
    f"&response_type=code"
    f"&client_id={CLIENT_ID}"
    f"&scope={urllib.parse.quote(SCOPES)}"
    f"&code_challenge={code_challenge}"
    f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
)

print(f"\nOpen this URL in your browser:\n\n{auth_url}\n")
print("Waiting for callback...")

server = HTTPServer(("127.0.0.1", 8080), CallbackHandler)
server.handle_request()

if not auth_code:
    print("ERROR: No auth code received")
    exit(1)

print(f"Auth code received. Exchanging for tokens...")

import base64
CLIENT_SECRET = os.environ.get("CANVA_CLIENT_SECRET", "")
credentials = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()

response = httpx.post(
    "https://api.canva.com/rest/v1/oauth/token",
    data={
        "grant_type": "authorization_code",
        "code": auth_code,
        "code_verifier": code_verifier,
        "redirect_uri": REDIRECT_URI,
    },
    headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {credentials}"
    }
)

if response.status_code != 200:
    print(f"ERROR: {response.status_code} — {response.text}")
    exit(1)

tokens = response.json()
print("\n✅ SUCCESS — add these to your .env and Railway env vars:\n")
print(f"CANVA_ACCESS_TOKEN={tokens['access_token']}")
print(f"CANVA_REFRESH_TOKEN={tokens.get('refresh_token', 'none')}")
print(f"\nAccess token expires in: {tokens.get('expires_in', 'unknown')} seconds")
