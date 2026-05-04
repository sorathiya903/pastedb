from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime, timedelta
from typing import Optional
from bson import ObjectId

client = MongoClient("mongodb://Aditya:Qu1IZrvVdB0ajaCm@ac-zqtl0lb-shard-00-00.fz0oqsr.mongodb.net:27017,ac-zqtl0lb-shard-00-01.fz0oqsr.mongodb.net:27017,ac-zqtl0lb-shard-00-02.fz0oqsr.mongodb.net:27017/?ssl=true&replicaSet=atlas-10lbo4-shard-0&authSource=admin&appName=Cluster0")
db = client["pasteDB"]
collection = db["pastes"]

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
        default_factory=datetime.utcnow
    )


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.get("/")
def home():
    return {"message": "Server running"}

@app.post("/create")
async def create_new_paste(paste: PasteCreate):

    try:

        paste_dict = paste.dict()

        # CURRENT TIME
        now = datetime.utcnow()

        # DEFAULT
        expire_at = None

        if paste.expiration in ["10m", "10min"]:
            expire_at = now + timedelta(minutes=10)

        elif paste.expiration in ["1h", "1hour"]:

            expire_at = now + timedelta(hours=1)

        elif paste.expiration in ["1d", "1day"]:

            expire_at = now + timedelta(days=1)

        elif paste.expiration in ["1w", "1week"]:

            expire_at = now + timedelta(days=7)

        paste_dict["expire_at"] = expire_at

        result = collection.insert_one(
            paste_dict
        )

        return {

            "status": "success",

            "id": str(result.inserted_id),

            "message":
            "Paste created successfully!"

        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )



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

        # EXPIRED CHECK

        expire_at = paste.get("expire_at")

        if expire_at:

            if datetime.utcnow() > expire_at:

                raise HTTPException(

                    status_code=404,

                    detail="Paste expired"

                )

        return {

            "title": paste.get("title"),

            "content": paste.get("content"),

            "syntax": paste.get("syntax"),

            "expiration": paste.get("expiration"),

            "created_at": str(paste.get("created_at")),
            "expire_at": str(paste.get("expire_at"))
            

        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
