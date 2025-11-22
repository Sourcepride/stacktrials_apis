from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.common.constants import ALLOWED_ORIGINS, SECRET_KEY
from app.common.utils import safe_json_loads
from app.common.ws_manager import manager
from app.core.exceptions import setup_logger
from app.modules import chat, creator, management, media, student

from .modules import account, auth, course, media


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await manager.connect()
        yield
    finally:
        await manager.close()


app = FastAPI(lifespan=lifespan)
app_logger = setup_logger()


static_path = Path(__file__).resolve().parent.joinpath("static")
app.mount("/static", StaticFiles(directory=static_path), name="static")


assert ALLOWED_ORIGINS is not None
assert SECRET_KEY is not None

# middlewares
origins = safe_json_loads(ALLOWED_ORIGINS, [])


# @app.middleware("http")
# async def log_exceptions(request: Request, call_next):
#     try:
#         return await call_next(request)
#     except Exception as e:
#         app_logger.error(f"Unhandled error: {e}", exc_info=True)
#         return JSONResponse(
#             {"detail": "Internal server error"}, status_code=500
#         )


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="trails",
    max_age=86400,
    same_site="lax",
    https_only=False,  # TODO: set True in production with HTTPS
)


@app.get("/")
async def index():
    return {"ok": True}


version_1 = "/api/v1"
app.include_router(media.router.media_routes, prefix=f"{version_1}", tags=["media"])
app.include_router(auth.router.router, prefix=f"{version_1}/auth", tags=["auth"])
app.include_router(
    account.router.router, prefix=f"{version_1}/account", tags=["account"]
)
app.include_router(
    course.router.router, prefix=f"{version_1}/courses", tags=["courses"]
)
app.include_router(
    creator.router.router, prefix=f"{version_1}/creators", tags=["creators"]
)
app.include_router(
    student.router.router, prefix=f"{version_1}/student", tags=["students"]
)
app.include_router(
    management.router.router, prefix=f"{version_1}/management", tags=["management"]
)
app.include_router(student.ws_router.router, prefix="/ws/documents")
app.include_router(chat.ws_router.router, prefix="/ws/chat")
