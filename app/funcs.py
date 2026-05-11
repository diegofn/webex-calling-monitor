import secrets
from app.config.config import c
from app.logger.logrr import lm
from datetime import datetime, timezone

def is_token_expired(token):
    """Check if the token is expired."""
    try:
        return datetime.now().timestamp() > token.get('expires_at', 0)  # Check if the token has expired
    except Exception as e:
        lm.lnp(f"Error checking token expiration: {e}", style="error", level="error")
        return True  # Assume the token is expired if an error occurs


def is_refresh_token_expired(token):
    """Check if the refresh token is expired."""
    try:
        refresh_token_lifespan = token.get('refresh_token_expires_in', 0)  # lifespan in seconds
        token_acquired_time = token.get('acquired_at', datetime.now().timestamp())  # Time when the token was saved
        refresh_token_expiry_time = token_acquired_time + refresh_token_lifespan    # Time when the token will expire
        return datetime.now().timestamp() > refresh_token_expiry_time   # Check if the token has expired
    except Exception as e:
        lm.lnp(f"Error checking refresh token expiration: {e}", style="error", level="error")
        return True  # Assume the refresh token is expired if an error occurs


def generate_session_token(token_len: int = 24):
    """Generate a random session token."""
    token: str = secrets.token_urlsafe(token_len)
    return token
