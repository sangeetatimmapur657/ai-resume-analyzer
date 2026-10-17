import asyncio
import os
import time
from collections import deque
import httpx
import pymupdf
from app.main import app
from app.api.v1 import routes
from app.schemas.schemas import ModelAnalysis


def pdf_bytes(text="Candidate has Python experience and built web applications."):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def encrypted_pdf_bytes():
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Candidate resume with readable text.")
    data = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="user", owner_pw="owner")
    doc.close()
    return data


async def request(method, path, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def run(coroutine):
    # Windows' default Proactor loop uses socketpair, unavailable in this sandbox.
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(coroutine)


def test_health_is_minimal():
    response = run(request("GET", "/api/v1/health"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "resume-analyzer"}


def test_invalid_signature_rejected_before_ai_call():
    response = run(request("POST", "/api/v1/analyze", data={"job_description": "A role requiring Python and application development."}, files={"resume": ("resume.pdf", b"not pdf", "application/pdf")}))
    assert response.status_code == 415


def test_empty_pdf_and_unreadable_text_are_rejected():
    empty = run(request("POST", "/api/v1/analyze", data={"job_description": "A role requiring Python and application development."}, files={"resume": ("resume.pdf", b"", "application/pdf")}))
    no_text = run(request("POST", "/api/v1/analyze", data={"job_description": "A role requiring Python and application development."}, files={"resume": ("resume.pdf", pdf_bytes(""), "application/pdf")}))
    assert empty.status_code == 422
    assert no_text.status_code == 422


def test_bad_extension_corrupt_and_oversized_uploads_are_rejected():
    job = {"job_description": "A role requiring Python and application development."}
    wrong_type = run(request("POST", "/api/v1/analyze", data=job, files={"resume": ("resume.docx", pdf_bytes(), "application/pdf")}))
    corrupt = run(request("POST", "/api/v1/analyze", data=job, files={"resume": ("resume.pdf", b"%PDF-1.4\\n%%EOF", "application/pdf")}))
    too_large = run(request("POST", "/api/v1/analyze", data=job, files={"resume": ("resume.pdf", b"%PDF-" + b"x" * (5 * 1024 * 1024), "application/pdf")}))
    request_too_large = run(request("POST", "/api/v1/analyze", data=job, files={"resume": ("resume.pdf", b"%PDF-" + b"x" * (6 * 1024 * 1024), "application/pdf")}))
    assert wrong_type.status_code == 415
    assert corrupt.status_code == 422
    assert too_large.status_code == 413
    assert request_too_large.status_code == 413


def test_encrypted_pdf_is_rejected():
    response = run(request("POST", "/api/v1/analyze", data={"job_description": "A role requiring Python and application development."}, files={"resume": ("resume.pdf", encrypted_pdf_bytes(), "application/pdf")}))
    assert response.status_code == 422


def test_complete_multipart_flow_uses_real_api_contract(monkeypatch):
    monkeypatch.setattr(routes, "analyze_with_nvidia", lambda *_: ModelAnalysis.model_validate({"requirements": [{"name": "Python", "category": "required_skills", "status": "matched", "evidence": "Python experience"}]}))
    response = run(request("POST", "/api/v1/analyze", data={"job_description": "We need Python experience for application development work."}, files={"resume": ("resume.pdf", pdf_bytes(), "application/pdf")}))
    assert response.status_code == 200, response.text
    assert response.json()["score"] == 100
    assert response.json()["matched_skills"][0]["evidence"] == "Python experience"


def test_per_ip_hourly_limit_is_enforced():
    routes._requests_by_ip["127.0.0.1"] = deque([time.monotonic()] * 10)
    response = run(request("POST", "/api/v1/analyze", data={"job_description": "A role requiring Python and application development."}, files={"resume": ("resume.pdf", pdf_bytes(), "application/pdf")}))
    assert response.status_code == 429
