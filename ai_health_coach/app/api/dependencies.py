from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Clinician
from app.db.repository import get_patient
from app.db.session import get_db_session


async def verify_api_key(x_api_key: str = Header(...)) -> str:
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


async def verify_clinician(
    x_api_key: str = Header(...),
    session: AsyncSession = Depends(get_db_session),
) -> Clinician:
    """Authenticate clinician by API key from DB."""
    result = await session.execute(
        select(Clinician).where(
            Clinician.api_key == x_api_key, Clinician.is_active == True
        )
    )
    clinician = result.scalar_one_or_none()
    if not clinician:
        raise HTTPException(status_code=401, detail="Invalid clinician API key")
    return clinician


async def verify_consent(
    patient_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    if not settings.CONSENT_CHECK_ENABLED:
        return
    patient = await get_patient(session, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if not patient.consent_status:
        raise HTTPException(
            status_code=403,
            detail="Patient has not granted consent",
        )
