"use client";

import Image from "next/image";
import Icon from "@/components/Icon";

export const EXAMPLES = [
  { id: "smiski", name: "Little Smiski", caption: "The usual suspect", src: "/examples/smiski.jpeg" },
  { id: "sonny-angel", name: "Sonny Angel", caption: "A familiar look-alike", src: "/examples/sonny-angel.jpg" },
];
export type Example = typeof EXAMPLES[number];

export default function ExamplePicker({ onSelect, loadingId, selectedName }: {
  onSelect: (example: Example) => void;
  loadingId: string | null;
  selectedName?: string;
}) {
  return (
    <div className="examples">
      <div className="examples-heading"><span>No photo handy?</span><span>Try an example <Icon name="arrow" size={12} /></span></div>
      <div className="example-options">
        {EXAMPLES.map(example => (
          <button className="example-button" type="button" key={example.id} onClick={() => onSelect(example)} aria-label={`Try the ${example.name} example`} aria-pressed={selectedName === `${example.id}-example.jpg`}>
            <Image src={example.src} width={43} height={43} alt="" />
            <span><strong>{example.name}</strong><small>{loadingId === example.id ? "Loading photo…" : example.caption}</small></span>
            <Icon name="arrow" size={14} />
          </button>
        ))}
      </div>
    </div>
  );
}
