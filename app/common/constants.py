import os

from dotenv import load_dotenv

load_dotenv()


DATABASE_URI = f"postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASSWORD")}@{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/{os.getenv("DB_NAME")}"
SECRET_KEY = os.getenv("SECRET_KEY")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS")
ALLOWED_IMAGE_ORIGIN = os.getenv("ALLOWED_IMAGE_ORIGIN")
REDIS_URL = os.getenv("REDIS_URL")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8082")

# JWT
JWT_SECRET = os.getenv("JWT_SECRET")
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "45"))
REFRESH_TOKEN_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", "7"))
JWT_ALG = "HS256"


# Google
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")


# github
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI")


# drop box
DROPBOX_CLIENT_ID = os.getenv("DROPBOX_CLIENT_ID")
DROPBOX_CLIENT_SECRET = os.getenv("DROPBOX_CLIENT_SECRET")
DROPBOX_REDIRECT_URI = os.getenv("DROPBOX_REDIRECT_URI")

PER_PAGE = 20
IS_DEV = bool(os.getenv("DEV", "").lower() == "true")
FRONTEND_URL = os.getenv("FRONTEND_URL", "")


# Configuration
UPLOAD_DIR = "uploads"
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
GOOGLE_FILES_URL = "https://www.googleapis.com/drive/v3/files"
DROPBOX_SEARCH_URL = "https://api.dropboxapi.com/2/files/search_v2"
DROPBOX_API = "https://api.dropboxapi.com/2/files"


MIME_TYPE_GROUPS = {
    "document": [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # DOCX
        "application/msword",  # DOC
    ],
    "video": [
        "video/mp4",
        "video/x-msvideo",  # AVI
        "video/quicktime",  # MOV
        "video/x-ms-wmv",  # WMV
        "video/mpeg",  # MPEG
        "video/x-matroska",  # MKV
        "video/x-flv",  # FLV
    ],
    "image": [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/svg+xml",
    ],
}


DROPBOX_EXT_GROUPS = {
    "document": [
        ".pdf",
        ".docx",
        ".doc",
    ],
    "video": [
        ".mp4",
        ".avi",
        ".mov",
        ".wmv",
        ".mpeg",
        ".mpg",
        ".mkv",
        ".flv",
    ],
    "image": [
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".svg",
    ],
}
