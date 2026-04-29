import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from models.database import create_tables
from routers import generate, documents, auth, admin, analytics, notifications, projects as projects_router


UPLOADS_BASE = os.path.join(os.path.dirname(__file__), "..", "uploads")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure upload directories exist at startup
    for subdir in ("logos", "images"):
        os.makedirs(os.path.join(UPLOADS_BASE, subdir), exist_ok=True)
    create_tables()
    yield


app = FastAPI(title="DocGen API", version="3.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Document-Id", "X-Group-Id", "X-Version"],
)

# Generation & documents (no prefix — legacy URLs stay stable)
app.include_router(generate.router)
app.include_router(documents.router)

# Phase 3 routers
app.include_router(auth.router)                          # /auth/*
app.include_router(admin.router)                         # /admin/*
app.include_router(analytics.router)                     # /analytics/*
app.include_router(notifications.router)                 # /notifications/*
app.include_router(projects_router.router, prefix="/projects", tags=["projects"])  # /projects/*

# Serve uploaded logos/images (for frontend preview)
uploads_path = os.path.abspath(UPLOADS_BASE)
if os.path.exists(uploads_path):
    app.mount("/uploads", StaticFiles(directory=uploads_path), name="uploads")


@app.get("/health")
def health():
    return {"status": "ok", "version": "3.0.0"}
