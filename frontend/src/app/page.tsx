"use client";

import { ChangeEvent, DragEvent, FormEvent, useRef, useState } from "react";

type Requirement = { name: string; category: string; status: string; evidence?: string | null };
type Analysis = {
  score: number;
  score_breakdown: Record<string, { base_weight: number; weight: number; match_percentage: number | null; category_score: number; requirements: Requirement[] }>;
  matched_skills: { resume_skill: string; job_skill: string; match_type: string; evidence: string }[];
  missing_evidence: string[];
  uncertain_matches: string[];
  experience_observations: string;
  qualification_observations: string;
  improvement_suggestions: string[];
  warnings: string[];
};

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const MAX_FILE_BYTES = 5 * 1024 * 1024;

export default function Home() {
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState("");
  const [result, setResult] = useState<Analysis | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);

  function chooseFile(next: File | undefined) {
    setError("");
    if (!next) return;
    if (!next.name.toLowerCase().endsWith(".pdf") || (next.type && next.type !== "application/pdf")) {
      setFile(null); setError("Choose a PDF file to continue."); return;
    }
    if (next.size === 0) { setFile(null); setError("That file is empty. Choose another PDF."); return; }
    if (next.size > MAX_FILE_BYTES) { setFile(null); setError("The PDF must be 5 MB or smaller."); return; }
    setFile(next);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault(); setDragging(false); chooseFile(event.dataTransfer.files[0]);
  }

  async function analyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError("");
    if (!file) { setError("Add your resume PDF first."); return; }
    if (job.trim().length < 30) { setError("Add a job description with at least 30 characters."); return; }
    if (job.length > 12000) { setError("The job description must be 12,000 characters or fewer."); return; }
    setBusy(true);
    try {
      const body = new FormData(); body.append("resume", file); body.append("job_description", job);
      const response = await fetch(`${API_URL}/api/v1/analyze`, { method: "POST", body });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        const detail = payload?.detail;
        const message = typeof detail === "string" ? detail : detail?.message;
        throw new Error(message || "Analysis could not be completed. Check your inputs and try again.");
      }
      setResult(payload as Analysis);
      requestAnimationFrame(() => document.getElementById("results")?.focus());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The analysis service could not be reached. Check that the backend is running and retry.");
    } finally { setBusy(false); }
  }

  function reset() { setFile(null); setJob(""); setResult(null); setError(""); if (input.current) input.current.value = ""; window.scrollTo({ top: 0, behavior: "smooth" }); }

  return (
    <main className="shell">
      <header className="topbar"><a className="brand" href="#top" aria-label="Matchbook home"><span className="brand-mark">M</span> Matchbook</a><span className="top-note">RESUME ALIGNMENT</span></header>
      <section id="top" className="intro"><p className="eyebrow">A clearer next step</p><h1>Make your experience<br className="desktop-break"/> easier to see.</h1><p className="lede">Compare your resume with a job description. Get an explainable alignment estimate and practical edits grounded in what you’ve actually done.</p></section>

      {!result ? <form className="workspace" onSubmit={analyze}>
        <div className="section-heading"><div><span className="step">01</span><h2>Your materials</h2></div><p>Both are needed to make a useful comparison.</p></div>
        <div className="form-grid">
          <section className="field-block"><label className="field-label" htmlFor="resume">Resume <span>PDF · up to 5 MB</span></label>
            <div className={`dropzone ${dragging ? "is-dragging" : ""} ${file ? "has-file" : ""}`} onDragOver={(e) => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop}>
              <input ref={input} id="resume" className="visually-hidden" type="file" accept=".pdf,application/pdf" onChange={(e: ChangeEvent<HTMLInputElement>) => chooseFile(e.target.files?.[0])} aria-describedby="resume-help" />
              {file ? <div className="file-row"><span className="file-icon" aria-hidden="true">PDF</span><span className="file-info"><strong>{file.name}</strong><small>{(file.size / 1024).toFixed(0)} KB · Ready to analyze</small></span><button className="text-button" type="button" onClick={() => { setFile(null); if (input.current) input.current.value = ""; }}>Remove</button></div> : <><span className="upload-icon" aria-hidden="true">↑</span><p><button className="text-button" type="button" onClick={() => input.current?.click()}>Choose a file</button> or drop it here</p><small id="resume-help">Text based PDFs work best. Scanned documents may not be readable.</small></>}
            </div>
          </section>
          <section className="field-block"><label className="field-label" htmlFor="job">Job description <span>{job.length.toLocaleString()} / 12,000</span></label><textarea id="job" value={job} onChange={(e) => setJob(e.target.value)} maxLength={12000} minLength={30} placeholder="Paste the role description, including responsibilities and qualifications…" rows={9} required aria-describedby="job-help" /><small id="job-help">Include the full description for a more complete comparison.</small></section>
        </div>
        {error && <p className="error-message" role="alert"><span aria-hidden="true">!</span>{error}</p>}
        <div className="form-footer"><p><span className="lock" aria-hidden="true">◈</span> Your PDF is processed temporarily. Resume text is sent to NVIDIA for analysis and is not saved by this app.</p><button className="primary-button" type="submit" disabled={busy}>{busy ? <><span className="spinner" aria-hidden="true"/> Comparing…</> : <>Compare resume <span aria-hidden="true">↗</span></>}</button></div>
        {busy && <p className="status" role="status">Reading your resume and comparing it with the role. This can take up to a minute.</p>}
      </form> : <Results result={result} onReset={reset} />}

      <footer className="page-footer"><span>Matchbook</span><span>Alignment estimate only · Not a hiring prediction</span></footer>
    </main>
  );
}

