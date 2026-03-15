import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config import settings
from app.db.seed import seed_demo_patient, seed_education_content
from app.db.session import get_db_session, init_db

_STATIC_DIR = Path(__file__).parent / "static"

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Health Coach")
    await init_db()
    logger.info("Database initialized")
    async for session in get_db_session():
        await seed_demo_patient(session)
        await seed_education_content(session)
    logger.info("Demo patient seeded")
    yield
    logger.info("Shutting down AI Health Coach")


app = FastAPI(
    title="AI Health Coach",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    html = (_STATIC_DIR / "index.html").read_text()
    html = html.replace("%%API_KEY%%", settings.API_KEY)
    return HTMLResponse(html)


app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
