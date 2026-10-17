# Attribution and provenance

- NumPy, SciPy and scikit-learn: numerical computation and classification,
  BSD-style upstream licences; joblib: BSD-3-Clause. Exact installed versions
  are recorded in requirements files and each model manifest.
- PyTorch: BSD-style licence; Transformers and Sentence Transformers:
  Apache-2.0. These are used only when running candidate B.
- `intfloat/multilingual-e5-small`: MIT, attributed to its upstream authors.
  [Model card](https://huggingface.co/intfloat/multilingual-e5-small).
  Downloaded weights are pinned to the commit stored in `revision.json` and
  copied with upstream model metadata. Declared multilingual coverage does not
  establish this task's Sinhala, Tamil or transliteration quality.
- pypdf: BSD-3-Clause, used to read the supplied competition PDFs.
- Source CSV: supplied by the user; origin and licence unknown. No assertion
  of redistribution rights is made. Keep the original, derived data and model
  bundles private pending review.
- Synthetic seeds: generated locally with OpenAI Codex during this session,
  fictional and unreviewed, restricted to training/testing and private review.
- No previous-phase code templates or weights were reused.
