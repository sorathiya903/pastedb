from fastapi import FastAPI, HTTPException, Depends, Query, Cookie 
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime, timedelta , timezone
from typing import Optional
from bson.objectid import ObjectId
from auth import router as auth_router, get_current_user , get_optional_user 
import os
import re

import logging
logging.basicConfig(level=logging.DEBUG)
import traceback


from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ph = PasswordHasher()

client = MongoClient(os.getenv('MONGO_URI'))
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"


if not os.getenv("MONGO_URI"):
    raise Exception("MONGO_URI not set")


db = client["pasteDB"]
pastes_collection = db["pastes"]
users_collection = db["users"]

pastes_collection.create_index(
    "expire_at",
    expireAfterSeconds=0
)

pastes_collection.create_index([
    ("title", "text"),
    ("content", "text"),
    ("syntax", "text")
])





def hash_password(password: str):
    return ph.hash(password)

def verify_password(plain_password, hashed_password):
    try:
        return ph.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False

class PasswordCheck(BaseModel):
    password: str = Field(min_length=1, max_length=200)


class PasteCreate(BaseModel):

    title: str = Field(
        default="Untitled Paste",
        max_length=100
    )

    content: str

    syntax: str = Field(
        default="text"
    )

    expiration: str = Field(
        default="never"
    )

    custom_id: Optional[str] = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    password: Optional[str] = None
    visibility: str = "public"



