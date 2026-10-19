import type { CSSProperties } from "react";

type IconName = "arrow" | "upload" | "sparkle" | "close" | "check" | "image" | "retry" | "camera";

const paths: Record<IconName, React.ReactNode> = {
  arrow: <path d="M7 17 17 7M7 7h10v10" />,
  upload: <><path d="M12 16V4m-4 4 4-4 4 4M4 15v5h16v-5" /></>,
  sparkle: <><path d="m12 3 2.3 6.7L21 12l-6.7 2.3L12 21l-2.3-6.7L3 12l6.7-2.3L12 3Z" /><path d="m20 3 .5 1.5L22 5l-1.5.5L20 7l-.5-1.5L18 5l1.5-.5L20 3Z" /></>,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  check: <path d="m5 12 4 4L19 6" />,
  image: <><rect x="3" y="3" width="18" height="18" rx="3" /><circle cx="8.5" cy="8.5" r="1.5" /><path d="m21 15-5-5L5 21" /></>,
  retry: <><path d="M3 10a9 9 0 1 1 2 8M3 4v6h6" /></>,
  camera: <><path d="M3 7h4l2-3h6l2 3h4v13H3Z" /><circle cx="12" cy="13" r="4" /></>,
};

export default function Icon({ name, size = 20, className, style }: { name: IconName; size?: number; className?: string; style?: CSSProperties }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" className={className} style={style}>{paths[name]}</svg>;
}

export function BrandMark() {
  return <svg viewBox="0 0 40 40" fill="none" aria-hidden="true" focusable="false"><path d="M8 31V18a12 12 0 0 1 24 0v13l-6-3-6 3-6-3-6 3Z" fill="currentColor" /><circle cx="16" cy="18" r="1.4" fill="var(--paper)" /><circle cx="24" cy="18" r="1.4" fill="var(--paper)" /><path d="M18 23h4" stroke="var(--paper)" strokeWidth="1.5" strokeLinecap="round" /></svg>;
}
