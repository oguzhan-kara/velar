from fastapi import APIRouter, HTTPException, status
from app.auth.schemas import LoginRequest, TokenResponse
from app.auth import service as auth_service

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    try:
        result = await auth_service.sign_in(body.email, body.password)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Invalid credentials", "code": "INVALID_CREDENTIALS"},
        )
    return TokenResponse(access_token=result["access_token"])
