"use client";

import { useEffect, useRef, useState } from "react";
import {
  PHOTO_TYPES,
  predictionEndpoint,
  requestPrediction,
  validatePhoto,
  type PredictionResult,
} from "@/lib/prediction";

type Photo = { file: File; url: string };
type Example = { name: string; src: string };
const EXAMPLES: Example[] = [
  { name: "Smiski", src: "/examples/smiski.jpeg" },
  { name: "Sonny Angel", src: "/examples/sonny-angel.jpg" },
];

export default function DragDropImageBox() {
  const input = useRef<HTMLInputElement>(null);
  const dropButton = useRef<HTMLButtonElement>(null);
  const request = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const [photo, setPhoto] = useState<Photo | null>(null);
  const [phase, setPhase] = useState<"idle" | "preparing" | "predicting">(
    "idle",
  );
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [dragging, setDragging] = useState(false);
  const busy = phase !== "idle";

  useEffect(
    () => () => {
      generation.current += 1;
      request.current?.abort();
    },
    [],
  );

  useEffect(
    () => () => {
      if (photo) URL.revokeObjectURL(photo.url);
    },
    [photo],
  );

  function resetRequest() {
    request.current?.abort();
    generation.current += 1;
    setResult(null);
    setError(null);
    return generation.current;
  }

  async function selectPhoto(source: File | Example) {
    const current = resetRequest();
    const controller = new AbortController();
    request.current = controller;
    setPhase("preparing");
    let url: string | null = null;
    try {
      let file: File;
      if ("src" in source) {
        const signal = AbortSignal.any([
          controller.signal,
          AbortSignal.timeout(15_000),
        ]);
        const response = await fetch(source.src, { signal });
        if (!response.ok)
          throw new Error("Could not load the example. Please try again.");
        file = new File([await response.blob()], `${source.name}.jpg`, {
          type: "image/jpeg",
        });
      } else {
        file = source;
      }
      await validatePhoto(file);
      if (current !== generation.current) return;
      url = URL.createObjectURL(file);
      const image = new window.Image();
      image.src = url;
      await image.decode();
      if (current !== generation.current) return;
      setPhoto({ file, url });
      url = null; // The selected photo's effect now owns cleanup.
    } catch (caught) {
      if (current === generation.current) {
        setError(
          caught instanceof Error && caught.name !== "EncodingError"
            ? caught.message
            : "Could not open that photo. Please choose another image.",
        );
      }
    } finally {
      if (url) URL.revokeObjectURL(url);
      if (current === generation.current) setPhase("idle");
    }
  }

  function selectFiles(files: File[]) {
    if (!files.length) return;
    if (files.length !== 1) {
      resetRequest();
      setPhase("idle");
      setError("Please choose one photo at a time.");
      return;
    }
    void selectPhoto(files[0]);
  }

  function clearPhoto() {
    resetRequest();
    setPhoto(null);
    setPhase("idle");
    requestAnimationFrame(() => dropButton.current?.focus());
  }

  async function predict() {
    if (!photo || busy) return;
    const current = resetRequest();
    const controller = new AbortController();
    request.current = controller;
    const signal = AbortSignal.any([
      controller.signal,
      AbortSignal.timeout(180_000),
    ]);
    setPhase("predicting");
    try {
      const prediction = await requestPrediction(photo.file, {
        endpoint: predictionEndpoint(),
        signal,
      });
      if (current === generation.current) setResult(prediction);
    } catch (caught) {
      if (current === generation.current) {
        setError(
          signal.aborted && signal.reason?.name === "TimeoutError"
            ? "The request timed out. Please try again."
            : caught instanceof Error
              ? caught.message
              : "Could not classify the photo. Please try again.",
        );
      }
    } finally {
      if (current === generation.current) setPhase("idle");
    }
  }

  return (
    <section className="uploader" aria-label="Photo classification">
      <input
        ref={input}
        hidden
        type="file"
        accept={PHOTO_TYPES}
        onChange={(event) => {
          selectFiles(Array.from(event.target.files || []));
          event.currentTarget.value = "";
        }}
      />
      <button
        ref={dropButton}
        type="button"
        className={`drop-zone${dragging ? " dragging" : ""}`}
        aria-label={photo ? "Change photo" : "Choose a photo"}
        aria-describedby="upload-hint"
        onClick={() => input.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          selectFiles(Array.from(event.dataTransfer.files));
        }}
      >
        <strong>
          {dragging ? "Drop your photo here" : "Drag & drop a photo here"}
        </strong>
        <span>or click to {photo ? "replace it" : "browse"}</span>
        <small id="upload-hint">JPG, PNG or WebP · Up to 10 MB</small>
      </button>
      <div className="examples" aria-label="Example photos">
        <span>Or try:</span>
        {EXAMPLES.map((example) => (
          <button
            key={example.name}
            type="button"
            onClick={() => void selectPhoto(example)}
          >
            {example.name}
          </button>
        ))}
      </div>
      {photo && (
        <figure className="preview">
          {/* Browser object URLs are local previews, not Next.js image sources. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={photo.url} alt={`Selected photo: ${photo.file.name}`} />
          <figcaption>{photo.file.name}</figcaption>
        </figure>
      )}
      <div role="status" aria-live="polite" aria-atomic="true">
        {phase === "preparing" && <p className="feedback">Opening photo…</p>}
        {phase === "predicting" && (
          <p className="feedback">
            Classifying photo… The first request may take a minute while the
            server wakes up.
          </p>
        )}
        {result && (
          <div className="result">
            <h2>Prediction: {result.prediction}</h2>
            <p>Model score: {(result.confidence * 100).toFixed(1)}%</p>
            <small>
              A model guess, not a guarantee or an authenticity check.
            </small>
          </div>
        )}
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {photo && (
        <div className="actions">
          <button
            type="button"
            className="primary"
            disabled={busy}
            onClick={() => void predict()}
          >
            {phase === "predicting"
              ? "Classifying…"
              : error
                ? "Try again"
                : "Classify image"}
          </button>
          <button type="button" onClick={clearPhoto}>
            Clear
          </button>
        </div>
      )}
    </section>
  );
}