app = FastAPI()
app.include_router(auth_router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://pastedb.netlify.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"message": "Server running"}


@app.post("/create")
def create_paste(
    paste: PasteCreate,
    user=Depends(get_current_user)
):

    try:

        email_key = user["email"].replace(".", "_")

        now = datetime.now(timezone.utc)

        expire_at = None

        if paste.expiration in ["10m", "10min"]:
            expire_at = now + timedelta(minutes=10)

        elif paste.expiration in ["1h", "1hour"]:
            expire_at = now + timedelta(hours=1)

        elif paste.expiration in ["1d", "1day"]:
            expire_at = now + timedelta(days=1)

        elif paste.expiration in ["1w", "1week"]:
            expire_at = now + timedelta(days=7)

        # CUSTOM ID VALIDATION
        custom_id = paste.custom_id

        if custom_id:

            custom_id = custom_id.lower().strip()

            if not re.match(r"^[a-z0-9-]+$", custom_id):
                raise HTTPException(
                    400,
                    "Invalid custom ID"
                )

            existing = pastes_collection.find_one({
                "custom_id": custom_id
            })

            if existing:
                raise HTTPException(
                    400,
                    "Custom ID already taken"
                )

        paste_doc = paste.model_dump()
        print("DEBUG PAYLOAD:", paste_doc)
        if paste_doc.get("password"):
            paste_doc["password"] = hash_password(paste_doc["password"])

        paste_doc.update({
            "user_email_key": email_key,
            "expire_at": expire_at,
            "custom_id": custom_id
        })
        result = pastes_collection.insert_one(
            paste_doc
        )

        users_collection.update_one(
            {"email_key": email_key},
            {
                "$push": {
                    "pastes": str(result.inserted_id)
                }
            }
        )

        return {
            "status": "success",
            "id": str(result.inserted_id),
            "custom_id": custom_id
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500,detail=str(e))
    
    

# ---------------- GET USER DASHBOARD ----------------
@app.get("/user/dashboard")
async def user_dash(user=Depends(get_current_user)):

    
    email_key = user.get("email", "").replace(".", "_")

    db_user = users_collection.find_one({"email_key": email_key})

    if not db_user:
        return {
            "user": {
                "name": user.get("name", "User"),
                "email": user.get("email", ""),
                "picture": user.get("picture", "")
            },
            "pastes": []
        }

    paste_ids = db_user.get("pastes", [])

    pastes = []

    for pid in paste_ids:
        try:
            p = pastes_collection.find_one({"_id": ObjectId(pid)})
            if p:
                p["_id"] = str(p["_id"])
                pastes.append(p)
        except:
            pass

    return {
        "user": {
            "name": db_user.get("name", "User"),
            "email": db_user.get("email", ""),
            "picture": db_user.get("picture", "")
        },
        "pastes": pastes
    }



@app.get("/paste/{paste_id}")
async def get_paste(paste_id: str):

    print("PASTE ID:", paste_id)

    try:

        paste = pastes_collection.find_one({
            "_id": ObjectId(paste_id)
        })

        if not paste:
            raise HTTPException(
                status_code=404,
                detail="Paste not found"
            )

        paste["_id"] = str(paste["_id"])

        return paste

    except Exception as e:

        print(e)

        raise HTTPException(
            status_code=400,
            detail="Invalid paste ID"
        )
# delete

@app.delete("/delete/{paste_id}")
async def delete_paste(
    paste_id: str,
    user=Depends(get_current_user)
):

    try:

        email_key = user["email"].replace(".", "_")

        paste = pastes_collection.find_one({
            "_id": ObjectId(paste_id)
        })

        if not paste:
            raise HTTPException(404, "Paste not found")

        # SECURITY CHECK
        if paste.get("user_email_key") != email_key:
            raise HTTPException(403, "Unauthorized")

        # DELETE FROM PASTES COLLECTION
        pastes_collection.delete_one({
            "_id": ObjectId(paste_id)
        })

        # REMOVE FROM USER DOCUMENT
        users_collection.update_one(
            {"email_key": email_key},
            {
                "$pull": {
                    "pastes": paste_id
                }
            }
        )

        return {
            "status": "success",
            "message": "Paste deleted"
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.put("/paste/{paste_id}")
def update_paste(paste_id: str, data: dict):

    now = datetime.now(timezone.utc)

    expiry = None
    expiration = data.get("expiration")

    if expiration in ["10m", "10min"]:
        expiry = now + timedelta(minutes=10)
    elif expiration in ["1h", "1hour"]:
        expiry = now + timedelta(hours=1)
    elif expiration in ["1d", "1day"]:
        expiry = now + timedelta(days=1)
    elif expiration in ["1w", "1week"]:
        expiry = now + timedelta(days=7)

    update_data = {
        "title": data.get("title"),
        "content": data.get("content"),
        "syntax": data.get("syntax"),
        "expiration": expiration,
        "expire_at": expiry
    }

    #  HANDLE PASSWORD IN EDIT
    if "password" in data:
        # new password entered
        if data.get('password'):
            hashed = hash_password(data.get('password'))
            update_data["password"] = hashed

# user disabled password
    
        elif data.get("remove_password"):
            update_data["password"] = None

        elif data["password"] is None or data["password"] == "":
            update_data["password"] = None
        else:
            update_data["password"] = hash_password(data["password"])

    result = pastes_collection.update_one(
        {"_id": ObjectId(paste_id)},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(404, "Paste not found")

    return {"status": "updated"}




@app.get("/search")
async def search_pastes(q: str = Query(...)):

    results = pastes_collection.find(
        {
            "$text": {
                "$search": q
            }
        },
        {
            "score": {
                "$meta": "textScore"
            }
        }
    ).sort([
        ("score", {"$meta": "textScore"})
    ]).limit(20)

    pastes = []

    for p in results:
        p["_id"] = str(p["_id"])
        pastes.append(p)

    return {
        "results": pastes
    }


@app.get("/suggest")
async def suggest(q: str):

    results = pastes_collection.find(
        {
            "$text": {
                "$search": q
            }
        }
    ).limit(5)

    suggestions = []

    for p in results:

        if p.get("title"):
            suggestions.append(p["title"])

    return {
        "suggestions": suggestions
    }


@app.get("/check-id")
async def check_custom_id(id: str):

    # basic validation
    if len(id) < 3:
        return {
            "available": False,
            "message": "Too short"
        }

    # check existing paste
    existing = pastes_collection.find_one({
        "custom_id": id
    })

    return {
        "available": existing is None
    }



@app.post("/p/{custom_id}/verify-password")
def verify_custom_password(custom_id: str, body: PasswordCheck):

    paste = pastes_collection.find_one({
        "custom_id": custom_id
    })

    if not paste:
        raise HTTPException(404, "Paste not found")

    stored_password = paste.get("password")

    if not stored_password:
        return {"access": True}

    if verify_password(body.password, stored_password):
        return {"access": True}

    return {"access": False}
