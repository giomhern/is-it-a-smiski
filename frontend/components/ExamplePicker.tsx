"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import Icon from "@/components/Icon";

const EXAMPLES = [
  { id: "smiski", name: "Little Smiski", caption: "The usual suspect", src: "/examples/smiski.jpeg" },
  { id: "sonny-angel", name: "Sonny Angel", caption: "A familiar look-alike", src: "/examples/sonny-angel.jpg" },
];

export default function ExamplePicker({ onSelect, onError, disabled = false, selectedName }: {
  onSelect: (file: File) => void;
  onError: (message: string) => void;
  disabled?: boolean;
  selectedName?: string;
}) {
  const [loading, setLoading] = useState<string | null>(null);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);

  async function choose(example: typeof EXAMPLES[number]) {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setLoading(example.id);
    try {
      const response = await fetch(example.src, { signal: controller.signal });
      if (!response.ok) throw new Error("This example couldn’t load. Please try your own photo.");
      const blob = await response.blob();
      if (controller.signal.aborted) return;
      onSelect(new File([blob], `${example.id}-example.jpg`, { type: "image/jpeg" }));
    } catch (error) {
      if (!controller.signal.aborted) onError(error instanceof Error ? error.message : "Couldn’t load this example.");
    } finally {
      if (!controller.signal.aborted) setLoading(null);
    }
  }

  return (
    <div className="examples">
      <div className="examples-heading"><span>No photo handy?</span><span>Try an example <Icon name="arrow" size={12} /></span></div>
      <div className="example-options">
        {EXAMPLES.map(example => (
          <button className="example-button" type="button" key={example.id} disabled={disabled || loading !== null} onClick={() => choose(example)} aria-label={`Try the ${example.name} example`} aria-pressed={selectedName === `${example.id}-example.jpg`}>
            <Image src={example.src} width={43} height={43} alt="" />
            <span><strong>{example.name}</strong><small>{loading === example.id ? "Loading photo…" : example.caption}</small></span>
            <Icon name="arrow" size={14} />
          </button>
        ))}
      </div>
    </div>
  );
}
