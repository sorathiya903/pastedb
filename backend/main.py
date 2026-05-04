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

pastes_collection.create_index(
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
async def create_paste(
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

        # IMPORTANT
        paste_doc = paste.model_dump()

        paste_doc.update({
            "user_email_key": email_key,
            "expire_at": expire_at
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
            "id": str(result.inserted_id)
        }

    except Exception as e:

        print("CREATE ERROR:", e)

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ---------------- GET USER DASHBOARD ----------------
@app.get("/user/dashboard")
async def get_dashboard(user=Depends(get_current_user)):

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

    paste = pastes_collection.find_one({"_id": ObjectId(paste_id)})

    if not paste:
        raise HTTPException(404, "Paste not found")

    expire_at = paste.get("expire_at")

    if expire_at and datetime.now(timezone.utc) > expire_at:
        raise HTTPException(404, "Paste expired")

    paste["_id"] = str(paste["_id"])
    return paste
