# Firebase setup and the login check that protected API routes depend on

import os

import firebase_admin
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth, credentials
from google.auth.credentials import AnonymousCredentials

bearer = HTTPBearer(auto_error=False)

class NoKeyCredential(credentials.Base):
    """Placeholder so token checking works without a service account key.

    Verifying a login token only needs Google's public keys, but firebase-admin
    still asks for a credential when it starts. This hands it an empty one.
    It cannot be used for Firestore or other admin actions.
    """

    def get_credential(self):
        return AnonymousCredentials()

def init_firebase() -> None:
    """Start the Firebase Admin SDK once.

    With a key file: full admin access. Without one: token checking only,
    which needs just the project id. On Cloud Run the service identity is used.
    """
    try:
        firebase_admin.get_app()
    except ValueError:
        key = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if key:
            firebase_admin.initialize_app(credentials.Certificate(key))
        else:
            firebase_admin.initialize_app(
                NoKeyCredential(),
                options={"projectId": os.environ["FIREBASE_PROJECT_ID"]}
            )


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    """Verify the Firebase ID token and return its claims (uid, email, ...)."""
    if creds is None:
        raise HTTPException(status_code=401, detail="Missing authentication token")
    try:
        return auth.verify_id_token(creds.credentials)
    except auth.CertificateFetchError:
        raise HTTPException(
            status_code=503, detail="Could not reach Google to verify login"
        ) from None
    except (ValueError, auth.InvalidIdTokenError):
        # InvalidIdTokenError also covers expired and revoked tokens
        raise HTTPException(
            status_code=401, detail="Invalid or expired token"
        ) from None