from fastapi import FastAPI, HTTPException, Depends, Query, Cookie, Request , status, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime, timedelta , timezone
from typing import Optional
from bson.objectid import ObjectId
from auth import (
    router as auth_router,
    get_current_user,
    get_optional_user,
    decode_token
)
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse 
import io
from coolname import generate_slug
import os
import re
from collections import Counter
import user_agents
import secrets
import logging
#ogging.basicConfig(level=logging.DEBUG)
import traceback
import requests
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import asyncio
import json
import time
import uuid
from math import radians, sin, cos, sqrt, atan2


ph = PasswordHasher()

client = MongoClient(os.getenv('MONGO_URI'))
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"


if not os.getenv("MONGO_URI"):
    raise Exception("MONGO_URI not set")


db = client["pasteDB"]
pastes_collection = db["pastes"]
users_collection = db["users"]
api_keys_collection = db["api_keys"]

pastes_collection.create_index(
    "expire_at",
    expireAfterSeconds=0
)

pastes_collection.create_index([
    ("title", "text"),
    ("content", "text"),
    ("syntax", "text")
])



def get_api_user(request: Request):

    api_key = request.headers.get(
        "x-api-key"
    )

    if not api_key:

        raise HTTPException(
            status_code=401,
            detail="API key required"
        )

    
    key_doc = api_keys_collection.find_one({
        "api_key": api_key
    })

    if not key_doc:

        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return {

        "email": key_doc.get("email"),

        "api_key": api_key,

        "created_at": key_doc.get(
            "created_at"
        )
    }

def hash_password(password: str):
    return ph.hash(password)

def verify_password(plain_password, hashed_password):
    try:
        return ph.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False

class PasswordCheck(BaseModel):
    password: str = Field(min_length=1, max_length=200)


class EncryptedField(BaseModel):
    iv: str
    data: str

class EncryptedImage(BaseModel):
    url: EncryptedField
    type: str


class PasteCreate(BaseModel):
    title: str | EncryptedField
    content: str | EncryptedField
    images: list[str | EncryptedField | EncryptedImage]
    encrypted_pek: Optional[EncryptedField] = None
    
    syntax: str = Field(
        default="text"
    )
    encrypted_pek: Optional[EncryptedField] = None
    guest: bool = False

    e2ee: bool = False

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
    "https://pastedb.netlify.app",
    "https://sorathiya903.github.io"
    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)




 
    


import httpx

SEARX_URL = "https://searx.be/search"

@app.get("/search")
async def search(
    q: str = Query(...)
):
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            general_task = client.get(
                SEARX_URL,
                params={
                    "q": q,
                    "format": "json"
                }
            )

            image_task = client.get(
                SEARX_URL,
                params={
                    "q": q,
                    "categories": "images",
                    "format": "json"
                }
            )

            pdf_task = client.get(
                SEARX_URL,
                params={
                    "q": q + " filetype:pdf",
                    "format": "json"
                }
            )

            general_res = await general_task
            image_res = await image_task
            pdf_res = await pdf_task

        general = general_res.json().get("results", [])
        images = image_res.json().get("results", [])
        pdfs = pdf_res.json().get("results", [])

        pdf_results = []

        for r in pdfs:
            url = r.get("url", "")

            if ".pdf" in url.lower():
                pdf_results.append({
                    "title": r.get("title"),
                    "url": url,
                    "content": r.get("content")
                })

        return JSONResponse({
            "web": general,
            "images": images,
            "pdfs": pdf_results
        })

    except Exception as e:
        return JSONResponse(
            {
                "error": str(e)
            },
            status_code=500
        )
        


@app.get("/images/{paste_id}")
async def get_images(paste_id: str):

    paste = None

    # Search by MongoDB ObjectId
    if ObjectId.is_valid(paste_id):
        paste = pastes_collection.find_one({
            "_id": ObjectId(paste_id)
        })

    # Search by custom ID
    if not paste:
        paste = pastes_collection.find_one({
            "custom_id": paste_id
        })

    # Not found
    if not paste:
        raise HTTPException(
            status_code=404,
            detail="Paste not found"
        )

    return {
    "e2ee": paste.get("e2ee", False),
    "encrypted_pek": paste.get("encrypted_pek"),
    "images": paste.get("images", [])}


        
        
@app.api_route("/health", methods=["GET", "HEAD"])
async def health(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"

    return {
        "status": "ok",
        "service": "PasteDB",
        "timestamp": int(time.time())
    }



@app.post("/copy/{paste_id}")
async def copy_paste(paste_id: str):

    paste = None

    # Search by MongoDB ObjectId
    if ObjectId.is_valid(paste_id):
        paste = pastes_collection.find_one({
            "_id": ObjectId(paste_id)
        })

    # Search by custom ID
    if not paste:
        paste = pastes_collection.find_one({
            "custom_id": paste_id
        })

    # Not found
    if not paste:
        raise HTTPException(
            status_code=404,
            detail="Paste not found"
        )

    # Increment copy count
    pastes_collection.update_one(
        {"_id": paste["_id"]},
        {
            "$inc": {
                "analytics.copies": 1
            }
        }
    )

    return {
        "success": True,
        "copies": paste.get("analytics", {}).get("copies", 0) + 1
    }










receivers = {}

MAX_RECEIVERS = 5
TIMEOUT = 10


def distance(lat1, lon1, lat2, lon2):
    R = 6371000

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat/2)**2 +
        cos(radians(lat1)) *
        cos(radians(lat2)) *
        sin(dlon/2)**2
    )

    return R * 2 * atan2(sqrt(a), sqrt(1-a))


