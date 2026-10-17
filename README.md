# Matchbook · AI Resume Analyzer

Matchbook compares a PDF resume with a job description and returns an evidence based alignment estimate. It is designed to help a job seeker see what their resume already demonstrates and where clearer evidence may help. It does not measure candidate quality or predict hiring outcomes.

## Features

- PDF upload with a 5 MiB limit, extension, MIME type, signature, encryption and readable text checks.
- NVIDIA Nemotron structured requirement extraction and practical resume suggestions.
- Backend evidence verification: a match can contribute only when the model's quoted excerpt appears in the extracted resume text.
- Deterministic Python score with category breakdown and explicit handling of missing and uncertain evidence.
- Responsive form and results view, drag and drop upload, keyboard accessible controls, loading and retry states.
- Resume files are not saved permanently by this app; the multipart upload stream is closed after processing.

## Architecture

`frontend/` is the Next.js App Router and TypeScript user interface. `backend/` is a FastAPI service. It extracts text using PyMuPDF, sends the resume text and job description to NVIDIA's OpenAI compatible chat completions API, validates the structured response with Pydantic, verifies evidence, then calculates the score. No database is needed for this single user MVP, so analysis history is not stored.

NVIDIA API format was checked against the [official Nemotron 3.5 Lightning model page](https://build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b) and [NVIDIA NIM structured JSON documentation](https://docs.nvidia.com/nim/large-language-models/latest/get-started/advanced/get-started-nemotron-3.5-lightning.html). The model's JSON is treated as untrusted and schema validated. JSON mode guarantees JSON syntax, not the requested shape; Pydantic supplies that shape validation.

## Requirements

- Node.js 20+ and npm.
- Python 3.11+ and pip.
- An NVIDIA NIM API key for live analysis. The UI and backend tests do not require paid service connectivity.

## Local setup

### 1. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edit `backend/.env` and set `NVIDIA_API_KEY`. Keep each setting on its own `NAME=value` line. The example file contains no secret and the setup command does not overwrite an existing `.env`. To start FastAPI:

```powershell
uvicorn app.main:app --reload --port 8000
```

Health check: `http://localhost:8000/api/v1/health`. API documentation: `http://localhost:8000/api/docs`.

### 2. Frontend

In another terminal:

```powershell
cd frontend
npm install
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
npm run dev
```

Open `http://localhost:3000`. The browser calls the FastAPI URL in `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`). This URL is public configuration; never put the NVIDIA API key in a `NEXT_PUBLIC_` variable.

## API contract

`POST /api/v1/analyze` accepts multipart form data:

- `resume`: PDF, maximum 5 MiB.
- `job_description`: 30–12,000 characters.

On success it returns `score` (0–100), `score_breakdown`, `matched_skills` with exact resume evidence, `missing_evidence`, `uncertain_matches`, experience and qualification observations, improvement suggestions, and warnings. Validation errors use 4xx status codes; model/service failures return a safe 503 message. A basic liveness endpoint is `GET /api/v1/health`.

## Scoring method

Initial weights are required skills 50%, relevant experience 25%, explicit qualifications 15%, and preferred skills 10%. These are product choices, not validated hiring criteria. Requirement names are deduplicated within each category after simple alias normalization. A directly evidenced match scores 1; a verified partial match scores 0.5; a stated requirement without evidence scores 0; uncertain requirements are excluded. Empty and all-uncertain categories are omitted, and active category weights are proportionally normalized back to 100%. The final score is the sum of these category contributions, rounded to a whole number. This makes absent job requirements neutral and avoids presenting uncertainty as proof of absence.

## Checks

From `frontend/`:

```powershell
npm run lint
npx tsc --noEmit
npm run build
```

From `backend/`:

```powershell
python -m pytest -q
python scripts/check_nvidia.py
```

These automated tests mock NVIDIA for the complete multipart contract. `python scripts/check_nvidia.py` makes one separate real connectivity request and prints only a safe status; it can incur NVIDIA trial or service usage.

