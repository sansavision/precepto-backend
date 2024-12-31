# common/token_utils.py
import os
import jwt
from typing import Dict, Any
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


if os.environ.get('PROD_MODE',"false") == 'false':
    # only in dev
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(os.path.pardir,".env"))
class TokenValidator:
    def __init__(self, secret_key: str = None, algorithm: str = 'HS256'):
        self.secret_key = secret_key or os.environ.get('JWT_SECRET')
        self.algorithm = algorithm

    async def validate_access_token(self, token: str) -> Dict[str, Any]:
        """
        Validates an access token and returns the decoded payload
        Raises jwt.InvalidTokenError if token is invalid
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            if payload.get('type') != 'access':
                raise jwt.InvalidTokenError('Invalid token type')

            if 'user' not in payload:
                raise jwt.InvalidTokenError('User information missing from token')

            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Access token has expired")
            raise
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            raise jwt.InvalidTokenError(f"Token validation failed: {str(e)}")