def device_name(ua: str):
    ua = ua.lower()

    phone = "Desktop"

    if "iphone" in ua:
        phone = "iPhone"
    elif "ipad" in ua:
        phone = "iPad"
    elif "android" in ua:
        phone = "Android"

    browser = "Browser"

    if "edg" in ua:
        browser = "Edge"
    elif "chrome" in ua and "edg" not in ua:
        browser = "Chrome"
    elif "firefox" in ua:
        browser = "Firefox"
    elif "safari" in ua and "chrome" not in ua:
        browser = "Safari"

    return f"{browser} on {phone}"


async def cleaner():
    while True:

        now = time.time()

        remove = []

        for rid, info in receivers.items():
            if now - info["joined"] > TIMEOUT:
                try:
                    await info["ws"].close()
                except:
                    pass

                remove.append(rid)

        for rid in remove:
            receivers.pop(rid, None)

        await asyncio.sleep(1)


@app.on_event("startup")
async def startup():
    asyncio.create_task(cleaner())


@app.websocket("/ws/nearby")
async def nearby(ws: WebSocket):

    await ws.accept()

    my_id = None

    try:

        while True:

            msg = json.loads(await ws.receive_text())
            print(msg)

            action = msg["action"]

            if action == "register":

                if len(receivers) >= MAX_RECEIVERS:

                    await ws.send_text(json.dumps({
                        "type": "full"
                    }))

                    continue

                my_id = str(uuid.uuid4())

                receivers[my_id] = {
                    "ws": ws,
                    "joined": time.time(),
                    "lat": msg.get("lat"),
                    "lon": msg.get("lon"),
                    "device": device_name(
                        ws.headers.get("user-agent", "")
                    )
                }
                print(receivers[my_id])

                await ws.send_text(json.dumps({
                    "type": "registered"
                }))

            elif action == "find":
                print("action find called ")
                
                sender_lat = msg.get("lat")
                sender_lon = msg.get("lon")

                found = []
                
                print(receivers.items())
                
                for rid, info in receivers.items():

                    if sender_lat is not None and info["lat"] is not None:

                        d = distance(
                            sender_lat,
                            sender_lon,
                            info["lat"],
                            info["lon"]
                        )
                        print('dist :',d)

                        if d <= 110:
                            found.append({
                                "id": rid,
                                "name": info["device"],
                                "distance": round(d)
                            })
                            print(found)

                    else:

                        found.append({
                            "id": rid,
                            "name": info["device"]
                        })
                        print(found)

                await ws.send_text(json.dumps({
                    "type": "devices",
                    "devices": found
                }))

            elif action == "send":

                rid = msg["receiver"]

                url = msg["url"]

                if rid in receivers:

                    rws = receivers[rid]["ws"]

                    await rws.send_text(json.dumps({
                        "type": "incoming",
                        "url": url
                    }))

                    try:
                        await rws.close()
                    except:
                        pass

                    receivers.pop(rid, None)

                    await ws.send_text(json.dumps({
                        "type": "sent"
                    }))

    except WebSocketDisconnect:
        print("WebSocket disconnected")

        if my_id:
            receivers.pop(my_id, None)

    except Exception as e:
        print(e)
        import traceback

        traceback.print_exc()

        if my_id:
            receivers.pop(my_id, None)

        try:
            await ws.close()
        except:
            pass

@app.post("/fork/{paste_id}")
async def fork_paste(
    paste_id: str,
    user=Depends(get_current_user)
):

    original = None

    # =========================
    # TRY MONGO OBJECT ID
    # =========================
    if ObjectId.is_valid(paste_id):

        original = pastes_collection.find_one({
            "_id": ObjectId(paste_id)
        })

    # =========================
    # TRY CUSTOM ID
    # =========================
    if not original:

        original = pastes_collection.find_one({
            "custom_id": paste_id
        })

    # =========================
    # NOT FOUND
    # =========================
    if not original:

        raise HTTPException(
            status_code=404,
            detail="Paste not found"
        )

    # =========================
    # PRIVATE CHECK
    # =========================
    if original.get("visibility") == "private":

        raise HTTPException(
            status_code=403,
            detail="Cannot fork private paste"
        )

    # =========================
    # PASSWORD CHECK
    # =========================
    if original.get("password"):

        raise HTTPException(
            status_code=403,
            detail="Cannot fork password protected paste"
        )

    # =========================
    # GET CURRENT USER
    # =========================
    db_user = users_collection.find_one({
        "email": user["email"]
    })

    if not db_user:

        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    # =========================
    # CREATE FORK DATA
    # =========================
    fork_data = {

        "title":
            f"Fork of {original.get('title', 'Untitled')}",

        "content":
            original.get("content", ""),

        "syntax":
            original.get("syntax", "text"),

        "expiration":
            "never",

        "visibility":
            "public",

        "forked_from":
            str(original["_id"]),

        "is_fork":
            True
    }

    # =========================
    # OPTIONAL:
    # Increase fork count
    # =========================
    pastes_collection.update_one(
        {"_id": original["_id"]},
        {
            "$inc": {
                "analytics.forks": 1
            }
        }
    )

    # =========================
    # CREATE NEW PASTE
    # =========================
    return await create_paste_logic(
        fork_data,
        db_user
    )

