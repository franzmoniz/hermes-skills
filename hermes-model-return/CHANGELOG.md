# Changelog - Hermes Model Return

## 1.0.0 - 2026-11-10
### Added
- First public version: on every prompt, while you are on a fallback model, tests the primary and the
  fallbacks above and switches to the best one that answers.
- A model you chose by hand (/model) is never changed: every 5th prompt you get a reminder (fallback:
  which better models are available; not a fallback: keep it or go back?).
