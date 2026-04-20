"""
Final URCI — saved manual calculations.

The actual URCI math lives on the frontend (user traces the CDV chart).
The server just persists the sample-unit's inputs and the final URCI
number the user read off the chart, per user.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.database import get_db
from app.models import URCIRecord, User
from app.schemas import URCIRecordCreate, URCIRecordResponse
from app.auth import get_current_active_user

router = APIRouter(prefix="/urci", tags=["URCI"])


@router.post("", response_model=URCIRecordResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=URCIRecordResponse, status_code=status.HTTP_201_CREATED)
def create_urci_record(
    body: URCIRecordCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if not body.sample_unit or not body.sample_unit.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sample unit name is required.",
        )
    if not (0.0 <= body.final_urci <= 100.0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="final_urci must be between 0 and 100.",
        )

    record = URCIRecord(
        user_id=current_user.id,
        sample_unit=body.sample_unit.strip(),
        deduct_values=body.deduct_values or {},
        total_dv=float(body.total_dv or 0.0),
        q_value=int(body.q_value or 0),
        final_urci=float(body.final_urci),
        notes=(body.notes or None),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("", response_model=List[URCIRecordResponse])
@router.get("/", response_model=List[URCIRecordResponse])
def list_urci_records(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(URCIRecord)
        .filter(URCIRecord.user_id == current_user.id)
        .order_by(URCIRecord.created_at.desc())
        .all()
    )


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_urci_record(
    record_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    record = (
        db.query(URCIRecord)
        .filter(URCIRecord.id == record_id, URCIRecord.user_id == current_user.id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="URCI record not found")
    db.delete(record)
    db.commit()
    return None
