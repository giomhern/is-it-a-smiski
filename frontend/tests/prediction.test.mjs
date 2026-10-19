import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import {
  MAX_PHOTO_BYTES,
  parsePrediction,
  requestPrediction,
  validatePhoto,
} from "../lib/prediction.ts";

const valid = {
  prediction: "Smiski",
  confidence: 0.9,
  probabilities: { smiski: 0.9, non_smiski: 0.1 },
};
const photo = new File(
  [await readFile(new URL("../public/examples/smiski.jpeg", import.meta.url))],
  "smiski.jpg",
  { type: "image/jpeg" },
);
const endpoint = "http://localhost:5050/api/predict";

// Real fixture bytes exercise content checks rather than trusting file extensions/MIME.
test("accepts the bundled JPEG and rejects disguised, empty, unsupported, and oversized files", async () => {
  await validatePhoto(photo);
  await assert.rejects(
    validatePhoto(
      new File(["not a photo"], "fake.jpg", { type: "image/jpeg" }),
    ),
    /doesn’t look like/,
  );
  await assert.rejects(
    validatePhoto(new File([], "empty.jpg", { type: "image/jpeg" })),
    /empty/,
  );
  await assert.rejects(
    validatePhoto(
      new File(["<svg/>"], "drawing.svg", { type: "image/svg+xml" }),
    ),
    /JPG, PNG, or WebP/,
  );
  await assert.rejects(
    validatePhoto(
      new File([new Uint8Array(MAX_PHOTO_BYTES + 1)], "large.jpg", {
        type: "image/jpeg",
      }),
    ),
    /under 10 MB/,
  );
});

test("rejects invalid probabilities and inconsistent server results", () => {
  assert.deepEqual(parsePrediction(valid), valid);
  for (const value of [
    null,
    {},
    { ...valid, confidence: Number.NaN },
    { ...valid, confidence: 2 },
    { ...valid, prediction: "Other" },
    { ...valid, probabilities: { smiski: 0.1, non_smiski: 0.9 } },
    { ...valid, probabilities: { smiski: 0.9, non_smiski: 0.9 } },
  ]) {
    assert.throws(() => parsePrediction(value), /Could not read/);
  }
});

test("uploads the selected image as multipart form data and validates the real response shape", async () => {
  const result = await requestPrediction(photo, {
    endpoint,
    signal: new AbortController().signal,
    fetcher: async (url, options) => {
      assert.equal(url, endpoint);
      assert.equal(options.method, "POST");
      assert.equal(options.body.get("image").name, "smiski.jpg");
      assert.equal(options.body.get("image").size, photo.size);
      return Response.json(valid);
    },
  });
  assert.deepEqual(result, valid);
});

test("network failure, backend failure, oversize response, and malformed response are actionable", async () => {
  const failures = [
    [
      async () => {
        throw new TypeError("Failed to fetch");
      },
      /Could not reach/,
    ],
    [
      async () => new Response("proxy unavailable", { status: 503 }),
      /unavailable/,
    ],
    [async () => new Response("too large", { status: 413 }), /under 10 MB/],
    [async () => new Response("<html>upstream error</html>"), /Could not read/],
    [async () => Response.json({ result: "wrong API" }), /Could not read/],
  ];
  for (const [fetcher, message] of failures) {
    await assert.rejects(
      requestPrediction(photo, {
        endpoint,
        signal: new AbortController().signal,
        fetcher,
      }),
      message,
    );
  }
});

test("a cancelled request cannot return a late response even when the transport ignores cancellation", async () => {
  const controller = new AbortController();
  let finish;
  const pending = requestPrediction(photo, {
    endpoint,
    signal: controller.signal,
    fetcher: () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  });
  controller.abort(new DOMException("Photo replaced", "AbortError"));
  finish(Response.json(valid));
  await assert.rejects(pending, { name: "AbortError" });
});

test("an already cancelled request sends no image", async () => {
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(
    requestPrediction(photo, {
      endpoint,
      signal: controller.signal,
      fetcher: () => {
        assert.fail("must not upload");
      },
    }),
    { name: "AbortError" },
  );
});

test("a timeout stays distinguishable from an offline error for the retry UI", async () => {
  await assert.rejects(
    requestPrediction(photo, {
      endpoint,
      signal: AbortSignal.timeout(10),
      fetcher: (_url, { signal }) =>
        new Promise((resolve, reject) => {
          const timer = setTimeout(() => resolve(Response.json(valid)), 100);
          signal.addEventListener(
            "abort",
            () => {
              clearTimeout(timer);
              reject(signal.reason);
            },
            { once: true },
          );
        }),
    }),
    { name: "TimeoutError" },
  );
});
