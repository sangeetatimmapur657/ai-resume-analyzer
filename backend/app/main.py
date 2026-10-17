"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import CORS_ORIGINS
from app.core.config import MAX_REQUEST_SIZE
from app.api.v1.routes import router

app = FastAPI(title="AI Resume Analyzer", version="1.0.0", docs_url="/api/docs", redoc_url=None)


class RequestBodyLimitMiddleware:
    """Bound the multipart body before Starlette parses and spools uploaded files."""

    def __init__(self, application, limit: int):
        self.application = application
        self.limit = limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") != "/api/v1/analyze":
            await self.application(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                if int(content_length) > self.limit:
                    await self._too_large(send)
                    return
            except ValueError:
                await self._too_large(send)
                return

        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.limit:
                await self._too_large(send)
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break

        body = b"".join(chunks)
        delivered = False

        async def replay_body():
            nonlocal delivered
            if delivered:
                return {"type": "http.request", "body": b"", "more_body": False}
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.application(scope, replay_body, send)

    async def _too_large(self, send):
        payload = b'{"detail":{"message":"The request is too large. Keep the PDF under 5 MB and the job description under 12,000 characters."}}'
        await send({"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())]})
        await send({"type": "http.response.body", "body": payload})


app.add_middleware(RequestBodyLimitMiddleware, limit=MAX_REQUEST_SIZE)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=False,
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
app.include_router(router, prefix="/api/v1", tags=["analysis"])