async def create_paste_logic(
    paste_data: dict,
    user_data: dict
):
    print(paste_data)

    email_key = user_data["email"].replace(".", "_")

    now = datetime.now(timezone.utc)

    expire_at = None

    expiration = paste_data.get("expiration", "never")
    burn_after_read = False

    if expiration == "burn":
        burn_after_read = True

    
    if expiration in ["10m", "10min"]:
        expire_at = now + timedelta(minutes=10)

    elif expiration in ["1h", "1hour"]:
        expire_at = now + timedelta(hours=1)

    elif expiration in ["1d", "1day"]:
        expire_at = now + timedelta(days=1)

    elif expiration == "30m":
        expire_at = now + timedelta(minutes=30)

    elif expiration == "6h":
        expire_at = now + timedelta(hours=6)

    elif expiration == "12h":
        expire_at = now + timedelta(hours=12)

    elif expiration == "3d":
        expire_at = now + timedelta(days=3)

    elif expiration == "30d":
        expire_at = now + timedelta(days=30)

    elif expiration in ["1w", "1week"]:
        expire_at = now + timedelta(days=7)

    # CUSTOM ID
    custom_id = paste_data.get("custom_id")

    if custom_id:

        custom_id =  custom_id.lower().strip()

        if not re.match(
            r"^[a-z0-9-]+$",
            custom_id
        ):

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

    if paste_data.get("e2ee"):
        if (
            not paste_data.get("guest", False)
            and not paste_data.get("encrypted_pek")    ):
            raise HTTPException(
                status_code=400,
                detail="encrypted_pek required for account E2EE pastes"
            )

    # PASSWORD HASH
    if paste_data.get("password"):

        paste_data["password"] = hash_password( paste_data["password"])

    # FINAL DOC
    paste_data.update({
        "forked_from": paste_data.get("forked_from"),
        
        "is_fork": paste_data.get("is_fork", False),

        "user_email_key": email_key,

        "expire_at": expire_at,

        "custom_id": custom_id,

        "e2ee": paste_data.get("e2ee", False),

        "encrypted_pek": paste_data.get("encrypted_pek"),
        "owner": user_data.get("name"),

        "picture":  user_data.get("picture"),
        
        "burn_after_read": burn_after_read,

        "created_at":now.timestamp(),
        "images": paste_data.get("images", []),

        "updated_at": now.timestamp(),

        "analytics": {

            "views": 0,

            "copies": 0,

            "shares": 0,

            "failed_passwords": 0,

            "last_viewed": None,

            "total_read_time": 0,

            "scroll_completion": 0,

            "impressions": 0,

            "forks": 0,

            "visitors": [],

            "activities": [],

            "daily_views": {}

        }

    })

    # INSERT
    result =  pastes_collection.insert_one(  paste_data    )

    
    
    if not custom_id or not custom_id.strip():
        custom_id = str(result.inserted_id)

        pastes_collection.update_one(
            {"_id": result.inserted_id},
             {
                "$set": {
                    "custom_id": custom_id
                }
             }
        )
    

    # UPDATE USER
    users_collection.update_one(
        {"email_key": email_key},
        {
            "$push": {
                "pastes":
                    str(result.inserted_id)
            }
        }
    )

    return {

        "status": "success",

        "id": str(result.inserted_id),

        "custom_id":  custom_id

    }

@app.post("/create")
async def create_paste(
    paste: PasteCreate,
    user=Depends(get_optional_user)
):

    # logged in user
    if user:

        db_user = users_collection.find_one({
            "email": user["email"]
        })

        # token valid but account deleted
        if not db_user:
            raise HTTPException(
                status_code=401,
                detail="User no longer exists"
            )

    # guest user
    else:

        db_user = {
            "email": "guest@pastedb.com",
            "name": "Guest",
            "picture": ""
        }

    return await create_paste_logic(
        paste.model_dump(),
        db_user
    )
    

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

    

    paste_ids = [
    ObjectId(pid)
    for pid in db_user.get("pastes", [])
    if ObjectId.is_valid(pid)]
    
    pastes = list(
    pastes_collection.find(
        {"_id": {"$in": paste_ids}}    ))

    for p in pastes:
        p["_id"] = str(p["_id"])

    return {
        "user": {
            "name": db_user.get("name", "User"),
            "email": db_user.get("email", ""),
            "picture": db_user.get("picture", "")
        },
        "pastes": pastes
    }




