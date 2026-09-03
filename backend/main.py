from fastapi import FastAPI
from routers import youtube

app = FastAPI()

app.include_router(youtube.router)

@app.get("/")
def read_root():
    return {"message": "KSL-Tube backend is running"}