import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.core.db import init_db  # noqa: E402
from app.api.routes import router  # noqa: E402


app = FastAPI(title="Jason Capital API", version="0.1.0")
init_db()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")
