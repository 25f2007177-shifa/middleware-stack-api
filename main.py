
import time
import uuid
import threading
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI()

EMAIL = "25f2007177@ds.study.iitm.ac.in"

ALLOWED_ORIGINS = [
    "https://app-jdyuk7.example.com",
    "https://exam.sanand.workers.dev",
]

RATE_LIMIT = 9
WINDOW_SECONDS = 10

rate_lock = threading.Lock()
client_requests = defaultdict(deque)


def check_rate_limit(client_id: str):
    now = time.monotonic()

    with rate_lock:
        timestamps = client_requests[client_id]

        while timestamps and now - timestamps[0] >= WINDOW_SECONDS:
            timestamps.popleft()

        if len(timestamps) >= RATE_LIMIT:
            retry_after = max(
                1, int(WINDOW_SECONDS - (now - timestamps[0]) + 0.999)
            )
            return retry_after

        timestamps.append(now)
        return None


@app.middleware("http")
async def request_context_and_rate_limit(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    if request.method != "OPTIONS":
        client_id = request.headers.get("X-Client-Id") or "anonymous"
        retry_after = check_rate_limit(client_id)

        if retry_after is not None:
            response = JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(retry_after)},
            )
            response.headers["X-Request-ID"] = request_id
            return response

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["X-Request-ID", "X-Client-Id"],
    expose_headers=["X-Request-ID"],
)


@app.get("/ping")
def ping(request: Request):
    return {
        "email": EMAIL,
        "request_id": request.state.request_id,
    }