## Privacy and security

The NVIDIA key is read only by FastAPI from `backend/.env`. The request body is capped before multipart parsing; the framework may temporarily spool larger uploads, and the upload stream is closed after processing. The app does not save resumes permanently or keep analysis history. Obvious email addresses and phone numbers are removed from extracted text before sending it to NVIDIA, but other identifying details may remain. The provider's applicable retention terms govern that processing; this project does not claim third party non-retention. CORS defaults to localhost and can be changed with `CORS_ORIGINS`. A per-process limit of ten analysis attempts per client IP per hour protects a single instance; multi-instance deployment must also apply a shared limit at its gateway. Do not expose FastAPI directly to the public internet without TLS, gateway rate limits, and appropriate operational monitoring.

## Deployment notes

Deploy the frontend and Python backend as separate services. Set `NEXT_PUBLIC_API_URL` to the reachable backend URL and set `NVIDIA_API_KEY`, `NVIDIA_BASE_URL`, `NVIDIA_MODEL`, `MAX_FILE_SIZE`, and `CORS_ORIGINS` in the backend environment. Configure TLS and gateway level rate limiting. Build the frontend with `npm run build` and run it with `npm run start`; run the API with `uvicorn app.main:app --host 0.0.0.0 --port 8000`. Do not deploy this project automatically or commit credentials.

## Troubleshooting

- **Backend unavailable:** start Uvicorn and confirm `/api/v1/health` returns `{"status":"ok"...}`.
- **Missing key:** set `NVIDIA_API_KEY` in `backend/.env`, then restart Uvicorn.
- **Malformed `.env`:** keep each variable on a `NAME=value` line; if a key was pasted without its variable name, label it `NVIDIA_API_KEY=` without sharing the value in chat.
- **No PDF text:** scanned/image-only resumes are not supported in this version; export a text based PDF.
- **CORS error:** add the exact frontend origin to backend `CORS_ORIGINS`, then restart the API.
- **NVIDIA 429 or service error:** wait and retry; API rate limits, credits and availability depend on the provider account.

## Evidence matrix

| Requirement | Implementation | Validation | Actual result | Status |
|---|---|---|---|---|
| PDF validation and extraction | Multipart endpoint; signature, MIME, extension, file and request size, encryption and text checks; PyMuPDF | `python -m pytest -q` in backend | Valid text PDF, empty, textless, corrupt, unsupported, oversized, and encrypted cases passed; request cap checked before multipart parsing | PASS (12 tests passed) |
| NVIDIA structured analysis | OpenAI Python client at configured NVIDIA endpoint; Pydantic response schema and safe errors | `python -m pytest -q`; `python scripts/check_nvidia.py` | JSON mode, disabled reasoning, schema validation, missing key, malformed JSON covered by mocks; live connectivity command stopped safely because no usable key is configured | BLOCKED (live service) |
| Deterministic weighted score | Backend scorer, category breakdown, alias deduplication, partial and uncertainty policy | `python -m pytest -q` | All, partial, missing, uncertain, duplicate alias, and unverified quote cases passed | PASS |
| Real frontend workflow | FormData request to FastAPI, real result only, errors and loading state | `npm run lint`; `npx tsc --noEmit --incremental false`; `npm run build` | Lint and TypeScript passed; Webpack production build completed successfully | PASS |
| Secret and privacy boundaries | Backend-only key, uploads closed after parsing, contact redaction, bounded body/file sizes, localhost CORS, per-process request limit | API tests and code inspection | Upload checks, body cap, per-IP limit, and safe error paths passed; third-party retention policy was not independently verified | PASS (implementation) |
| Responsive accessible interface | Responsive layout, labels, visible focus, status/error announcements, reduced motion | CSS and semantic markup inspection; local browser review attempted | Responsive breakpoints and accessibility hooks are present; in-app browser timed out connecting to the local dev server, so rendered mobile and keyboard interaction remain unverified | NOT TESTED (browser unavailable) |
