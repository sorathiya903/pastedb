from fastapi import FastAPI, HTTPException, Depends, Query, Cookie, Request 
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

import os
import re
from collections import Counter
import user_agents
import secrets
import logging
#ogging.basicConfig(level=logging.DEBUG)
import traceback
import requests
import time
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


async def create_paste_logic(
    paste_data: dict,
    user_data: dict
):

    email_key = user_data["email"].replace(".", "_")

    now = datetime.now(timezone.utc)

    expire_at = None

    expiration = paste_data.get("expiration", "never")

    if expiration in ["10m", "10min"]:
        expire_at = now + timedelta(minutes=10)

    elif expiration in ["1h", "1hour"]:
        expire_at = now + timedelta(hours=1)

    elif expiration in ["1d", "1day"]:
        expire_at = now + timedelta(days=1)

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

    # PASSWORD HASH
    if paste_data.get("password"):

        paste_data["password"] = hash_password( paste_data["password"])

    # FINAL DOC
    paste_data.update({

        "user_email_key": email_key,

        "expire_at": expire_at,

        "custom_id": custom_id,

        "owner": user_data.get("name"),

        "picture":  user_data.get("picture"),

        "created_at":now.timestamp(),

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

            "visitors": [],

            "activities": [],

            "daily_views": {}

        }

    })

    # INSERT
    result =  pastes_collection.insert_one(  paste_data    )

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
        "expire_at": expiry,
        "visibility":data.get("visibility")
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
        "Only public search allowed"
    )

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





@app.post("/run")
async def run_code(data: RunCode):

    allowed = [
        "python",
        "javascript"
    ]

    if data.language not in allowed:

        return {
            "error": "Language not supported"
        }



    language_ids = {

        "python": 71,

        "javascript": 63

    }



    try:

        # CREATE SUBMISSION

        response = requests.post(

            "https://ce.judge0.com/submissions?base64_encoded=false&wait=true",

            json={

                "source_code": data.code,

                "language_id":
                    language_ids[data.language]

            },

            timeout=20
        )



        result = response.json()



        stdout =  result.get("stdout")

        stderr = result.get("stderr")

        compile_output =   result.get("compile_output")



        output = (  stdout or stderr  or compile_output  or "No output" )



        return {
            "output": output
        }



    except Exception as e:

        return {
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

@app.post("/generate-api-key")
async def generate_api_key(
    user=Depends(get_current_user)
):

    email = user.get("email")

    if not email:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized"
        )

    # Generate secure API key
    api_key = secrets.token_hex(32)

    # Save API key
    api_keys_collection.insert_one({
        "email": email,
        "api_key": api_key,
        "created_at": datetime.now(timezone.utc)
    })

    return {
        "status": "success",
        "api_key": api_key
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

    return {
        "keys": keys
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


# =========================
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

    if expiration in ["10m", "10min"]:

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
