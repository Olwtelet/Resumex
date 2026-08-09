"""Optional publishing targets. Nothing here runs unless you ask for it."""

from resumex.upload.youtube import UploadResult, YouTubeUploader, is_available

__all__ = ["UploadResult", "YouTubeUploader", "is_available"]
