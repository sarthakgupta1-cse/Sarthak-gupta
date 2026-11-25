"""One-time helper: obtain a Gmail API refresh token with the gmail.send scope ONLY.

Run on any computer with a browser (once):
    pip install google-auth-oauthlib
    python scripts/get_gmail_refresh_token.py path/to/client_secret.json

Copy the printed values into GitHub Secrets (GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET,
GMAIL_REFRESH_TOKEN). Then delete client_secret.json from your computer, or keep it
somewhere private. Never commit it.
"""
import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python get_gmail_refresh_token.py client_secret.json")
    flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    info = json.load(open(sys.argv[1]))
    client = info.get("installed") or info.get("web") or {}
    print("\nAdd these as GitHub repository secrets:\n")
    print(f"GMAIL_CLIENT_ID={client.get('client_id')}")
    print(f"GMAIL_CLIENT_SECRET={client.get('client_secret')}")
    print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")
    print("\nGMAIL_SENDER = the Gmail address you just signed in with.")


if __name__ == "__main__":
    main()
