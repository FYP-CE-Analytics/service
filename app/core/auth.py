from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import httpx
from typing import Optional, Dict
from pydantic import BaseModel
from dotenv import load_dotenv
import os
load_dotenv()
class AuthInfo(BaseModel):
    auth_id: str

JWKS_URL = os.getenv("JWKS_URL", "https://vital-joey-73.clerk.accounts.dev/.well-known/jwks.json") 
print("JWKS_URL", JWKS_URL)
print("CLERK_ISSUER_URL", os.getenv("CLERK_ISSUER_URL"))
class JWTBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super(JWTBearer, self).__init__(auto_error=auto_error)
        self.jwks_client = None

    async def get_jwks_client(self):
        if not self.jwks_client:
            async with httpx.AsyncClient() as client:
                response = await client.get(JWKS_URL)
                self.jwks_client = response.json()
        return self.jwks_client

    async def __call__(self, request: Request):
        credentials: HTTPAuthorizationCredentials = await super(JWTBearer, self).__call__(request)
        if credentials:
            if not credentials.scheme == "Bearer":
                raise HTTPException(status_code=403, detail="Invalid authentication scheme.")
            if not await self.verify_jwt(credentials.credentials):
                raise HTTPException(status_code=403, detail="Invalid token or expired token.")
            return credentials.credentials
        else:
            raise HTTPException(status_code=403, detail="Invalid authorization code.")

    async def verify_jwt(self, jwtoken: str) -> bool:
        try:
            # Get the JWKS
            jwks = await self.get_jwks_client()
            
            # Get the unverified header to find the key ID
            unverified_header = jwt.get_unverified_header(jwtoken)
            key_id = unverified_header.get('kid')
            
            # Find the key in JWKS
            key = None
            for k in jwks['keys']:
                if k['kid'] == key_id:
                    key = k
                    break
            
            if not key:
                print("key not found")
                return False

            # Verify the token
            payload = jwt.decode(
                jwtoken,
                key,
                algorithms=['RS256'],
                audience='vital-joey-73',
                issuer=os.getenv("CLERK_ISSUER_URL")
            )
            print("payload", payload)
            return True
        except JWTError as e:
            print("JWTError", e)
            return False

async def get_current_user(
    token: str = Depends(JWTBearer())
) -> AuthInfo:
    try:
        # Get the JWKS
        jwks_client = JWTBearer()
        jwks = await jwks_client.get_jwks_client()
        print("jwks", jwks)
        # Get the unverified header to find the key ID
        unverified_header = jwt.get_unverified_header(token)
        key_id = unverified_header.get('kid')
        print("key_id", key_id)
        # Find the key in JWKS
        key = None
        for k in jwks['keys']:
            if k['kid'] == key_id:
                key = k
                break
        
        if not key:
            raise HTTPException(status_code=403, detail="Invalid token key")

        # Verify and decode the token
        payload = jwt.decode(
            token,
            key,
            algorithms=['RS256'],
            audience='vital-joey-73',
            issuer='https://vital-joey-73.clerk.accounts.dev'
        )
        print("payload", payload)
        
        auth_id = payload.get('sub')
        
        if not auth_id:
            raise HTTPException(status_code=403, detail="Invalid token payload")
        
        return AuthInfo(auth_id=auth_id)
    except JWTError as e:
        raise HTTPException(status_code=403, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=403, detail=str(e))
