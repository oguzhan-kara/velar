from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.config import settings
from typing import TypedDict

security = HTTPBearer()


class CurrentUser(TypedDict):
    user_id: str
    email: str


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CurrentUser:
    token = credentials.credentials
    try:
        # Check Supabase dashboard > Settings > Auth > JWT Settings
        # If project uses asymmetric keys (ES256/JWKS), update algorithms=["ES256"]
        # and replace supabase_jwt_secret with the JWKS public key.
        # For most new projects in 2026, HS256 is still the default runtime behavior;
        # verify at implementation time.
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        user_id: str | None = payload.get("sub")
        email: str = payload.get("email", "")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "Invalid token", "code": "INVALID_TOKEN"},
            )
        return CurrentUser(user_id=user_id, email=email)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Could not validate credentials", "code": "JWT_ERROR"},
        ) from exc
