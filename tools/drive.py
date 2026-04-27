import os
import pickle
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
_drive_service = None


def _token_path() -> Path:
    return Path(os.getenv("GOOGLE_TOKEN_FILE", "token.pickle"))


def _credentials_path() -> Path:
    env_path = os.getenv("GOOGLE_CREDENTIALS_FILE")
    if env_path:
        return Path(env_path)

    for candidate in ("credentials.json", "Credentials.json"):
        path = Path(candidate)
        if path.exists():
            return path

    return Path("credentials.json")


def _running_in_docker() -> bool:
    return Path("/.dockerenv").exists()


def get_drive_service():
    creds = None
    token_file = _token_path()

    if token_file.exists():
        with token_file.open("rb") as f:
            creds = pickle.load(f)

    if creds and creds.valid:
        return build("drive", "v3", credentials=creds)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError as exc:
            token_file.unlink(missing_ok=True)
            raise RuntimeError(
                "Google Drive token is expired or revoked. Re-authenticate on host and "
                "restart the container."
            ) from exc
    else:
        if _running_in_docker():
            raise RuntimeError(
                "Google Drive is not authenticated for Docker. Generate token.pickle on "
                "your host, then restart the container."
            )

        creds_file = _credentials_path()
        flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
        creds = flow.run_local_server(port=0)

    with token_file.open("wb") as f:
        pickle.dump(creds, f)

    return build("drive", "v3", credentials=creds)


def _get_cached_drive_service():
    global _drive_service
    if _drive_service is None:
        _drive_service = get_drive_service()
    return _drive_service


def list_drive_files(query: str = "") -> str:
    try:
        drive = _get_cached_drive_service()
        q = (
            f"name contains '{query}'"
            if query
            else "mimeType != 'application/vnd.google-apps.folder'"
        )
        results = drive.files().list(
            q=q,
            pageSize=5,
            fields="files(id,name,webViewLink)",
        ).execute()
        return (
            "\n".join(f"{f['name']}: {f['webViewLink']}" for f in results.get("files", []))
            or "No files found."
        )
    except Exception as e:
        return f"Drive error: {e}"