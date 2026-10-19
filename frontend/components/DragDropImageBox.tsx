"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import ExamplePicker, { type Example } from "@/components/ExamplePicker";
import Icon from "@/components/Icon";
import { PHOTO_TYPES, predictionEndpoint, requestPrediction, validatePhoto, type PredictionResult } from "@/lib/prediction";

export type { PredictionResult } from "@/lib/prediction";

type Photo = { file: File; url: string };
type Phase = "idle" | "preparing" | "ready" | "analyzing" | "complete";

export default function DragDropImageBox({ className = "", apiUrl }: { className?: string; apiUrl?: string }) {
  const input = useRef<HTMLInputElement>(null);
  const camera = useRef<HTMLInputElement>(null);
  const photoRef = useRef<Photo | null>(null);
  const request = useRef<AbortController | null>(null);
  const intent = useRef(0);
  const dragDepth = useRef(0);
  const [photo, setPhoto] = useState<Photo | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [dragging, setDragging] = useState(false);
  const [exampleLoading, setExampleLoading] = useState<string | null>(null);
  const reducedMotion = useReducedMotion();

  useEffect(() => () => {
    intent.current += 1;
    request.current?.abort();
    if (photoRef.current) URL.revokeObjectURL(photoRef.current.url);
  }, []);

  function beginIntent(): number {
    intent.current += 1;
    request.current?.abort();
    request.current = null;
    setResult(null);
    setError(null);
    setExampleLoading(null);
    return intent.current;
  }

  async function adoptPhoto(file: File, generation: number): Promise<void> {
    let url: string | null = null;
    try {
      await validatePhoto(file);
      if (generation !== intent.current) return;
      url = URL.createObjectURL(file);
      const image = new window.Image();
      image.src = url;
      await image.decode();
      if (generation !== intent.current) return;
      const previous = photoRef.current;
      const next = { file, url };
      photoRef.current = next;
      setPhoto(next);
      url = null; // The selected photo now owns this URL.
      if (previous) URL.revokeObjectURL(previous.url);
      setPhase("ready");
    } catch (caught) {
      if (generation !== intent.current) return;
      setError(caught instanceof Error && caught.name !== "EncodingError" ? caught.message : "We couldn’t open that photo. Please try another image.");
      setPhase(photoRef.current ? "ready" : "idle");
    } finally {
      if (url) URL.revokeObjectURL(url);
    }
  }

  async function selectFiles(files: File[]): Promise<void> {
    if (files.length === 0) return;
    const generation = beginIntent();
    if (files.length !== 1) {
      setPhase(photoRef.current ? "ready" : "idle");
      setError("One little mystery at a time. Please choose a single photo.");
      return;
    }
    setPhase("preparing");
    await adoptPhoto(files[0], generation);
  }

  async function selectExample(example: Example): Promise<void> {
    const generation = beginIntent();
    const controller = new AbortController();
    request.current = controller;
    setPhase("preparing");
    setExampleLoading(example.id);
    try {
      const response = await fetch(example.src, { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15_000)]) });
      if (!response.ok) throw new Error("That example couldn’t load. Try again or choose your own photo.");
      const blob = await response.blob();
      if (generation !== intent.current) return;
      await adoptPhoto(new File([blob], `${example.id}-example.jpg`, { type: "image/jpeg" }), generation);
    } catch (caught) {
      if (generation === intent.current && !controller.signal.aborted) {
        setError(caught instanceof Error ? caught.message : "That example couldn’t load. Please try again.");
        setPhase(photoRef.current ? "ready" : "idle");
      }
    } finally {
      if (generation === intent.current) {
        setExampleLoading(null);
        request.current = null;
      }
    }
  }

  function clearPhoto(): void {
    beginIntent();
    if (photoRef.current) URL.revokeObjectURL(photoRef.current.url);
    photoRef.current = null;
    setPhoto(null);
    setPhase("idle");
    input.current?.focus();
  }

  async function predict(): Promise<void> {
    const selected = photoRef.current;
    if (!selected || phase === "analyzing" || phase === "preparing") return;
    const generation = beginIntent();
    const controller = new AbortController();
    request.current = controller;
    const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(45_000)]);
    setPhase("analyzing");
    try {
      const next = await requestPrediction(selected.file, { endpoint: predictionEndpoint(apiUrl), signal });
      if (generation !== intent.current) return;
      setResult(next);
      setPhase("complete");
    } catch (caught) {
      if (generation !== intent.current || controller.signal.aborted) return;
      setError(signal.aborted && signal.reason?.name === "TimeoutError" ? "That took longer than expected. Please give it another try." : caught instanceof Error ? caught.message : "Something went a little sideways. Please try again.");
      setPhase("ready");
    } finally {
      if (generation === intent.current) request.current = null;
    }
  }

  const busy = phase === "preparing" || phase === "analyzing";
  const smiski = result?.prediction === "Smiski";
  const score = result ? (result.confidence * 100).toFixed(1) : "";

  return (
    <div className={`photo-workbench ${className}`}>
      <input ref={input} id="photo-input" className="sr-only" type="file" accept={PHOTO_TYPES} aria-label="Choose a photo" onChange={event => { void selectFiles(Array.from(event.target.files || [])); event.currentTarget.value = ""; }} />
      <input ref={camera} className="sr-only" type="file" accept={PHOTO_TYPES} capture="environment" aria-label="Take a photo" onChange={event => { void selectFiles(Array.from(event.target.files || [])); event.currentTarget.value = ""; }} />
      <div className={`photo-zone ${dragging ? "is-dragging" : ""}`}
        onDragEnter={event => { event.preventDefault(); if (event.dataTransfer.types.includes("Files")) { dragDepth.current += 1; setDragging(true); } }}
        onDragOver={event => { event.preventDefault(); event.dataTransfer.dropEffect = "copy"; }}
        onDragLeave={event => { event.preventDefault(); dragDepth.current = Math.max(0, dragDepth.current - 1); if (dragDepth.current === 0) setDragging(false); }}
        onDrop={event => { event.preventDefault(); dragDepth.current = 0; setDragging(false); void selectFiles(Array.from(event.dataTransfer.files)); }}>
        {photo ? (
          <div className="photo-stage">
            {/* Object URLs preview local files without uploading them. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={photo.url} alt={`Selected photo: ${photo.file.name}`} className="photo-preview" />
            <span className="photo-tag">Your little mystery</span>
            <button className="remove-photo icon-button" type="button" onClick={clearPhoto} aria-label="Remove photo"><Icon name="close" size={17} /></button>
            {phase === "analyzing" && <div className="scan-overlay" aria-hidden="true"><span className="scan-line" /><span className="scan-label"><span className="spinner" /> Taking a closer look…</span></div>}
            {dragging && <span className="replace-overlay">Drop to replace this photo</span>}
          </div>
        ) : (
          <button className="drop-area" type="button" onClick={() => input.current?.click()} aria-describedby="upload-hint" disabled={phase === "preparing"}>
            <span className="upload-symbol"><Icon name="upload" size={26} /><span className="symbol-sparkle"><Icon name="sparkle" size={14} /></span></span>
            <span className="drop-title">{phase === "preparing" ? "Getting your photo ready…" : dragging ? "A little closer. Drop it here." : "Who’s hiding in your photo?"}</span>
            <span className="drop-description">Drag & drop a photo, or <span>browse files</span></span>
            <span id="upload-hint" className="upload-hint">JPG, PNG or WebP · Up to 10 MB</span>
          </button>
        )}
      </div>
      {photo && <div className="photo-info"><span title={photo.file.name}>{photo.file.name}</span><button className="change-photo" type="button" onClick={() => input.current?.click()}>Change photo <Icon name="image" size={13} /></button></div>}
      <button className="camera-button" type="button" onClick={() => camera.current?.click()}><Icon name="camera" size={15} /> Or take a photo</button>
      {photo && <button className="predict-button" type="button" disabled={busy} onClick={result ? () => input.current?.click() : () => void predict()}>
        {phase === "analyzing" ? <><span className="spinner" /> Looking for a little glow…</> : phase === "preparing" ? "Getting your photo ready…" : result ? <>Try another photo <Icon name="arrow" size={17} /></> : error ? <><Icon name="retry" size={16} /> Try again</> : <>Take a closer look <Icon name="sparkle" size={17} /></>}
      </button>}
      {error && <div className="photo-error" role="alert"><span><strong>A little hiccup.</strong> {error}</span><button type="button" onClick={() => setError(null)} aria-label="Dismiss error"><Icon name="close" size={15} /></button></div>}
      <AnimatePresence mode="wait">
        {result && <motion.div className={`result-card ${smiski ? "is-smiski" : "is-other"}`} key={`${photo?.file.name}-${result.prediction}`} initial={reducedMotion ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: reducedMotion ? 0 : 0.18 }}>
          <div className="result-heading"><span className="result-icon"><Icon name={smiski ? "sparkle" : "image"} size={19} /></span><div><p className="result-eyebrow">The little verdict</p><h3>{smiski ? "Smiski spotted." : "Another little friend."}</h3></div><span className="result-dot" /></div>
          <p className="result-description">{smiski ? "The model thinks there’s a Smiski in this photo." : "The model thinks this is something other than a Smiski."}</p>
          <div className="score-label"><span>Model score</span><strong>{score}%</strong></div>
          <div className="score-track" role="meter" aria-label={`Model score for ${result.prediction}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Number(score)}><span style={{ width: `${score}%` }} /></div>
          <details className="score-explainer"><summary>A guess, not a guarantee.</summary><p>The score shows how strongly the model favors its guess. It isn’t a verified probability or an authenticity check. Similar toys, unusual lighting, and busy scenes can fool it.</p></details>
        </motion.div>}
      </AnimatePresence>
      <ExamplePicker loadingId={exampleLoading} selectedName={photo?.file.name} onSelect={example => void selectExample(example)} />
    </div>
  );
}
