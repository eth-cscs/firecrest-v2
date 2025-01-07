from typing import List
from jose import jwt, ExpiredSignatureError, JWTError, jwk
from fastapi import HTTPException, status
import requests
from requests.adapters import HTTPAdapter, Retry
from requests_file import FileAdapter


# models
from lib.auth.authN.authentication_service import AuthenticationService
from lib.models import ApiAuthModel


class OIDCTokenAuth(AuthenticationService):

    public_keys = {}

    def __init__(self, public_certs: List[str] = None):
        keys = []
        s = requests.Session()
        retries = Retry(total=6, backoff_factor=0.22)
        s.mount("http://", HTTPAdapter(max_retries=retries))
        s.mount("https://", HTTPAdapter(max_retries=retries))
        s.mount("file://", FileAdapter())

        for url in public_certs:
            try:
                cert = s.get(url, timeout=2)
                keys += cert.json()["keys"]
            except Exception:
                pass

        for key in keys:
            identifier = key.get("kid", None) or key.get("x5t", None)
            if identifier:
                self.public_keys[identifier] = jwk.construct(key)

    def auth_from_token(self, access_token: str):
        token_header = jwt.get_unverified_header(access_token)
        identifier = token_header.get("kid", None) or token_header.get("x5t", None)
        # Note: if kid not found throws KeyError catched by authenticate method
        public_key = self.public_keys[identifier]

        options = {"verify_signature": True, "verify_aud": False, "verify_exp": True}
        decoded_token = jwt.decode(token=access_token, key=public_key, options=options)
        return ApiAuthModel.build_from_oidc_decoded_token(decoded_token=decoded_token)

    async def authenticate(self, access_token: str):
        try:
            auth = self.auth_from_token(access_token)
            if not auth.is_active():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Inactive authentication",
                    headers={"auth-token": access_token},
                )
            return auth
        except ExpiredSignatureError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Access token expired",
                headers={"auth-token": access_token},
            ) from exc
        except JWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Access token is invalid.",
                headers={"auth-token": access_token},
            ) from exc
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token's public key not found.",
                headers={"auth-token": access_token},
            ) from exc
