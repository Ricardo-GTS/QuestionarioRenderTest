from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.user import UserReputationOut
from app.services.stats import compute_user_reputation

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/me", response_model=UserReputationOut)
def read_my_reputation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserReputationOut:
    return UserReputationOut(**compute_user_reputation(db, current_user.id))
