import os

from dotenv import load_dotenv

load_dotenv()


DATABASE_URI = f"postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASSWORD")}@{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/{os.getenv("DB_NAME")}"
SECRET_KEY = os.getenv("SECRET_KEY")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS")

# JWT
JWT_SECRET = os.getenv("JWT_SECRET")
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))
REFRESH_TOKEN_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", "7"))
JWT_ALG = "HS256"


# Google
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