@app.get("/p/{paste_id}")
async def get_paste(
    paste_id: str,
    request: Request
):

    try:

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

        # NOT FOUND
        if not paste:

            raise HTTPException(
                status_code=404,
                detail="Paste not found"
            )

        # PRIVATE CHECK
        if paste.get("visibility") == "private":

            token = request.cookies.get("session")

            if not token:

                raise HTTPException(
                    status_code=404,
                    detail="Paste not found"
                )

            payload = decode_token(token)

            if not payload:

                raise HTTPException(
                    status_code=401,
                    detail="Invalid token"
                )

            current_email_key = (
                payload["email"]
                .replace(".", "_")
            )

            if (
                current_email_key !=
                paste.get("user_email_key")
            ):

                raise HTTPException(
                    status_code=404,
                    detail="Paste not found"
                )

        # ANALYTICS UPDATE
        now = datetime.now(
            timezone.utc
        ).timestamp()

        visitor_data = {

            "ip": request.client.host,

            "timestamp": now,

            "user_agent": request.headers.get(
                "user-agent",
                "Unknown"
            )
        }

        pastes_collection.update_one(

            {"_id": paste["_id"]},

            {
                "$inc": {
                    "analytics.views": 1
                },

                "$push": {
                    "analytics.visitors":
                        visitor_data
                },

                "$set": {
                    "analytics.last_viewed":
                        now
                }
            }
        )

        # SAFE SERIALIZATION
        paste["_id"] = str(
            paste["_id"]
        )
        paste.pop("password", None)
        
        if paste.get("burn_after_read"):
            pastes_collection.delete_one({"_id": paste["_id"] })
            users_collection.update_one( {      "email_key": paste["user_email_key"]  },   {  "$pull": {  "pastes": str(paste["_id"])      }   }        )

        return paste

    except HTTPException:

        raise

    except Exception as e:

        print("GET PASTE ERROR:")
        print(traceback.format_exc())

        raise HTTPException(
            status_code=500,
            detail="Internal server error"
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
def update_paste(paste_id: str, data: dict, user=Depends(get_current_user)):
    paste = pastes_collection.find_one({ "_id": ObjectId(paste_id)})
    if not paste:
        raise HTTPException(404, "Paste not found")
        
    email_key = user["email"].replace(".", "_")
    
    if paste.get("user_email_key") != email_key:
        raise HTTPException(403, "Unauthorized")

    now = datetime.now(timezone.utc)

    expire_at= None
    expiration = data.get("expiration")
    burn_after_read = expiration == "burn"

    if expiration in ["10m", "10min"]:
        expire_at = now + timedelta(minutes=10)

    elif expiration in ["1h", "1hour"]:
        expire_at = now + timedelta(hours=1)

    elif expiration in ["1d", "1day"]:
        expire_at = now + timedelta(days=1)

    elif expiration == "30m":
        expire_at = now + timedelta(minutes=30)

    elif expiration == "6h":
        expire_at = now + timedelta(hours=6)

    elif expiration == "12h":
        expire_at = now + timedelta(hours=12)

    elif expiration == "3d":
        expire_at = now + timedelta(days=3)

    elif expiration == "30d":
        expire_at = now + timedelta(days=30)

    elif expiration in ["1w", "1week"]:
        expire_at = now + timedelta(days=7)
        
    update_data = {
        "title": data.get("title"),
        "content": data.get("content"),
        "syntax": data.get("syntax"),
        "expiration": expiration,
        "expire_at": expire_at,
        "burn_after_read": burn_after_read,
        "visibility":data.get("visibility"),
        "e2ee": data.get("e2ee", False)
    }
    if "images" in data:
        update_data["images"] = data["images"]
    
    # Handle encrypted PEK
    # Handle encrypted PEKs
    if update_data["e2ee"]:

        if not data.get("encrypted_pek"):
            raise HTTPException(
                400,
                "encrypted_pek required"
            )  

        update_data["encrypted_pek"] = data.get(
            "encrypted_pek"
        )

    else:
        update_data["encrypted_pek"] = None

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

    return {"status": "updated",
           "custom_id":paste.get("custom_id")
           }




@app.get("/search")
async def search_pastes(

    q: str = "",

    syntax: str = None,

    visibility: str = "public",

    owner: str = None,

    has_password: bool = None,

    created_after: float = None,

    created_before: float = None,

    min_views: int = None,

    max_views: int = None,

    sort_by: str = "relevance"
):
    if visibility != "public":
        raise HTTPException( 403,  "Only public search allowed" )

    filters = []

    # TEXT SEARCH
    if q:

        filters.append({
            "$text": {
                "$search": q
            }
        })

    # VISIBILITY
    if visibility:

        filters.append({
            "visibility": visibility
        })

    # LANGUAGE / SYNTAX
    if syntax:

        filters.append({
            "syntax": syntax
        })

    # OWNER
    if owner:

        filters.append({
            "owner": {
                "$regex": owner,
                "$options": "i"
            }
        })

    # PASSWORD FILTER
    if has_password is True:

        filters.append({
            "password": {
                "$ne": None
            }
        })

    elif has_password is False:

        filters.append({
            "$or": [
                {"password": None},
                {"password": {"$exists": False}}
            ]
        })

    # DATE RANGE
    if created_after or created_before:

        date_filter = {}

        if created_after:
            date_filter["$gte"] = created_after

        if created_before:
            date_filter["$lte"] = created_before

        filters.append({
            "created_at": date_filter
        })

    # VIEWS RANGE
    if min_views or max_views:

        views_filter = {}

        if min_views is not None:
            views_filter["$gte"] = min_views

        if max_views is not None:
            views_filter["$lte"] = max_views

        filters.append({
            "analytics.views": views_filter
        })

    # FINAL QUERY
    mongo_query = {}

    if filters:
        mongo_query = {
            "$and": filters
        }

    # SORTING
    sort_stage = None

    if sort_by == "views":

        sort_stage = [("analytics.views", -1)]

    elif sort_by == "latest":

        sort_stage = [("created_at", -1)]

    elif sort_by == "oldest":

        sort_stage = [("created_at", 1)]

    else:
        # relevance
        sort_stage = [
            ("score", {"$meta": "textScore"})
        ] if q else [("created_at", -1)]

    # QUERY
    cursor = pastes_collection.find(
        mongo_query,
        {
            "score": {
                "$meta": "textScore"
            }
        }
    )

    cursor = cursor.sort(sort_stage).limit(50)

    results = []

    for paste in cursor:
        paste["_id"] = str(paste["_id"])
        paste.pop("password", None)
        results.append(paste)

    return {
        "count": len(results),
        "results": results
            }

@app.get("/suggest")
async def suggest(q: str ):

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
def verify_custom_password(
    custom_id: str,
    body: PasswordCheck
):

    paste = pastes_collection.find_one({
        "custom_id": custom_id
    })

    if not paste:
        raise HTTPException(404, "Paste not found")

    stored_password = paste.get("password")

    # no password
    if not stored_password:
        return {"access": True}

    # correct password
    if verify_password(
        body.password,
        stored_password
    ):
        return {"access": True}

    # WRONG PASSWORD
    pastes_collection.update_one(
        {"_id": paste["_id"]},
        {
            "$inc": {
                "analytics.failed_passwords": 1
            }
        }
    )

    return {"access": False}
    

@app.get("/stats/{paste_id}")
def paste_stats(
    paste_id: str,
    request: Request, 
    user=Depends(get_current_user)
):

    paste = pastes_collection.find_one({
        "_id": ObjectId(paste_id)
    })

    if not paste:
        raise HTTPException(
            status_code=404,
            detail="Paste not found"
        )

    email_key = user["email"].replace(".", "_")
    if paste.get("user_email_key") != email_key:
        raise HTTPException( 403,  "Unauthorized")

    
    content = paste.get("content", "")

    analytics = paste.get("analytics", {})

    visitors =analytics.get("visitors", [])

    views =  analytics.get("views", 0)

    copies = analytics.get("copies", 0)

    shares = analytics.get("shares", 0)

    failed_passwords = analytics.get("failed_passwords", 0)

    # UNIQUE VISITORS

    unique_ips = set()

    for v in visitors:
        ip = v.get("ip")

        if ip:
            unique_ips.add(ip)

    unique_visitors = len(unique_ips)
    countries = []
    for v in visitors:
        country = v.get("country")

    # ignore invalid countries
        if (
            country and
            isinstance(country, str) and
            country.strip() and
            country.lower() != "unknown"
        ):
            countries.append(country.strip())
            
    top_country = "Unknown"

    if countries:

        top_country = Counter(
            countries
        ).most_common(1)[0][0]

    # DEVICE TYPES

    mobile = 0
    desktop = 0
    tablet = 0

    browsers = []
    operating_systems = []

    for v in visitors:

        ua_string =v.get("user_agent", "")

        ua = user_agents.parse(ua_string)

        if ua.is_mobile:
            mobile += 1

        elif ua.is_tablet:
            tablet += 1

        else:
            desktop += 1

        browsers.append(
            ua.browser.family
        )

        operating_systems.append(
            ua.os.family
        )

    total_devices = max(
        mobile + desktop + tablet,
        1
    )

    mobile_percent = round(
        (mobile / total_devices) * 100
    )

    desktop_percent = round(
        (desktop / total_devices) * 100
    )

    tablet_percent = round(
        (tablet / total_devices) * 100
    )

    # TOP BROWSER

    top_browser = "Unknown"

    if browsers:
        top_browser = Counter(
            browsers
        ).most_common(1)[0][0]

    # TOP OS

    top_os = "Unknown"

    if operating_systems:
        top_os = Counter(
            operating_systems
        ).most_common(1)[0][0]

    # TIME ANALYTICS

    now = datetime.utcnow()

    views_today = 0
    views_week = 0
    views_month = 0

    hours = []

    for v in visitors:

        ts = v.get("timestamp")

        if not ts:
            continue

        diff =now.timestamp() - ts

        hours.append(
            datetime.fromtimestamp(ts).hour
        )

        if diff <= 86400:
            views_today += 1

        if diff <= 604800:
            views_week += 1

        if diff <= 2592000:
            views_month += 1

    # PEAK HOUR

    peak_hour = "N/A"

    if hours:

        peak = Counter(hours).most_common(1)[0][0]

        peak_hour = f"{peak}:00"

    # AVG READ TIME

    total_read_time = analytics.get("total_read_time", 0)

    avg_read_seconds = 0

    if views > 0:
        avg_read_seconds =int(total_read_time / views)

    minutes =avg_read_seconds // 60

    seconds = avg_read_seconds % 60

    read_time = f"{minutes}m {seconds}s"

    # SCROLL COMPLETION

    scroll_completion =analytics.get("scroll_completion", 0 )

    # OPEN RATE

    open_rate = 0

    if analytics.get("impressions", 0) > 0:

        open_rate = round(
            (
                views /
                analytics.get("impressions")
            ) * 100
        )

    # TRENDING SCORE

    trending_score = min(
        100,
        (
            views_today * 2 +
            shares * 4 +
            copies * 3
        )
    )

    # LIVE VIEWERS

    live_ips = set()
    for v in visitors:
        ts = v.get("timestamp", 0)
        if now.timestamp() - ts < 300:
            ip = v.get("ip")

            if ip:
                live_ips.add(ip)

    live_viewers = len(live_ips)

    
    daily_views ={}
    for v in visitors:
        ts = v.get("timestamp")
        if not ts:
            continue

        date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        daily_views[date] = (daily_views.get(date, 0) + 1)


    return {

        "title":
            paste.get("title", "Untitled"),

        "views":
            views,

        "unique_visitors":
            unique_visitors,

        "copies":
            copies,

        "shares":
            shares,

        "trending_score":
            trending_score,

        "live_viewers":
            live_viewers,

        "top_country":
            top_country,

        "mobile":
            f"{mobile_percent}%",

        "desktop":
            f"{desktop_percent}%",

        "tablet":
            f"{tablet_percent}%",

        "browser":
            top_browser,

        "os":
            top_os,

        "views_today":
            views_today,

        "views_week":
            views_week,

        "views_month":
            views_month,

        "peak_hour":
            peak_hour,

        "read_time":
            read_time,

        "scroll_completion":
            scroll_completion,

        "open_rate":
            open_rate,

        "password_protected":
            "Yes" if paste.get("password")
            else "No",

        "failed_passwords":
            failed_passwords,

        "visibility":
            paste.get(
                "visibility",
                "public"
            ),

        "size_kb":
            round(
                len(content.encode()) / 1024,
                2
            ),
        "daily_views": daily_views,

        "characters":
            len(content),

        "lines":
            len(content.splitlines()),

        "syntax":
            paste.get(
                "syntax",
                "plain"
            ),

        "created_at":
            paste.get("created_at"),

        "updated_at":
            paste.get("updated_at"),

        "last_viewed":
            analytics.get("last_viewed"),
        "activity_timestamps": [
            v.get("timestamp")
            for v in visitors
            if v.get("timestamp")],
    }


@app.get("/explore")
def explore_pastes():

    pastes = list(
        pastes_collection.find({
            "visibility": "public"
        })
    )

    results = []

    for paste in pastes:

        analytics = paste.get(
            "analytics",
            {}
        )

        results.append({

            "id":
                str(paste["_id"]),
            
            "custom_id":str(paste["custom_id"]),
            "title":
                paste.get(
                    "title",
                    "Untitled"
                ),

            "content":
                paste.get(
                    "content",
                    ""
                )[:240],

            "syntax":
                paste.get(
                    "syntax",
                    "plain"
                ),

            "stars":
                paste.get(
                    "stars",
                    0
                ),

            "views":
                analytics.get(
                    "views",
                    0
                ),

            "copies":
                analytics.get(
                    "copies",
                    0
                ),

            "shares":
                analytics.get(
                    "shares",
                    0
                ),

            "owner_name":
                paste.get(
                    "owner",
                    "Unknown"
                ),

            "owner_picture":
                paste.get(
                    "picture",
                    "https://share.google/IYg1IdYoqMPJgJ0Hj"
                ),

            "created_at":
                paste.get(
                    "created_at"
                )
        })

    results.sort(
        key=lambda x: (
            x["stars"] * 5 +
            x["views"] * 1 +
            x["shares"] * 3
        ),
        reverse=True
    )

    return results[:50]





class RunCode(BaseModel):
    language: str
    code: str


LANGUAGE_IDS = {
    "python": 109,        # Python 3.13.2
    "javascript": 102,    # Node.js 22.08.0
    "typescript": 101,    # TypeScript 5.6.2
    "java": 91,           # Java 17
    "c": 103,             # GCC 14.1.0
    "cpp": 105,           # C++ GCC 14.1.0
    "csharp": 51,         # C#
    "php": 98,            # PHP 8.3.11
    "go": 107,            # Go 1.23.5
    "rust": 108,          # Rust 1.85.0
    "ruby": 72,           # Ruby
    "swift": 83,          # Swift
    "kotlin": 111,        # Kotlin 2.1.10
    "dart": 90,           # Dart
    "lua": 64,            # Lua
    "r": 99,              # R 4.4.1
    "perl": 85,           # Perl
    "bash": 46,           # Bash
    "sql": 82,            # SQLite
    "scala": 112,         # Scala 3.4.2
    "haskell": 61,        # Haskell
    "pascal": 67,         # Pascal
    "fortran": 59,        # Fortran
    "clojure": 86,        # Clojure
    "elixir": 57,         # Elixir
    "erlang": 58,         # Erlang
    "fsharp": 87,         # F#
    "groovy": 88,         # Groovy
    "lisp": 55,           # Common Lisp
    "ocaml": 65,          # OCaml
    "objectivec": 79,     # Objective-C
    "prolog": 69,         # Prolog
    "vb": 84,             # Visual Basic
    "assembly": 45,       # NASM
    "cobol": 77           # COBOL
}



@app.post("/run")
async def run_code(data: RunCode):

    language = data.language.lower()

    if language not in LANGUAGE_IDS:
        return {
            "success": False,
            "error": f"Language '{language}' is not supported."
        }

    try:
        response = requests.post(
            "https://ce.judge0.com/submissions?base64_encoded=false&wait=true",
            json={
                "source_code": data.code,
                "language_id": LANGUAGE_IDS[language]
            },
            timeout=30
        )

        result = response.json()

        output = (
            result.get("stdout")
            or result.get("stderr")
            or result.get("compile_output")
            or result.get("message")
            or "No output"
        )

        return {
            "success": True,
            "language": language,
            "output": output,
            "status": result.get("status", {}).get("description"),
            "execution_time": result.get("time"),
            "memory": result.get("memory")
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
    




@app.post("/star/{paste_id}")
async def toggle_star(

    paste_id: str,

    user=Depends(get_current_user)

):

    email = user["email"]

    paste = pastes_collection.find_one({
        "_id": ObjectId(paste_id)
    })
    if not user:
        raise HTTPException(   401, "Login required"  )

    if not paste:
        raise HTTPException(404)

    starred_by = paste.get(
        "starred_by",
        []
    )

    if email in starred_by:

        pastes_collection.update_one(
            {"_id": ObjectId(paste_id)},
            {
                "$pull": {
                    "starred_by": email
                },
                "$inc": {
                    "stars": -1
                }
            }
        )

        return {
            "starred": False,
            "stars": max(
                paste.get("stars", 1) - 1,
                0
            )
        }

    else:

        pastes_collection.update_one(
            {"_id": ObjectId(paste_id)},
            {
                "$push": {
                    "starred_by": email
                },
                "$inc": {
                    "stars": 1
                }
            }
        )

        return {
            "starred": True,
            "stars": paste.get("stars", 0) + 1
        }
        
# =========================
# API KEYS SECTION
# =========================

def mask_api_key(key: str):
    if len(key) <= 16:
        return key

    return f"{key[:8]}*****...*****{key[-4:]}"

class ApiKeyRequest(BaseModel):
    name: str


@app.post("/generate-api-key")
async def generate_api_key(
    data: ApiKeyRequest,
    user=Depends(get_current_user)
):
    email = user.get("email")

    if not email:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized"
        )

    # pdb_ prefix
    api_key = "pdb_" + secrets.token_hex(32)

    api_keys_collection.insert_one({
        "email": email,
        "name": data.name.strip(),
        "api_key": api_key,
        "created_at": datetime.now(timezone.utc)
    })

    return {
        "status": "success",
        "api_key": api_key,
        "name": data.name
    }



@app.get("/my-api-keys")
async def my_api_keys(
    user=Depends(get_current_user)
):
    email = user.get("email")

    keys = list(
        api_keys_collection.find(
            {"email": email},
            {"_id": 0}
        )
    )

    result = []

    for item in keys:
        result.append({
            "name": item.get("name", "Untitled Key"),
            "api_key": mask_api_key(
                item["api_key"]
            ),
            "full_api_key": item["api_key"],
            "created_at": item["created_at"]
        })

    return {
        "keys": result
    }



@app.delete("/delete-api-key/{api_key}")
async def delete_api_key(
    api_key: str,
    user=Depends(get_current_user)
):

    email = user.get("email")

    result = api_keys_collection.delete_one({
        "email": email,
        "api_key": api_key
    })

    if result.deleted_count == 0:

        raise HTTPException(
            status_code=404,
            detail="API key not found"
        )

    return {
        "status": "success",
        "message": "API key deleted"
    }


# ========================
# API CREATE PASTE
# =========================

@app.post("/api/create")
async def api_create_paste(
    request: Request
):

    # Get API key
    api_key = request.headers.get(
        "x-api-key"
    )

    if not api_key:

        raise HTTPException(
            status_code=401,
            detail="API key required"
        )

    # Find API key
    key_doc = api_keys_collection.find_one({
        "api_key": api_key
    })

    if not key_doc:

        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    # Get JSON body
    data = await request.json()

    # Validate using Pydantic
    try:

        validated = PasteCreate(
            **data
        ).model_dump()

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    # Fake authenticated user
    fake_user = {

        "email":
            key_doc["email"],

        "name":
            key_doc.get(
                "name",
                "API User"
            ),

        "picture":
            key_doc.get(
                "picture",
                ""
            )
    }

    # Create paste
    return await create_paste_logic(
        validated,
        fake_user
    )


# =========================
# API CURRENT USER
# =========================

@app.get("/api/me")
async def api_me(

    api_user=Depends(
        get_api_user
    )

):

    return {

        "email":
            api_user["email"],

        "created_at":
            api_user["created_at"]
    }


# =========================
# API GET PASTE
# =========================

@app.get("/api/paste/{paste_id}")
async def api_get_paste(
    paste_id: str,
    api_user=Depends(get_api_user)
):

    paste = None

    # Search by ObjectId
    if ObjectId.is_valid(paste_id):

        paste = pastes_collection.find_one({
            "_id": ObjectId(paste_id)
        })

    # Search by custom ID
    if not paste:

        paste = pastes_collection.find_one({
            "custom_id": paste_id
        })

    if not paste:

        raise HTTPException(
            status_code=404,
            detail="Paste not found"
        )

    # Private paste protection
    if (
        paste.get("visibility") == "private"
        and
        paste.get("user_email_key")
        !=
        api_user["email"].replace(".", "_")
    ):

        raise HTTPException(
            status_code=404,
            detail="Paste not found"
        )

    paste["_id"] = str(
        paste["_id"]
    )
    paste.pop("password", None)

    
    if paste.get("burn_after_read"):
        pastes_collection.delete_one({
        "_id": paste["_id"]})
        
        users_collection.update_one(    {
        "email_key": paste["user_email_key"]  },  {   "$pull": {      "pastes": str(paste["_id"])   }   })

    return paste


# =========================
# API DELETE PASTE
# =========================

@app.delete("/api/paste/{paste_id}")
async def api_delete_paste(
    paste_id: str,
    api_user=Depends(get_api_user)
):

    paste = pastes_collection.find_one({
        "_id": ObjectId(paste_id)
    })

    if not paste:

        raise HTTPException(
            status_code=404,
            detail="Paste not found"
        )

    email_key = (
        api_user["email"]
        .replace(".", "_")
    )

    if (
        paste.get("user_email_key")
        !=
        email_key
    ):

        raise HTTPException(
            status_code=403,
            detail="Unauthorized"
        )

    pastes_collection.delete_one({
        "_id": ObjectId(paste_id)
    })

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


# =========================
# API UPDATE PASTE
# =========================

@app.put("/api/paste/{paste_id}")
async def api_update_paste(
    paste_id: str,
    data: dict,
    api_user=Depends(get_api_user)
):

    paste = pastes_collection.find_one({
        "_id": ObjectId(paste_id)
    })

    if not paste:

        raise HTTPException(
            status_code=404,
            detail="Paste not found"
        )

    email_key = (
        api_user["email"]
        .replace(".", "_")
    )

    if (
        paste.get("user_email_key")
        !=
        email_key
    ):

        raise HTTPException(
            status_code=403,
            detail="Unauthorized"
        )

    now = datetime.now(
        timezone.utc
    )

    expire_at = None

    expiration = data.get(
        "expiration",
        "never"
    )
    burn_after_read = False

    if expiration == "burn":
        burn_after_read = True

    elif expiration in ["10m", "10min"]:

        expire_at = (
            now +
            timedelta(minutes=10)
        )

    elif expiration in ["1h", "1hour"]:

        expire_at = (
            now +
            timedelta(hours=1)
        )

    elif expiration in ["1d", "1day"]:

        expire_at = (
            now +
            timedelta(days=1)
        )

    elif expiration in ["1w", "1week"]:

        expire_at = (
            now +
            timedelta(days=7)
        )

    update_data = {

        "title":
            data.get("title"),

        "content":
            data.get("content"),

        "syntax":
            data.get("syntax"),

        "visibility":
            data.get("visibility"),

        "expiration":
            expiration,

        "expire_at":
            expire_at,
        "burn_after_read": burn_after_read,

        "updated_at":
            now.timestamp()
    }

    # Password handling
    if "password" in data:

        if data.get("password"):

            update_data["password"] = (
                hash_password(
                    data["password"]
                )
            )

        else:

            update_data["password"] = None

    pastes_collection.update_one(
        {"_id": ObjectId(paste_id)},
        {
            "$set": update_data
        }
    )

    return {
        "status": "success",
        "message": "Paste updated"
    }


# =========================
# API USER PASTES
# =========================

@app.get("/api/pastes")
async def api_user_pastes(
    api_user=Depends(get_api_user)
):

    email_key = (
        api_user["email"]
        .replace(".", "_")
    )

    pastes = list(
        pastes_collection.find({
            "user_email_key":
                email_key
        })
    )

    results = []

    for paste in pastes:

        paste["_id"] = str(
            paste["_id"]
        )
        paste.pop("password", None)

        results.append(paste)

    return {
        "count": len(results),
        "results": results
                                           }



class ExtensionPaste(BaseModel):

    content: str

    title: Optional[str] = None

    syntax: str = "text"

    visibility: str = "public"

    expiration: str = "never"

    password: Optional[str] = None

    custom_id: Optional[str] = None


def generate_random_title():

    while True:

        title = generate_slug(3)

        existing = pastes_collection.find_one({
            "title": title
        })

        if not existing:
            return title


@app.post("/ext/create")
async def extension_create(
    paste: ExtensionPaste,
    api_user=Depends(get_api_user)
):

    
    data = paste.model_dump()

    # Generate title if none supplied
    if not data.get("title"):

        data["title"] = generate_random_title()

    # Generate custom id from title if none supplied
    if not data.get("custom_id"):

        custom_id = (
            data["title"]
            .lower()
            .replace(".", "-")
            .replace("_", "-")
            .replace(" ", "-")
        )

        original = custom_id
        counter = 1

        while pastes_collection.find_one({
            "custom_id": custom_id
        }):

            custom_id = f"{original}-{counter}"
            counter += 1

        data["custom_id"] = custom_id

    user_doc = users_collection.find_one({
    "email": api_user["email"] })

    if not user_doc:
        raise HTTPException(
            404,
            "User not found"
        )

    result = await create_paste_logic( data, user_doc)
    return { "success": True,  "title": data["title"],  "custom_id": data["custom_id"],  "url": f"https://pastedb.netlify.app/paste/{data['custom_id']}",  "paste_id": result["id"]
           }
