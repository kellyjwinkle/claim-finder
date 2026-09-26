"""Google Drive text extraction for evidence documents.

Reads a file from a private Google Drive folder (by file ID) and extracts
text so it can be matched against settlement class-period/merchant criteria.
Only text is stored in Supabase (evidence.extracted_text) -- the document
itself always stays in Drive.

Auth: uses a Google service account. Share your evidence folder with the
service account's email address (read-only is enough) so this code can read
files without needing your personal Google login.

Required config (env var or Streamlit secret):
  GOOGLE_SERVICE_ACCOUNT_JSON -- the full JSON key content as a string.

System dependencies (documented in packages.txt for Streamlit Cloud):
  tesseract-ocr  -- for OCR on images and scanned PDF pages
  poppler-utils  -- for rendering PDF pages to images (pdf2image)
"""
import io
import json
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def _get_credentials_json():
    if "GOOGLE_SERVICE_ACCOUNT_JSON" in os.environ:
        return os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    try:
        import streamlit as st
        return st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    except Exception:
        return None


def get_drive_service():
    raw_json = _get_credentials_json()
    if not raw_json:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is not configured -- see .env.example."
        )
    info = json.loads(raw_json)
    credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def get_file_metadata(file_id):
    service = get_drive_service()
    return service.files().get(fileId=file_id, fields="id,name,mimeType,size").execute()


def download_file_bytes(file_id):
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    buffer.seek(0)
    return buffer.read()


def extract_text_from_image_bytes(image_bytes):
    from PIL import Image
    import pytesseract

    image = Image.open(io.BytesIO(image_bytes))
    return pytesseract.image_to_string(image)


def extract_text_from_pdf_bytes(pdf_bytes, ocr_fallback=True):
    """Try direct text extraction first (fast, works for digital PDFs).
    Falls back to rendering pages as images and running OCR for scanned PDFs
    that have no embedded text layer."""
    import pdfplumber

    text_parts = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)

    combined = "\n".join(text_parts).strip()
    if combined or not ocr_fallback:
        return combined

    from pdf2image import convert_from_bytes
    import pytesseract

    ocr_parts = []
    images = convert_from_bytes(pdf_bytes)
    for image in images:
        ocr_parts.append(pytesseract.image_to_string(image))
    return "\n".join(ocr_parts).strip()


def extract_text_from_drive_file(file_id):
    """Fetch a Drive file's metadata and content, then extract text using the
    appropriate method for its MIME type. Returns a dict with keys:
    text, mime_type, name, error (error is None on success)."""
    try:
        metadata = get_file_metadata(file_id)
        mime_type = metadata.get("mimeType", "")
        name = metadata.get("name", "")
        content = download_file_bytes(file_id)

        if mime_type == "application/pdf":
            text = extract_text_from_pdf_bytes(content)
        elif mime_type.startswith("image/"):
            text = extract_text_from_image_bytes(content)
        elif mime_type == "text/plain":
            text = content.decode("utf-8", errors="ignore")
        else:
            return {
                "text": None,
                "mime_type": mime_type,
                "name": name,
                "error": f"Unsupported file type for OCR: {mime_type}. "
                         "Supported: PDF, images (jpg/png), plain text.",
            }

        return {"text": text, "mime_type": mime_type, "name": name, "error": None}

    except Exception as exc:  # noqa: BLE001 -- surface any failure to the caller
        return {"text": None, "mime_type": None, "name": None, "error": str(exc)}
