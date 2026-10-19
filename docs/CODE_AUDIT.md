# Code audit — 2026-10-19

Scope: frontend interactions, assets/configuration/dependencies, Flask request handling, shared model code, dataset/training/evaluation scripts, and regression tests. Project standards are in [AGENTS.md](../AGENTS.md).

## Removed

- The expanded landing page, decorative icon/example components, animation, and duplicate UI state. The interface uses the original logo, centered heading, upload box, preview and result.
- Motion and the unused Tailwind/PostCSS configuration: 22 installed packages removed. Next.js still uses its patched PostCSS dependency internally.
- Unused Next.js starter images/favicon, empty configuration, remote font setup, and duplicate ignore rules.
- The unused Django application and management entry point. Flask is the active API.
- The superseded dataset loader and legacy training/validation loop. Training uses the versioned-snapshot workflow in `scripts/train_model.py`.
- Inference-time optimizer/loss initialization and unsupported model-selection/configuration options. Shared deterministic preprocessing is retained.

TypeScript/CSS follow Prettier formatting; Python imports and formatting follow Ruff. Formatting tools were run as maintenance tools, without adding runtime dependencies.

## Correctness fixes

- Requests accept one decoded JPG, PNG or WebP photo, capped at 10 MB and 40 megapixels. Filename/MIME alone cannot bypass format validation.
- Decode failures return 400; internal prediction failures return a generic 500. Server implementation details are not exposed.
- The UI preserves valid upload errors from the API and handles non-JSON responses, cancellation, timeouts and stale requests.
- Tests for the removed training loader now exercise partition selection in the active training script.

## Verification

- 23 backend tests and 8 frontend tests pass.
- Frontend lint, strict type checking, and production build pass. Ruff import/error checks and formatting checks pass.
- Reported first-load JavaScript is 111 KB, down from approximately 152 KB before UI simplification.
- Both published checkpoint files match their recorded checksums; real local API requests return the expected Smiski/Non-Smiski predictions for the two demo photos.
- The restored desktop interface was visually checked and captured in the README. HTTP checks confirm the production frontend and API are running locally.
- Automated phone-viewport/file-picker checks were not completed because browser tooling was unavailable/interrupted. A manual mobile/upload check remains useful before deployment.
- npm reports zero production dependency advisories. Five high-severity development dependency entries remain in the existing ESLint/braces chain; see the README's dependency maintenance note.

## Retained evidence and remaining work

Versioned dataset snapshots, model metadata, reports, fixtures and original branding are kept intentionally. Checkpoint weights and evaluation results were not regenerated or replaced during cleanup.

Dataset label review, an independent test collection, rate limiting, resource sizing and public hosting remain separate work. Existing model metrics and their limitations are documented in the [model card](MODEL_CARD.md).
