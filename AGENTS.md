# Project instructions

## Product and scope

- Preserve the original simple interface: existing Smiski logo, centered heading, one upload area, preview, and prediction. Refine spacing, clarity, and accessibility; do not introduce a new brand, landing page, or visual system without an explicit request.
- Keep the main flow short: choose one photo, classify it, read the result, replace or clear it. Examples are a small optional shortcut.
- Treat model scores as uncalibrated scores. Do not imply authenticity verification or proven real-world accuracy.
- Complete authorized work and verify it locally. Keep the user informed of meaningful findings and limitations.

## Engineering standards

- Prefer the smallest correct implementation. Remove unused code, imports, assets, dependencies, configuration, and obsolete framework scaffolding after checking references.
- Do not add abstractions, generic options, component layers, or dependencies for hypothetical future needs. Use native browser and standard-library features when they are sufficient.
- Keep responsibilities clear. UI code handles interaction; API helpers validate responses; the API handles requests; model code handles inference; scripts handle training and evaluation.
- Derive values instead of storing redundant state. Preserve cancellation, timeouts, object-URL cleanup, and protection against stale async results when simplifying the upload flow.
- Use descriptive names, small focused functions, consistent formatting, and comments explaining non-obvious decisions. Avoid dense one-line logic and comments that repeat the code.
- Use strict TypeScript. Validate unknown data at external boundaries; do not use `any` or unchecked casts to silence errors.
- Use Prettier defaults for TypeScript/React/CSS and Ruff formatting/import sorting for Python; use maintenance tools without adding runtime dependencies.
- Follow PEP 8 in Python. Keep training-only work and optimizer initialization out of API startup and inference.
- Keep validation/inference preprocessing shared and deterministic. Do not alter checkpoint architecture, class ordering, preprocessing, or recorded model provenance as incidental cleanup.
- Keep useful test fixtures and checksum manifests in Git. Store generated dataset snapshots, per-image reports, and training metadata under ignored `data/` or in release assets; preserve historical provenance without duplicating artifacts in source.
- Keep dependencies declared in `pyproject.toml` and `frontend/package.json`; commit `uv.lock` and `frontend/package-lock.json`. Use Python 3.11 and Node 22.
- Keep code and text concise. Prefer README setup and essential model limitations over miscellaneous audit logs, release instructions, or duplicate reports. Do not add documentation that repeats other documentation.
- Make targeted changes; do not reformat unrelated files or replace working infrastructure.

## Accessibility and privacy

- Use semantic controls with keyboard access, visible focus, readable contrast, and accessible loading/error/result messages.
- Support small screens. Avoid hover-only actions and unnecessary animation; honor reduced-motion preferences if animation is introduced.
- Accept only documented image types/sizes. Validate on the server too; client validation is for usability.
- Do not persist uploaded photos, expose exception details, log image contents, or put credentials in client code.
- Keep `.env` files, raw datasets, model binaries, caches, and build outputs out of Git. Checkpoint downloads must verify their recorded checksums.

## Verification

Run checks relevant to the change, using the locked project environment:

```sh
# Backend changes; inference tests require the downloaded checkpoint.
uv run --locked python -m unittest discover -s tests/unit -v

# Frontend changes, from frontend/.
npm run lint
npm run typecheck
npm test
npm run build
```

- Add regression tests for meaningful behavior and bugs, not implementation details or trivial cosmetic changes.
- For UI changes, verify the real upload/example, prediction, replacement/clear, failure/retry, keyboard, and mobile paths where applicable. Never claim a browser check passed if it was blocked or not performed.
- Before removing code, search for its callers and update affected tests/docs. Keep tests aimed at the active production or training path rather than preserving obsolete code solely for its tests.
- Do not regenerate published dataset splits, revise historical test labels/results, retrain models, or replace release assets as part of routine cleanup.
- Keep README setup instructions accurate. Document material audit findings and remaining limits concisely.

## Commits and pushes

- Commit and push often, in small coherent working increments. Do not leave all work for one large final commit.
- Use Conventional Commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, or `chore:`, followed by a concise imperative description.
- Run the checks appropriate to each increment before committing. Run the complete relevant checks before the final push.
- Push to `git@github.com:giomhern/is-it-a-smiski.git` on `main`, unless the user specifies another branch or destination.
- Preserve unrelated user changes. Do not rewrite published history or force-push to clean up commit names.
- Do not commit secrets, raw photos, generated caches, checkpoints, or unrelated files. Model checkpoints belong in checksum-verified release assets.
- Leave the requested local preview running and provide its URL when the task includes a local demo.
