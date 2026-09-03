from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from routers import youtube
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 나중에 실제 Frontend 주소로 교체
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(youtube.router)

@app.get("/")
def read_root():
    return {"message": "KSL-Tube backend is running"}

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    first_error = exc.errors()[0]
    message = first_error["msg"].replace("Value error, ", "")

    return JSONResponse(
        status_code=422,
        content={"error": message},
    )