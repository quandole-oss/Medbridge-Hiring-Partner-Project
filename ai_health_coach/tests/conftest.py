import os

# Set test env vars BEFORE any app imports
os.environ["ANTHROPIC_API_KEY"] = "test-key"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["API_KEY"] = "test-api-key"
os.environ["CONSENT_CHECK_ENABLED"] = "true"

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.db.models import Base  # noqa: E402
from app.db.session import get_db_session  # noqa: E402
from app.main import app  # noqa: E402


test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)


async def override_get_db_session():
    async with test_session_factory() as session:
        yield session


app.dependency_overrides[get_db_session] = override_get_db_session


@pytest_asyncio.fixture
async def db_session():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with test_session_factory() as session:
        yield session
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def api_headers():
    return {"X-Api-Key": "test-api-key"}


@pytest_asyncio.fixture
async def clinician(db_session):
    """Seed a test clinician."""
    from app.db.models import Clinician
    c = Clinician(
        clinician_id="test-clinician",
        name="Dr. Test",
        email="test@example.com",
        api_key="test-clinician-key",
    )
    db_session.add(c)
    await db_session.commit()
    return c


@pytest.fixture
def clinician_headers():
    return {"X-Api-Key": "test-clinician-key"}
