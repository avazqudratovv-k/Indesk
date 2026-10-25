from fastapi import APIRouter

from app.routers.deps import CurrentUser
from app.schemas.users import User

router = APIRouter(tags=["me"])


@router.get("/me", response_model=User)
def me(user: CurrentUser) -> User:
    return User.model_validate(user)
