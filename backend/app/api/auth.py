from fastapi import Request, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from app.utils.logger import get_logger

logger = get_logger(__name__)
security = HTTPBearer(auto_error=False)

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """
    Extracts the Clerk user ID from the Authorization Bearer token.
    For this prototype, we decode the JWT without verifying the signature 
    since we are trusting the Railway proxy / frontend.
    In a full production app, you should fetch the Clerk JWKS and verify the signature.
    """
    if not credentials:
        logger.warning("auth_failed_no_token")
        raise HTTPException(status_code=401, detail="Missing Authentication Token")
    
    token = credentials.credentials
    try:
        # Decode without verification (for prototype)
        decoded = jwt.decode(token, options={"verify_signature": False})
        user_id = decoded.get("sub")
        if not user_id:
            raise ValueError("No 'sub' claim in token")
        return user_id
    except Exception as e:
        logger.error("auth_failed_invalid_token", error=str(e))
        raise HTTPException(status_code=401, detail="Invalid Authentication Token")
