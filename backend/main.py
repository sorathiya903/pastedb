from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime
from typing import Optional

client = MongoClient("mongodb://Aditya:Qu1IZrvVdB0ajaCm@ac-zqtl0lb-shard-00-00.fz0oqsr.mongodb.net:27017,ac-zqtl0lb-shard-00-01.fz0oqsr.mongodb.net:27017,ac-zqtl0lb-shard-00-02.fz0oqsr.mongodb.net:27017/?ssl=true&replicaSet=atlas-10lbo4-shard-0&authSource=admin&appName=Cluster0")
db = client["pasteDB"]
collection = db["pastes"]


class PasteCreate(BaseModel):
    title: str = Field(default="Untitled Paste", max_length=100)
    content: str
    syntax: str = Field(default="text")
    expiration: str = Field(default="never")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)



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
        
    
        result = collection.insert_one(paste_dict)
        
        
        return {
            "status": "success",
            "id": str(result.inserted_id),
            "message": "Paste created successfully!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


