"""Medbridge consent verification service.

In production, this would call the Medbridge API to verify consent.
For local dev, consent is managed via the Patient DB record.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import get_patient


async def check_consent(session: AsyncSession, patient_id: str) -> bool:
    patient = await get_patient(session, patient_id)
    if not patient:
        return False
    return patient.consent_status
