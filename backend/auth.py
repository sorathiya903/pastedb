from fastapi import APIRouter, Response, HTTPException, Request, Depends
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from google.oauth2 import id_token
from google.auth.transport import requests
from bson.objectid import ObjectId
from jose import jwt
from datetime import datetime, timedelta, timezone
import os

from pymongo import MongoClient

router = APIRouter()

client = MongoClient(os.getenv("MONGO_URI"))
db = client["pasteDB"]
users_collection = db["users"]
pastes_collection = db["pastes"]

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

    # save/update user
    users_collection.update_one(
        {"email_key": email_key},
        {
            "$set": {
                "email": email,
                "name": name,
                "picture": picture,
            },
            "$setOnInsert": {
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

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        email = payload.get("email")

        user = users_collection.find_one({
            "email": email
        })

        if not user:
            raise HTTPException(401, "User not found")

        return payload

    except:
        raise HTTPException(401, "Invalid token")

@router.post("/logout")
async def logout():

    response = JSONResponse({
        "message": "Logged out"
    })

    response.delete_cookie("session")

    return response


def get_optional_user(request: Request):

    token = request.cookies.get("session")

    if not token:
        return None

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        return payload

    except:
        return None


@router.delete("/delete-account")
async def delete_account(
    user = Depends(get_current_user)
):

    user_email = user.get("email")

    if not user_email:
        raise HTTPException(401, "Invalid token")

    # delete all pastes
    db.pastes.delete_many({
        "email": user_email
    })

    # delete user
    db.users.delete_one({
        "email": user_email
    })

    response = JSONResponse({
        "message": "Account deleted"
    })

    response.delete_cookie("session")

    return response



@router.get("/p/{paste_id}")
async def get_paste(
    paste_id: str,
    request: Request
):

    paste = None

    # SEARCH BY OBJECT ID
    if ObjectId.is_valid(paste_id):

        paste = pastes_collection.find_one({
            "_id": ObjectId(paste_id)
        })

    # SEARCH BY CUSTOM ID
    if not paste:

        paste = pastes_collection.find_one({
            "custom_id": paste_id
        })

    if not paste:
        raise HTTPException(
            404,
            "Paste not found"
        )

    # CHECK USER COOKIE
    token = request.cookies.get("session")

    current_email_key = None

    if token:

        try:

            payload = jwt.decode(
                token,
                SECRET_KEY,
                algorithms=[ALGORITHM]
            )

            email = payload.get("email")

            current_email_key = (
                email.replace(".", "_")
            )

        except:
            pass

    # PRIVATE CHECK
    if paste.get("visibility") == "private":

        owner_email_key = paste.get(
            "user_email_key"
        )

        if current_email_key != owner_email_key:

            raise HTTPException(
                404,
                "Paste not found"
            )

    # ANALYTICS UPDATE
    pastes_collection.update_one(
        {"_id": paste["_id"]},
        {
            "$inc": {
                "analytics.views": 1
            },

            "$push": {
                "analytics.visitors": {
                    "ip": request.client.host,

                    "timestamp":
                        datetime.utcnow().timestamp(),

                    "user_agent":
                        request.headers.get(
                            "user-agent"
                        )
                }
            },

            "$set": {
                "analytics.last_viewed":
                    datetime.utcnow().timestamp()
            }
        }
    )

    return {

        "title":
            paste.get("title"),

        "content":
            paste.get("content"),

        "syntax":
            paste.get("syntax"),

        "created_at":
            paste.get("created_at"),

        "expire_at":
            paste.get("expire_at"),

        "visibility":
            paste.get(
                "visibility",
                "public"
            ),
        "custom_id":paste.get("custom_id", "Not found"),
        
        "password":
            True if paste.get("password")
            else False
        }