function Results({ result, onReset }: { result: Analysis; onReset: () => void }) {
  const labels: Record<string, string> = { required_skills: "Required skills", relevant_experience: "Relevant experience", explicit_qualifications: "Qualifications", preferred_skills: "Preferred skills" };
  const categories = Object.entries(result.score_breakdown);
  return <section id="results" className="results" tabIndex={-1} aria-labelledby="result-title">
    <div className="section-heading result-heading"><div><span className="step">02</span><h2 id="result-title">Your alignment</h2></div><button className="text-button" onClick={onReset}>← Start a new comparison</button></div>
    <div className="score-panel"><div className="score-number">{Math.round(result.score)}<span>/100</span></div><div className="score-copy"><p className="eyebrow">Job description alignment</p><h3>A guide to where your resume connects</h3><p>This score reflects evidence in the resume for requirements in this specific description. It is not a measure of candidate quality or hiring probability.</p></div></div>
    {result.warnings.length > 0 && <div className="notice" role="status">{result.warnings.join(" ")}</div>}
    <section className="result-section"><div className="result-section-title"><span className="step">A</span><div><h3>Score breakdown</h3><p>Initial category weights are product choices. Direct evidence counts fully; verified partial evidence counts half. Unclear and unstated requirements aren’t scored, and active weights are normalized.</p></div></div><div className="breakdown">{categories.map(([key, value]) => <div className="breakdown-row" key={key}><div className="breakdown-label"><strong>{labels[key] || key}</strong><span>{Math.round(value.base_weight * 100)}% initial · {Math.round(value.weight * 100)}% effective · {value.match_percentage === null ? "Not specified" : `${Math.round(value.match_percentage * 100)}% aligned`}</span></div><div className="bar" aria-label={`${labels[key] || key}: ${value.category_score} points`}><span style={{ width: `${value.match_percentage === null ? 0 : value.match_percentage * 100}%` }} /></div><strong className="points">{value.category_score.toFixed(1)} pts</strong></div>)}</div></section>
    <section className="result-section"><div className="result-section-title"><span className="step">B</span><div><h3>Skills and evidence</h3><p>Matches include a supporting phrase found in your resume.</p></div></div><div className="evidence-grid"><div><h4>Matched</h4>{result.matched_skills.length ? <ul className="clean-list">{result.matched_skills.map((item, i) => <li key={`${item.job_skill}-${i}`}><span className="status-dot matched"/><div><strong>{item.job_skill}</strong><p>“{item.evidence}”</p></div></li>)}</ul> : <p className="muted">No explicit skill matches were confirmed.</p>}</div><div><h4>Needs more evidence</h4>{result.missing_evidence.length ? <ul className="simple-list">{result.missing_evidence.map((item, i) => <li key={i}>{item}</li>)}</ul> : <p className="muted">No requirements were marked as missing evidence.</p>}{result.uncertain_matches.length > 0 && <><h4 className="subheading">Possible matches</h4><ul className="simple-list uncertain">{result.uncertain_matches.map((item, i) => <li key={i}>{item}</li>)}</ul></>}</div></div></section>
    <section className="result-section"><div className="result-section-title"><span className="step">C</span><div><h3>Experience & qualifications</h3><p>Observations from the supplied documents.</p></div></div><div className="observation-grid"><article><h4>Relevant experience</h4><p>{result.experience_observations || "No specific experience requirement was identified."}</p></article><article><h4>Qualifications</h4><p>{result.qualification_observations || "No specific qualification requirement was identified."}</p></article></div></section>
    <section className="result-section"><div className="result-section-title"><span className="step">D</span><div><h3>Ways to strengthen the resume</h3><p>Suggestions are prompts to consider, not claims about your background.</p></div></div>{result.improvement_suggestions.length ? <ol className="suggestions">{result.improvement_suggestions.map((item, i) => <li key={i}>{item}</li>)}</ol> : <p className="muted">No specific edits were suggested for this comparison.</p>}</section>
    <div className="result-end"><p>Keep every edit truthful to your experience. The score is a directional estimate based on the wording provided.</p><button className="primary-button" onClick={onReset}>Analyze another resume <span aria-hidden="true">↗</span></button></div>
  </section>;
}
