from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime, timedelta , timezone
from typing import Optional
from bson import ObjectId
from auth import router as auth_router, get_current_user 
import os


client = MongoClient(os.getenv('MONGO_URI'))
#print(os.getenv('MONGO_URI'))

if not os.getenv("MONGO_URI"):
    raise Exception("MONGO_URI not set")


db = client["pasteDB"]
pastes_collection = db["pastes"]
users_collection = db["users"]

collection.create_index(
    "expire_at",
    expireAfterSeconds=0
)


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

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


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
async def create_paste(paste: PasteCreate, user=Depends(get_current_user)):

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

    paste_doc = paste.dict()
    paste_doc.update({
        "user_email_key": email_key,
        "expire_at": expire_at
    })

    result = pastes_collection.insert_one(paste_doc)

    # push paste to user
    users_collection.update_one(
        {"email_key": email_key},
        {"$push": {"pastes": str(result.inserted_id)}}
    )

    return {
        "status": "success",
        "id": str(result.inserted_id)
    }


# ---------------- GET USER DASHBOARD ----------------
@app.get("/user/dashboard")
async def get_dashboard(user=Depends(get_current_user)):

    email_key = user["email"].replace(".", "_")

    db_user = users_collection.find_one({"email_key": email_key})

    if not db_user:
        raise HTTPException(404, "User not found")

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
            "name": db_user.get("name"),
            "email": db_user.get("email"),
            "picture": db_user.get("picture")
        },
        "pastes": pastes
    }



@app.get("/paste/{paste_id}")
async def get_paste(paste_id: str):

    try:

        paste = collection.find_one({
            "_id": ObjectId(paste_id)
        })

        if not paste:

            raise HTTPException(
                status_code=404,
                detail="Paste not found"
            )

        expire_at = paste.get("expire_at")

        if expire_at:

            current_time = datetime.now(timezone.utc)

            # Convert MongoDB datetime to UTC aware
            if expire_at.tzinfo is None:

                expire_at = expire_at.replace(
                    tzinfo=timezone.utc
                )

            if current_time > expire_at:

                raise HTTPException(
                    status_code=404,
                    detail="Paste expired"
                )

        return {

            "title": paste.get("title"),

            "content": paste.get("content"),

            "syntax": paste.get("syntax"),

            "expiration": paste.get("expiration"),
            "created_at": (
                paste.get("created_at")
                .astimezone(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
               ),
            "expire_at": (
                paste.get("expire_at")
                .astimezone(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
                if paste.get("expire_at")
                else None
            )
            }

    except HTTPException as e:

        raise e

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
