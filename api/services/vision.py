import json
import logging
import os

from google.cloud import vision
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

# Initialize Google Cloud Vision client with credentials from environment
vision_client = None


def get_vision_client():
    """Get Google Cloud Vision client instance using env vars only."""
    global vision_client
    if vision_client is None:
        try:
            import base64

            creds_json_str = os.getenv("GOOGLE_CLOUD_CREDENTIALS")
            if creds_json_str:
                creds_json_str = creds_json_str.strip()
                if len(creds_json_str) >= 2 and creds_json_str[0] == creds_json_str[-1] and creds_json_str[0] in {"\"", "'"}:
                    creds_json_str = creds_json_str[1:-1]
                creds_dict = json.loads(creds_json_str)
                credentials = service_account.Credentials.from_service_account_info(creds_dict)
                vision_client = vision.ImageAnnotatorClient(credentials=credentials)
            else:
                creds_b64 = os.getenv("GOOGLE_CLOUD_CREDENTIALS_B64")
                if creds_b64:
                    cleaned_b64 = "".join(creds_b64.strip().split())
                    if len(cleaned_b64) >= 2 and cleaned_b64[0] == cleaned_b64[-1] and cleaned_b64[0] in {"\"", "'"}:
                        cleaned_b64 = cleaned_b64[1:-1]
                    padding = "=" * (-len(cleaned_b64) % 4)
                    creds_json_decoded = base64.b64decode(cleaned_b64 + padding, validate=True).decode("utf-8")
                    creds_dict = json.loads(creds_json_decoded)
                    credentials = service_account.Credentials.from_service_account_info(creds_dict)
                    vision_client = vision.ImageAnnotatorClient(credentials=credentials)
                else:
                    raise RuntimeError(
                        "Missing Google Vision credentials. Set GOOGLE_CLOUD_CREDENTIALS or GOOGLE_CLOUD_CREDENTIALS_B64."
                    )
        except Exception as e:
            logger.error(f"Failed to initialize Vision client: {e}", exc_info=True)
            raise RuntimeError(f"Vision client initialization failed: {e}")
    return vision_client
