from fastapi import APIRouter, Depends, HTTPException, status, Request
from app.dependencies import get_current_user, CurrentUser
from app.users import service as users_service

router = APIRouter(tags=["users"])


@router.get("/me")
async def get_me(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    # Extract token from Authorization header to use as user-scoped client credential
    auth_header = request.headers.get("authorization", "")
    user_jwt = auth_header.replace("Bearer ", "").replace("bearer ", "")

    profile = await users_service.get_user_profile(current_user["user_id"], user_jwt)
    if profile is None:
        # Profile doesn't exist yet — return minimal user info from JWT
        return {
            "user_id": current_user["user_id"],
            "email": current_user["email"],
            "display_name": None,
        }
    return profile
