from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "KSL-Tube backend is running"}

class YoutubeRequest(BaseModel):
    url: str

@app.post("/translate")
def translate(request: YoutubeRequest):
    return {"received_url": request.url}