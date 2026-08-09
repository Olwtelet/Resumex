"""Optional YouTube publishing.

Deliberately conservative:

* uploads are **private** unless you ask for something else;
* authorisation is a separate step from uploading;
* the local file is never deleted, moved or modified after a successful upload.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from resumex.config import Config
from resumex.exceptions import MissingDependencyError, NotConfiguredError, UploadError
from resumex.logging import get_logger

logger = get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
WATCH_URL = "https://www.youtube.com/watch?v="

INSTALL_HINT = 'Install the YouTube extra:  pip install "resumex[youtube]"'
SETUP_HINT = (
    "Create an OAuth client (type: Desktop app) in the Google Cloud console with the\n"
    "YouTube Data API v3 enabled, download the JSON, then point youtube.client_secrets\n"
    "at it in resumex.toml and run `resumex youtube-auth`.\n"
    "Docs: https://developers.google.com/youtube/v3/guides/uploading_a_video"
)


@dataclass(frozen=True, slots=True)
class UploadResult:
    video_id: str
    url: str
    privacy: str


def is_available() -> bool:
    """True if the optional YouTube libraries are importable. Never raises."""
    from importlib.util import find_spec

    try:
        return all(
            find_spec(name) is not None
            for name in ("googleapiclient", "google.oauth2", "google_auth_oauthlib")
        )
    except (ImportError, ValueError):
        return False


def default_token_path(config: Config) -> Path:
    return config.paths.internal / "youtube-token.json"


class YouTubeUploader:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.settings = config.youtube

    # -- credentials -----------------------------------------------------

    @property
    def token_path(self) -> Path:
        return self.settings.token or default_token_path(self.config)

    def _client_secrets(self) -> Path:
        secrets = self.settings.client_secrets
        if secrets is None:
            raise NotConfiguredError(
                "YouTube is not configured.\n"
                "Rendering still works normally - this only affects publishing.",
                hint=SETUP_HINT,
            )
        path = Path(secrets)
        if not path.is_file():
            raise NotConfiguredError(
                f"youtube.client_secrets points at a file that does not exist: {path}",
                hint=SETUP_HINT,
            )
        return path

    def authorize(self) -> Path:
        """Run the browser OAuth flow and save the token. Separate from uploading."""
        _require_libraries()
        from google_auth_oauthlib.flow import InstalledAppFlow

        secrets = self._client_secrets()
        flow = InstalledAppFlow.from_client_secrets_file(str(secrets), SCOPES)
        credentials = flow.run_local_server(port=0)

        token = self.token_path
        token.parent.mkdir(parents=True, exist_ok=True)
        token.write_text(credentials.to_json(), encoding="utf-8")
        try:
            token.chmod(0o600)
        except OSError:  # pragma: no cover - not supported on every filesystem
            logger.debug("could not restrict permissions on %s", token)
        return token

    def _credentials(self):
        _require_libraries()
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        token = self.token_path
        if not token.is_file():
            raise NotConfiguredError(
                "YouTube is not authorised yet.\n"
                "Rendering still works normally - this only affects publishing.",
                hint="Run `resumex youtube-auth` to grant upload access.",
            )

        try:
            credentials = Credentials.from_authorized_user_file(str(token), SCOPES)
        except (OSError, ValueError) as exc:
            raise UploadError(
                f"Could not read the YouTube token at {token}: {exc}",
                hint="Delete the file and run `resumex youtube-auth` again.",
            ) from exc

        if credentials.expired and credentials.refresh_token:
            logger.debug("refreshing expired YouTube token")
            try:
                credentials.refresh(Request())
                token.write_text(credentials.to_json(), encoding="utf-8")
            except Exception as exc:  # noqa: BLE001 — google surfaces many refresh errors
                raise UploadError(
                    f"The YouTube token has expired and could not be refreshed: {exc}",
                    hint="Run `resumex youtube-auth` to sign in again.",
                ) from exc

        if not credentials.valid:
            raise UploadError(
                "The stored YouTube credentials are not valid.",
                hint="Run `resumex youtube-auth` to sign in again.",
            )
        return credentials

    # -- uploading -------------------------------------------------------

    def upload(
        self,
        video: Path,
        *,
        title: str,
        description: str,
        privacy: str | None = None,
        tags: list[str] | None = None,
    ) -> UploadResult:
        """Upload a video. Returns its id and watch URL; leaves the file alone."""
        if not video.is_file():
            raise UploadError(f"No such video file: {video}")

        visibility = privacy or self.settings.privacy
        if visibility not in ("private", "unlisted", "public"):
            raise UploadError(f"Unknown privacy setting: {visibility!r}")

        credentials = self._credentials()
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": list(tags or []),
                "categoryId": self.settings.category_id,
            },
            "status": {
                "privacyStatus": visibility,
                "selfDeclaredMadeForKids": self.settings.made_for_kids,
            },
        }

        media = MediaFileUpload(str(video), chunksize=-1, resumable=True, mimetype="video/mp4")
        try:
            service = build("youtube", "v3", credentials=credentials, cache_discovery=False)
            request = service.videos().insert(part="snippet,status", body=body, media_body=media)
            response = request.execute()
        except HttpError as exc:
            raise UploadError(
                f"YouTube rejected the upload (HTTP {exc.resp.status}).",
                hint=_http_hint(exc),
            ) from exc
        except OSError as exc:
            raise UploadError(f"Network error while uploading: {exc}") from exc

        video_id = str(response.get("id", ""))
        if not video_id:
            raise UploadError("YouTube accepted the upload but returned no video id.")

        return UploadResult(video_id=video_id, url=f"{WATCH_URL}{video_id}", privacy=visibility)


def _require_libraries() -> None:
    if not is_available():
        raise MissingDependencyError(
            "The Google API libraries are not installed.", hint=INSTALL_HINT
        )


def _http_hint(exc) -> str:
    status = getattr(getattr(exc, "resp", None), "status", None)
    if status == 401:
        return "Your credentials were rejected. Run `resumex youtube-auth` to sign in again."
    if status == 403:
        return (
            "Usually a quota problem or a channel that is not allowed to upload.\n"
            "Check the YouTube Data API quota for your Google Cloud project."
        )
    if status == 400:
        return "The request was malformed - often a title or description YouTube will not accept."
    return "See https://developers.google.com/youtube/v3/docs/errors for what the code means."
