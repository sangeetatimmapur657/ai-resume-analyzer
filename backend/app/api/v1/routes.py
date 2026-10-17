"""Version one API routes."""
import asyncio
import time
import re
from collections import defaultdict, deque
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import ValidationError
import pymupdf
from app.core.config import MAX_FILE_SIZE
from app.schemas.schemas import AnalysisResponse
from app.services.matching_engine import calculate_analysis
from app.services.nvidia_client import AnalysisServiceError, analyze_with_nvidia

router = APIRouter()
MAX_JOB_DESCRIPTION = 12_000
_requests_by_ip: dict[str, deque[float]] = defaultdict(deque)


def redact_contact_details(text: str) -> str:
    """Remove obvious contact channels before sending resume text to the model."""
    text = re.sub(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "[email removed]", text, flags=re.IGNORECASE)
    return re.sub(r"(?<!\w)(?:\+?\d[\d ().-]{8,}\d)(?!\w)", "[phone removed]", text)


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_resume(request: Request, resume: UploadFile = File(...), job_description: str = Form(..., max_length=MAX_JOB_DESCRIPTION)):
    """Analyze a PDF in memory; the original upload is never written to disk."""
    # A small per-process limit protects the single-instance MVP. Multi-instance
    # deployments should also enforce the same limit at their API gateway.
    now = time.monotonic()
    history = _requests_by_ip[request.client.host if request.client else "unknown"]
    while history and now - history[0] > 3600:
        history.popleft()
    if len(history) >= 10:
        raise HTTPException(429, detail={"message": "The hourly analysis limit has been reached. Please try again later."})
    history.append(now)
    name = (resume.filename or "").lower()
    if not name.endswith(".pdf"):
        raise HTTPException(415, detail={"message": "Upload a PDF resume."})
    if resume.content_type not in ("application/pdf", "application/octet-stream", None):
        raise HTTPException(415, detail={"message": "The uploaded file must be a PDF."})
    if not job_description.strip() or len(job_description.strip()) < 30:
        raise HTTPException(422, detail={"message": "Enter a job description with at least 30 characters."})
    content = await resume.read(MAX_FILE_SIZE + 1)
    await resume.close()
    if not content:
        raise HTTPException(422, detail={"message": "The PDF file is empty."})
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, detail={"message": "The PDF must be 5 MB or smaller."})
    if not content.startswith(b"%PDF-"):
        raise HTTPException(415, detail={"message": "The file does not have a valid PDF signature."})
    try:
        document = pymupdf.open(stream=content, filetype="pdf")
        if document.page_count > 50:
            document.close()
            raise HTTPException(422, detail={"message": "The PDF has more than 50 pages. Upload a shorter resume."})
        if document.is_encrypted:
            document.close()
            raise HTTPException(422, detail={"message": "This PDF is password protected. Save an unlocked copy and try again."})
        text = "\n\n".join(page.get_text("text") for page in document)
        document.close()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, detail={"message": "The PDF is corrupt or unreadable. Try exporting a fresh PDF."}) from exc
    if len(text.strip()) < 40:
        raise HTTPException(422, detail={"message": "No readable text was found. Scanned PDFs are not supported yet."})
    try:
        model_result = await asyncio.to_thread(analyze_with_nvidia, redact_contact_details(text), job_description)
        return AnalysisResponse.model_validate(calculate_analysis(model_result, text))
    except AnalysisServiceError as exc:
        raise HTTPException(503, detail={"message": str(exc)}) from exc
    except ValidationError as exc:
        raise HTTPException(502, detail={"message": "The analysis service returned data that could not be validated. Please retry."}) from exc


@router.get("/health")
async def health():
    """Basic liveness check. Does not expose credentials or model configuration."""
    return {"status": "ok", "service": "resume-analyzer"}
