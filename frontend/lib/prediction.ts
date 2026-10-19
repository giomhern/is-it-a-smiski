export type PredictionResult = {
  prediction: "Smiski" | "Non-Smiski";
  confidence: number;
  probabilities: { smiski: number; non_smiski: number };
};

export const MAX_PHOTO_BYTES = 10 * 1024 * 1024;
export const PHOTO_TYPES = "image/jpeg,image/png,image/webp";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function isProbability(value: unknown): value is number {
  return (
    typeof value === "number" &&
    Number.isFinite(value) &&
    value >= 0 &&
    value <= 1
  );
}

export function parsePrediction(value: unknown): PredictionResult {
  const message = "Could not read the prediction. Please try again.";
  if (
    !isRecord(value) ||
    (value.prediction !== "Smiski" && value.prediction !== "Non-Smiski") ||
    !isProbability(value.confidence) ||
    !isRecord(value.probabilities)
  )
    throw new Error(message);
  const { smiski, non_smiski } = value.probabilities;
  if (
    !isProbability(smiski) ||
    !isProbability(non_smiski) ||
    Math.abs(smiski + non_smiski - 1) > 0.001
  )
    throw new Error(message);
  const selected = value.prediction === "Smiski" ? smiski : non_smiski;
  if (Math.abs(selected - value.confidence) > 0.001 || selected < 0.5)
    throw new Error(message);
  return {
    prediction: value.prediction,
    confidence: value.confidence,
    probabilities: { smiski, non_smiski },
  };
}

export async function validatePhoto(file: File): Promise<void> {
  if (file.size === 0)
    throw new Error("That file is empty. Please choose another photo.");
  if (file.size > MAX_PHOTO_BYTES)
    throw new Error("Choose a photo under 10 MB.");
  if (file.type && !PHOTO_TYPES.split(",").includes(file.type))
    throw new Error(
      "Choose a JPG, PNG, or WebP photo. HEIC and SVG aren’t supported yet.",
    );
  const bytes = new Uint8Array(await file.slice(0, 12).arrayBuffer());
  const jpeg = bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
  const png = [137, 80, 78, 71, 13, 10, 26, 10].every(
    (value, index) => bytes[index] === value,
  );
  const webp =
    String.fromCharCode(...bytes.slice(0, 4)) === "RIFF" &&
    String.fromCharCode(...bytes.slice(8, 12)) === "WEBP";
  if (!jpeg && !png && !webp)
    throw new Error(
      "That doesn’t look like a supported photo. Try a different JPG, PNG, or WebP.",
    );
}

export function predictionEndpoint(): string {
  const base = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "");
  return base ? `${base}/api/predict` : "/api/predict";
}

export async function requestPrediction(
  file: File,
  {
    endpoint,
    signal,
    fetcher = fetch,
  }: {
    endpoint: string;
    signal: AbortSignal;
    fetcher?: typeof fetch;
  },
): Promise<PredictionResult> {
  signal.throwIfAborted();
  const body = new FormData();
  body.append("image", file);
  let response: Response;
  try {
    response = await fetcher(endpoint, { method: "POST", body, signal });
  } catch (error) {
    if (signal.aborted) throw signal.reason;
    if (error instanceof TypeError)
      throw new Error(
        "Could not reach the server. Check your connection and try again.",
      );
    throw error;
  }
  signal.throwIfAborted();
  if (!response.ok) {
    if (response.status === 429)
      throw new Error("The server is busy. Please try again later.");
    if (response.status === 413)
      throw new Error("That photo is too big. Choose one under 10 MB.");
    if (response.status >= 500)
      throw new Error(
        "The server is unavailable. Please try again in a moment.",
      );
    if (response.status === 400) {
      const payload: unknown = await response.json().catch(() => null);
      signal.throwIfAborted();
      if (
        isRecord(payload) &&
        typeof payload.error === "string" &&
        payload.error.length > 0 &&
        payload.error.length <= 200
      ) {
        throw new Error(payload.error);
      }
    }
    throw new Error(
      "Could not classify that photo. Please try a different image.",
    );
  }
  try {
    const value: unknown = await response.json();
    signal.throwIfAborted();
    return parsePrediction(value);
  } catch (error) {
    if (signal.aborted) throw signal.reason;
    if (error instanceof SyntaxError)
      throw new Error("Could not read the prediction. Please try again.");
    throw error;
  }
}
