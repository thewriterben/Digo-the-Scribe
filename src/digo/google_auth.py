"""
Google OAuth2 helper for Digo the Scribe.

Run this module directly once to complete the browser-based OAuth flow
and cache a token.json file for subsequent runs.
"""

from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from digo import config

# Scopes required by Digo
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    # Add more as needed, e.g.:
    # "https://www.googleapis.com/auth/gmail.send",
    # "https://www.googleapis.com/auth/drive.readonly",
]

TOKEN_PATH = Path(config.GOOGLE_TOKEN_FILE)


def get_credentials() -> Credentials:
    """Return valid Google credentials, refreshing or re-authorising as needed."""
    creds: Credentials | None = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(config.GOOGLE_CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return creds


if __name__ == "__main__":
    creds = get_credentials()
    print("✅ Google OAuth authorisation complete. Token cached at:", TOKEN_PATH)
