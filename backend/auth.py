from fastapi import APIRouter, Response, HTTPException, Request
from pydantic import BaseModel

from google.oauth2 import id_token
from google.auth.transport import requests

from jose import jwt
from datetime import datetime, timedelta, timezone
import os

from pymongo import MongoClient

router = APIRouter()

client = MongoClient(os.getenv("MONGO_URI"))
db = client["pasteDB"]
users_collection = db["users"]

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"


class GoogleLogin(BaseModel):
    token: str


# ---------------- GOOGLE LOGIN ----------------
@router.post("/auth/google")
async def google_auth(data: GoogleLogin, response: Response):

    user_data = id_token.verify_oauth2_token(
        data.token,
        requests.Request(),
        GOOGLE_CLIENT_ID
    )

    email = user_data["email"]
    name = user_data["name"]
    picture = user_data.get("picture")

    email_key = email.replace(".", "_")

    payload = {
        "email": email,
        "email_key": email_key,
        "name": name,
        "picture": picture,
        "exp": datetime.now(timezone.utc) + timedelta(days=7)
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    # save user in DB (auto-create)
    users_collection.update_one(
        {"email_key": email_key},
        {
            "$setOnInsert": {
                "email": email,
                "email_key": email_key,
                "name": name,
                "picture": picture,
                "pastes": [],
                "created_at": datetime.now(timezone.utc)
            }
        },
        upsert=True
    )

    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=60 * 60 * 24 * 7
    )

    return {"status": "success"}


# ---------------- AUTH DEPENDENCY ----------------
def get_current_user(request: Request):

    token = request.cookies.get("session")

    if not token:
        raise HTTPException(401, "Not authenticated")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except:
        raise HTTPException(401, "Invalid token")
