# TensorForge Buildathon Reusable Intelligence & MLOps Playbook

> A reusable, evidence-based reference distilled from the complete TensorForge 2.0 Phase 2 workspace: organizer resources, dataset notes, API contract, training notebooks and results, model artifacts, server/client implementations, tests, infrastructure, report, and demo deck.
>
> **Purpose:** help the team move quickly when the next phase introduces a **new problem, new guidelines, and a new product to pitch**. This is not a plan to continue, rebuild, or pitch the RideEat system. RideEat is retained only as a case study showing which working methods produced good evidence and a strong result.
>
> **Status:** reusable playbook plus Phase 2 evidence archive. The team’s second-place result is user-reported; technical claims below are tied to repository evidence. The next phase’s official material will become the new source of truth.

## 0. How to use this when the new challenge arrives

Do not begin by adapting the previous solution. Begin by replacing its assumptions.

1. Read the new guideline, rubric, dataset notes, API/schema files, submission rules, time limit, and pitch requirements.
2. Create a one-page **challenge brief** containing the new users, problem, inputs, outputs, constraints, forbidden approaches, judging criteria, deliverables, and deadlines.
3. Build a **requirement-to-evidence matrix**: every scored requirement must map to an implementation, a test, a measured result, and a pitch/demo proof.
4. Identify which practices in this playbook transfer. Contract testing, honest evaluation, artifact versioning, deployment parity, security, and demo rehearsal usually transfer; RideEat labels, thresholds, models, endpoints, AWS topology, and UI workflow do not transfer automatically.
5. Establish an evidence ledger and a minimal end-to-end baseline before pursuing sophisticated ideas.
6. Revisit the guideline after every major design decision. A technically impressive feature that does not improve the new rubric is a distraction.

### Reset checklist

Before allowing previous work to influence the new design, answer:

- What is explicitly scored this time?
- What is merely required as a gate?
- What data and inputs will exist at real inference/runtime time?
- What actions are prohibited?
- What must be live, hosted, reproducible, private, offline, or explainable?
- What are the judging hardware and time limits?
- What is the smallest end-to-end proof we can produce in the first few hours?
- Which previous assumptions are now invalid?

Treat all concrete Phase 2 details below as historical evidence unless the new organizers repeat them.

### Transfer filter

| Reuse by default | Re-evaluate from zero |
|---|---|
| Requirement traceability | Problem framing and target users |
| Evidence ledger and fixed acceptance criteria | Dataset, features, labels, and metrics |
| Simple baseline before complex approaches | Model family or whether ML is needed at all |
| Honest train/tune/test separation | API endpoints and response schemas |
| Versioned artifacts and reproducible builds | Cloud provider and deployment topology |
| Automated contract and failure-path testing | Batch/job architecture |
| Secret hygiene and least privilege | UI screens and workflow |
| Production-like performance tests | Language support and review thresholds |
| Rehearsed demo with fallbacks | Pitch claims, examples, and storyline |

### Fast-start challenge brief template

```markdown
# New Phase Challenge Brief

## Goal and user
- Problem:
- Primary user:
- Pain/value:
- One-sentence solution hypothesis:

## Official requirements
- Scored criteria:
- Pass/fail gates:
- Forbidden approaches:
- Required inputs/outputs or schema:
- Runtime/hardware/hosting constraints:
- Security/privacy constraints:
- Deliverables and deadline:
- Pitch/demo time and format:

## Evidence plan
- Simplest baseline:
- Primary metric:
- Guardrail metrics:
- Data splits or scenario sets:
- Locked final evaluation:
- Production-like test environment:

## Delivery plan
- Smallest end-to-end slice:
- Highest-risk unknowns:
- Owners and checkpoints:
- Freeze time:
- Demo fallback:
```

### Requirement-to-evidence template

| ID | New requirement / rubric item | Interpretation | Implementation | Verification | Evidence for pitch | Status |
|---|---|---|---|---|---|---|
| R1 | Quote or precise paraphrase | Testable meaning | Component/decision | Test or measurement | Number, screenshot, or demo step | Open |

This table should be created before implementation and updated continuously. It prevents important but unscored engineering from consuming the buildathon while a scored requirement remains unproven.

## 1. Executive intelligence

The strongest reason this project worked was not a single model or cloud service. It was the chain of evidence connecting the competition contract to the shipped behavior:

1. The official OpenAPI and JSON Schemas were treated as executable requirements, not documentation.
2. Data was investigated before modeling, and deployment constraints influenced model design from the start.
3. A classical baseline and multiple transformer challengers were compared on fixed splits.
4. Claims were made from held-out results, including failures and missed targets—not only favorable numbers.
5. Training and serving shared preprocessing, label mappings, decoding, thresholds, and business rules.
6. The selected model was packaged, hashed, versioned, embedded in the image, and verified during the Docker build.
7. Contract tests, model tests, browser tests, smoke tests, load tests, and deployment parity checks covered different failure modes.
8. The demo translated technical behavior into an operational workflow: classify, abstain, review, route, batch, monitor.

The reusable formula is:

> **Rules → measurable acceptance criteria → smallest viable baseline → controlled experiments → immutable artifact → contract-tested service → production-like verification → honest story.**

## 2. Source hierarchy: what future AI work should trust

When files disagree, use this order:

1. **Current organizer rules and machine-readable contracts**: latest guideline, OpenAPI document, and JSON Schemas.
2. **Final artifact metadata and measured results**: `training/models/winner/inference_config.json`, `metrics.json`, and `training/results/`.
3. **Current implementation and tests**: `app/server/`, `app/client/`, `infra/`, and their test suites.
4. **Final report and demo material**: useful narrative summaries, but numbers may predate last-minute test additions.
5. **Root/component READMEs**: operational documentation; verify numerical claims against result files.
6. **Architecture and training plans in `Resources/`**: valuable decision history, not necessarily the final design.

Examples of evolution that must not be misread:

- The early deployment plan proposed AWS App Runner. The implemented design uses EC2, CloudFront, ECR, CodeBuild, SSM, CloudWatch, and Amplify.
- The early frontend plan proposed a vanilla UI inside the API container. The shipped UI is a separate React/TypeScript static app on Amplify.
- The initial model plan proposed IndicBERT. Actual challengers included multilingual E5-small, MiniLM, and TF-IDF + logistic regression.
- Early calibration used `dev`; the final v1.2 artifact fits calibration and decoding thresholds on `val_cal` and reports once on `val_test`.
- Documents cite both 139 and 151 API tests, reflecting documentation drift. Treat the test runner/current test collection as authoritative. The independent runtime smoke suite records 55 checks.

**Reusable practice:** maintain one generated `evidence.json` or scorecard as the canonical source for the new project’s metrics, artifact version, test counts, performance results, and deployment identifiers; render reports and slides from it.

## 3. Phase 2 case study: what the previous problem required

This section preserves the old challenge so future work can understand *why* particular practices emerged. It does not describe the next buildathon problem.

The system classified fictional RideEat support tickets into:

- one of 11 primary categories and its fixed owning team;
- an optional secondary category, which must differ from the primary;
- an urgency flag;
- calibrated primary-category confidence;
- an optional human-review decision.

Inputs available at serving time were `channel`, optional `subject`, and `text`. Although the source dataset included `language`, the API did not send it, so it was correctly excluded as a feature and retained only for stratification and fairness/error analysis.

Key constraints that shaped the work:

- 4,000 training and 800 validation tickets;
- English, Sinhala, Tamil, Singlish, Tanglish, and mixed scripts;
- a 6:1 primary-class imbalance;
- only about 10% urgent tickets and 10% non-null secondary labels;
- 2 vCPU, 4 GB RAM, CPU only, no internet at runtime;
- authenticated synchronous and asynchronous inference;
- exact schema, status-code, ordering, consistency, and job-lifecycle behavior;
- a stable hosted HTTPS endpoint and locally runnable Docker image;
- scoring centered on correctness, schema compliance, and robustness rather than an LLM wrapper.

This led to the right optimization order: **contract correctness first, model quality second, operational robustness third, demo polish fourth**. Latency remained a pass/fail operational concern even when it was not a scored ranking metric.

## 4. Phase 2 contract lessons

The concrete endpoints and limits in this section belonged to Phase 2. Reuse the **method of extracting and testing a contract**, not these exact requirements, unless they appear again in the new guideline.

### Previous deliverables

- End-to-end solution and live dashboard.
- Hosted authenticated batch-inference API.
- Reproducible GitHub repository and one-command Docker runtime.
- Runtime that needs no internet.
- Up-to-15-minute demonstration video.
- Maximum-five-page report covering decisions, evaluation, and findings.

### Previous API behavior and the reusable lesson

- `GET /health` is public; protected endpoints require `X-API-Key` or bearer authentication.
- Health returns loading status until the model is ready and must become ready within the allowed startup window.
- `/predict/batch` accepts 1–100 tickets and preserves input order.
- Async jobs accept up to 5,000 tickets, validate the entire submission before acceptance, return quickly, expose monotonic progress, paginate ordered results, support cancellation/deletion, and retain terminal state.
- The same input and model version must yield the same prediction through single, batch, and job paths.
- Error evaluation order is deliberate: authentication → content type → payload size → JSON parsing → schema validation.
- Invalid input must produce the documented JSON error shape—not HTML, a traceback, or an accidental 5xx.
- `secondary_category` is always present and is `null` when absent.
- Spam must be non-urgent with no secondary category.
- Team must match the fixed category-to-team mapping.
- `model_version` must be non-empty, artifact-linked, and identical across health and prediction paths.
- Ticket text is untrusted data. Prompt-like content is classified, never followed as an instruction.

### Reusable key-handling practices

- Never place the organizer key in source, templates, model artifacts, screenshots, logs, browser bundles, or command examples containing the real value.
- Inject it through environment variables or a managed secret store. The implemented deployment used SSM SecureString.
- Refuse protected requests when the key is unset; never silently run an open service.
- Compare secrets in constant time and authenticate before reading or parsing the body.
- Keep the hosted key active throughout evaluation and rehearse rotation before the freeze window.
- In the browser, request the key at runtime; use session storage by default and explicit opt-in for persistent device storage.
- Scan the repository and built artifacts for secrets before delivery.

## 5. Data discipline and label intelligence

### EDA that materially affected design

- Verify schema, nulls, duplicates, text overlap, class balance, language balance, channels, subject availability, and character/token lengths.
- Parse CSV with a real RFC-compatible parser because quoted text can contain embedded newlines.
- Preserve UTF-8, combining marks, emoji, mixed scripts, messy spacing, transliteration, and speaker labels.
- Use both subject and body for email. Subject was absent outside email and therefore could not be a universal feature.
- The 99.5th percentile token length supported `max_length = 192`, avoiding an arbitrary 256-token cost.
- Stratify by category × language where possible to keep small linguistic groups visible.

### Important labeling rules

- A real safety incident takes primary precedence.
- A refund requested because food is late remains `delivery_delay` with refund as secondary; missing food remains `order_missing_wrong`; the charge dispute itself is `payment_refund`.
- OTP/login and promotions belong to `account_promo`; failures after login belong to `app_technical`.
- A left personal belonging is `lost_item`; absent delivery is `delivery_delay`; incomplete delivered contents are `order_missing_wrong`; food condition is `food_quality`.
- Partner onboarding and payout-information questions, plus genuinely vague issues, are `general_inquiry`.
- Urgency means immediate danger, active fraud, current medical symptoms, or a serious time-critical consequence. Anger alone is not urgency; a resolved historic safety complaint is not automatically urgent.
- Spam is never urgent and has no secondary label.
- Explicitly resolved quoted correspondence is background.

### Reusable data practices

- Write label rules before training and encode invariant rules once in shared code.
- Create adversarial fixtures for every ambiguous boundary.
- Separate data used for weight fitting, model/epoch selection, calibration/threshold fitting, and final reporting.
- Report subgroup sample size with every subgroup score; a percentage over 12 examples is a warning, not a conclusion.
- Preserve a small “known mistakes” set for demos, regression tests, and future data acquisition.
- Do not claim real-world readiness from synthetic data. The dataset notes explicitly say the multilingual text was synthetic and not independently reviewed by native speakers.

## 6. Evidence-based model development

### Implemented pipeline

Five ordered notebooks were backed by a shared `training/src/tfml/` library:

1. EDA and preprocessing.
2. XLM-RoBERTa baseline training.
3. transformer challengers plus a classical baseline.
4. comparison, CPU benchmarking, calibration, ONNX export, and quantization evaluation.
5. FP16-storage compression with fixed acceptance tests.

Training was resumable after every epoch—important for unreliable Colab sessions. Dependencies were pinned, seed 42 was recorded, and latency evaluation switched to CPU to resemble deployment.

### Final architecture

- One shared XLM-RoBERTa-base encoder.
- Three heads: 11-way category, 12-way secondary (`11 + none`), and binary urgency.
- Input pair: normalized `channel </s> subject` header plus ticket body.
- NFC normalization and whitespace collapse; body-only truncation where supported.
- Loss: `CE(category) + 0.5 × CE(secondary) + 0.3 × CE(urgency)`.
- Five epochs, AdamW, learning rate `2e-5`, batch 16, 10% warmup, weight decay `0.01`, mixed precision on T4.
- Category temperature `1.59546`, urgency threshold `0.425`, secondary threshold `0.4`, review threshold `0.7` in the shipped artifact.

### Why the experiment design was strong

- **Macro-F1, not accuracy alone:** appropriate for class imbalance.
- **Multi-task metrics:** category, secondary, urgency, exact match, and calibration were all measured.
- **Subgroup metrics:** per-language performance made transliteration weakness visible.
- **Deployment gates:** artifact size and CPU latency were considered alongside predictive quality.
- **A simple baseline:** TF-IDF + logistic regression revealed that a small classical model could outperform transformers on Singlish, a valuable ensemble clue.
- **Acceptance tests before optimization:** compression was accepted only if agreement and score deltas stayed inside fixed bounds.

### Model comparison evidence

Full-validation results reported by the final report/deck:

| Candidate | Category macro-F1 | Secondary F1 | Urgency F1 | Approx. size | Decision |
|---|---:|---:|---:|---:|---|
| XLM-RoBERTa-base | 0.814 | 0.890 | 0.943 | 1,059 MB FP32 | Winner |
| multilingual-e5-small | 0.729 | 0.458 | 0.229 | 448 MB | Faster, quality too low |
| TF-IDF + logistic regression | 0.625 | 0.621 | 0.874 | 5 MB | Strong sanity baseline; promising Singlish specialist |
| Multilingual MiniLM | 0.423 | 0.298 | 0.000 | 448 MB | Rejected |

The winner was selected with a weighted multi-task score and resource eligibility rather than one headline metric. A critical later correction was to stop treating the 30-second batch target as a scored selection term once the organizer guidance clarified it was not part of ranking.

## 7. Honest final evidence

The most defensible results are from `val_test`: 400 tickets never used for weight fitting, model choice, calibration, or threshold selection.

| Outcome | Held-out value |
|---|---:|
| Category accuracy | 0.803 |
| Category macro-F1 | **0.806** |
| Category weighted F1 | 0.810 |
| Secondary exact accuracy, including none | 0.983 |
| Secondary precision / recall / F1 when present | 1.000 / 0.821 / **0.901** |
| Urgency precision / recall / F1 | 0.917 / 0.971 / **0.943** |
| Exact match across all predicted targets | 0.790 |
| Calibration error (ECE) | **0.064**, down from 0.131 |
| Business-rule violations | 0 |

The calibration change is an exemplary evidence loop:

- Uncalibrated: mean confidence 0.931, ECE 0.131.
- Fitted on an over-easy dev split: mean confidence 0.968, ECE worsened to 0.165.
- Fitted on `val_cal`: mean confidence 0.830, ECE improved to 0.064, while category accuracy remained 0.803.

This shows why confidence must be validated separately from classification accuracy. Better calibration also made the review decision operationally meaningful.

### Results that should remain visible

- Category macro-F1 missed the team’s own 0.85 target by about 4.4 points.
- Dev performance near 0.99 did not generalize to validation near 0.81; dev was not representative enough for final claims.
- Singlish accuracy was about 0.67 and Tanglish about 0.50 on `val_test`, compared with English about 0.83. Tanglish had only 12 examples.
- Errors clustered between adjacent business concepts, especially missing/wrong order, food quality, delivery delay, payment/refund, and general inquiry.
- A known confident Tamil error classified a missing-item refund as `payment_refund`; the review flag did not catch it.
- The human-review threshold optimizes a risk/coverage tradeoff but cannot catch confident misclassifications.

These are not embarrassing footnotes. They define the next experiment backlog.

## 8. Optimization lesson: measure compression, do not assume it

| Artifact | Size | Category macro-F1 | Result |
|---|---:|---:|---|
| FP32 ONNX | ~1,059 MB | 0.814 | Accurate but large |
| Dynamic INT8 | ~266 MB | 0.711 | Rejected: about 10.3 points lost |
| FP16 storage, FP32 compute | ~530 MB | 0.814 | Shipped: half the size, no label changes |

The FP16-storage conversion had 100% agreement on category, secondary, urgency, and review decisions over all 800 validation tickets. Acceptance required at least 99.5% category agreement and no more than 0.005 degradation in macro-F1, secondary F1, urgency F1, or ECE.

Reusable rule:

> Never ship an optimization because it is theoretically faster or smaller. Define task-level acceptance checks first, measure the exact exported artifact, and retain the previous artifact for rollback.

## 9. Training-serving parity and artifact integrity

The model was not treated as a lone `.onnx` file. The winner bundle included:

- model graph;
- exact tokenizer files;
- ordered labels and category-to-team mapping;
- preprocessing/max-length configuration;
- temperature and decision thresholds;
- metrics and provenance;
- model SHA-256 and derived version;
- a torch-free runtime/decoder implementation.

Important practices:

- The version was derived from the artifact hash: `v1.2-558395869056`.
- Docker build verification checked required files, labels, importability, and model hash.
- The model and tokenizer were baked into the image, so runtime was offline and immutable.
- Decoder parity tests compared training rules with server rules.
- The exact exported tokenizer mattered: substituting the upstream tokenizer changed roughly 30% of predictions because header encoding differed.
- Single, synchronous batch, and async job paths used the same inference service and were tested for identical outputs.
- Large models used Git LFS; build checks detected an undownloaded LFS pointer early.

If the new solution contains a deployable model, package it as a manifest-addressed bundle and fail the build on any missing or mismatched component. For non-ML artifacts, apply the same principle to the configuration and assets needed at runtime.

## 10. Production-minded API design

### Useful architectural choices

- FastAPI and Pydantic for strict request/response behavior.
- ONNX Runtime with bounded CPU threads.
- One loaded classifier and one controlled inference lane to prevent memory multiplication and contention.
- Small job chunks so interactive requests do not wait behind an entire large batch.
- `/health` that does not invoke the model, keeping it responsive during jobs.
- SQLite in WAL mode for durable local job state under a one-container constraint.
- One running and three queued jobs, then `429` with `Retry-After`.
- Idempotency keys for safe client retries.
- Six-hour result retention, explicit `410` expiry, and interrupted-job recovery after restart.
- CORS as an explicit allowlist for the separately hosted client.
- Unprivileged container user and no secrets or ticket text in logs.

### Measured runtime evidence

On a local two-core-constrained setup using the shipped v1.2 model:

| Check | Measured |
|---|---:|
| Health ready after startup | 17 s |
| Single prediction p50 / p95 | 140 ms / 274 ms |
| Synchronous batch of 100 | 16.4 s |
| Submit 5,000-ticket job | 0.15 s |
| Complete 5,000-ticket job | 15.1 min (~5.5 tickets/s) |
| Health p95 during a job | 4 ms |
| Predict p95 / max during a job | 564 ms / 793 ms |
| Process RSS after large job | ~2.0 GB |
| Running-server contract smoke checks | 55/55 |

Hardware differences matter. The repository correctly recommended testing the deployed instance and both CPU architectures rather than assuming local numbers transfer.

## 11. Testing as layered evidence

No one test type proves readiness. This project used complementary layers:

- **Schema/contract tests:** official JSON Schemas validated real response bodies.
- **Unit tests:** validation, parsing, business rules, auth, configuration, and error formatting.
- **Lifecycle tests:** legal and monotonic job transitions, queue limits, idempotency, cancellation, expiry, and restart interruption.
- **Model integration tests:** multilingual scripts, emoji, prompt-injection text, long inputs, tokenizer fallback, determinism, and batch invariance.
- **Decoder parity tests:** training and serving produced the same decoded outputs.
- **Client tests:** CSV parsing and file validation, including embedded newlines and broken quotes.
- **Manual acceptance walkthrough:** exact inputs and expected UI outcomes for happy paths, failures, responsive layout, routing, CORS, restart, and export.
- **Smoke tests:** 55 checks against any running local or hosted endpoint.
- **Load tests:** latency and responsiveness while long jobs were active.
- **Cross-architecture parity:** same tickets on local amd64 and hosted arm64 had to match across five label fields.
- **End-to-end validation:** all 800 validation tickets through an API job matched notebook accuracy.

Best practice for the buildathon: convert every rubric item into at least one automated or rehearsed acceptance check, and keep one short command that answers “is this exact deployment ready?”

## 12. Deployment and operational practices

The implemented AWS design favored a stable endpoint and auditable artifact identity:

- CloudFront supplied HTTPS and a stable public API URL with caching disabled.
- EC2 matched the 2-vCPU/4-GB reference shape and ran the container under systemd.
- The security group restricted the origin port to CloudFront origin-facing addresses.
- ECR used immutable tags and scan-on-push.
- CodeBuild built amd64 and arm64 images inside AWS from a pushed commit, avoiding unreliable large uploads from a home connection.
- SSM handled the API key and instance access; no SSH port was needed.
- CloudWatch captured logs.
- Amplify hosted the static client and gated deployment on client tests and type-check/build.
- SAM/CloudFormation described infrastructure and a stack policy protected the stable URL resources.
- The same immutable image tag was checked in the registry and on the host.

Operational gates before submission:

1. Build from the exact pushed commit and verify Git LFS objects exist remotely.
2. Run the official-contract smoke suite against the hosted URL.
3. Compare local and hosted predictions for architecture parity.
4. Time synchronous and large asynchronous workloads on the actual instance.
5. Verify auth failure, TLS, CORS, model version, model hash, logs, restart behavior, and persistent job volume.
6. Freeze deployments, restarts, and OS changes during evaluation.
7. Maintain rollback instructions and an immutable previous image.

## 13. Demo and product design lessons

The UI was more than decoration; it made model governance visible:

- one-click multilingual samples reduced demo typing risk;
- confidence was shown against the 0.70 review threshold;
- urgent tickets, spam behavior, secondary issues, and human review were explicit;
- auto-routing applied only to confident tickets, while low-confidence tickets waited for a person;
- operators could override and reroute predictions;
- small batches used synchronous inference and larger files automatically became jobs;
- live progress followed server-provided retry timing;
- original columns were retained in exported CSV alongside predictions and routing audit fields;
- health and model version came from the live API, not fake dashboard counters;
- loading, unreachable, unauthenticated, malformed-file, queue-full, failed-job, and expired-result states all had designed UI behavior;
- keyboard access, text/icon redundancy, reduced motion, touch targets, responsive layout, and multilingual fonts were considered.

The key demo principle is: **show the risk controls, not only correct predictions**. A low-confidence abstention, an urgent escalation, a malformed input, and a recovering background job demonstrate production thinking more convincingly than a series of cherry-picked successes.

## 14. Buildathon execution playbook

### Before building

- Extract the rubric, hard constraints, forbidden approaches, required deliverables, judging environment, and time limits.
- Turn each requirement into a traceability row: source → implementation → test → evidence → demo moment.
- Identify which inputs exist in production; prohibit training-only fields from inference features.
- Define success metrics and minimum gates before experimenting.
- Choose a narrow user workflow and one memorable value statement.
- Establish the evidence ledger immediately: experiment ID, code/data/artifact version, hypothesis, metric, hardware, outcome, and decision.

### During the build

- Build the simplest end-to-end vertical slice first: input → baseline → API → minimal UI → deployment.
- Keep contracts and schemas under version control and test against them continuously.
- Centralize preprocessing, label order, decoding, and business rules.
- Compare at least one simple baseline with each sophisticated approach.
- Record rejected approaches and why; do not silently delete negative evidence.
- Use fixed splits and protect the final test set from iterative decisions.
- Make long-running work resumable and save checkpoints outside ephemeral compute.
- Version model and configuration together; derive identity from content where possible.
- Pin dependencies and build from lockfiles.
- Keep secrets outside source and built frontends.
- Add failure states and observability while features are built, not on the final night.
- Test on production-like CPU/memory/network constraints early.

### Before the judging freeze

- Run clean-room setup from the README on a fresh environment.
- Build the exact commit judges will receive.
- Run unit, integration, contract, model, client, smoke, load, and parity checks.
- Confirm hosted and local versions/hashes match.
- Rehearse the demo with the real hosted service, then rehearse an offline/fallback path.
- Capture evidence screenshots/video only after final verification.
- Validate all links, credentials, expiration dates, CORS origins, TLS, quotas, and billing.
- Prepare a concise known-limitations list and credible next experiments.
- Stop changing infrastructure during the evaluation window.

### Definition of done

A feature is done only when it has:

- a rubric or user need;
- an implemented happy path;
- explicit failure behavior;
- an automated or rehearsed test;
- measured evidence;
- documentation;
- a demo explanation;
- rollback or recovery behavior where applicable.

## 15. Reusable pitch intelligence

The next pitch must tell the story of the **new product**, not RideEat. The previous 15-slide deck is useful only because its causal narrative worked: problem → constraints → solution → live proof → design decisions → measured evidence → limitations. Rebuild every slide from the new guideline and new results.

### Recommended pitch spine

1. **Problem and stakes:** who loses time or takes risk today?
2. **One-sentence solution:** what the product does and for whom.
3. **Live workflow:** demonstrate one normal case, one risk-sensitive case, and one scale/failure case.
4. **Why it is credible:** data discipline, honest split design, comparison baseline, contract tests, and exact deployed artifact.
5. **Measured impact:** a small set of held-out model and operational metrics with denominators and hardware.
6. **Differentiation:** multilingual capability plus calibrated human review and production-grade delivery—not “we used AI.”
7. **Limitations and next move:** name the real weak spot and show the evidence-backed experiment that addresses it.
8. **Close:** repeat value, proof, and ask.

### Demo sequence that minimizes risk

Design the sequence after the new product’s core workflow is known:

1. Establish that the real deployed system is live and identify the exact version being shown.
2. Demonstrate the shortest normal journey from user input to useful outcome.
3. Demonstrate the new solution’s most differentiating capability.
4. Show one uncertainty, safety, validation, or failure path and how the product handles it responsibly.
5. Show scale or integration only if the new rubric values it.
6. Expose a small piece of raw evidence—a real API response, evaluation record, trace, or contract check—to prove the UI is not simulated.
7. Return to a prepared evidence slide rather than waiting for a long operation.

Use deterministic, rehearsed inputs and know their exact expected results. Keep a recorded demo, local fallback, screenshots, and cached evidence, but disclose when a fallback is being used. Do not force the previous classify/route/batch workflow onto an unrelated new product.

### How to speak about metrics

- Say “0.806 macro-F1 on 400 untouched tickets,” not “81% accurate.”
- Distinguish full-validation exploratory numbers from locked held-out reporting.
- State hardware beside latency.
- Show before/after metrics for each claimed improvement.
- Pair confidence/calibration with coverage or human-review rate.
- Avoid pretending a missed internal target passed. Explain what was learned and what would be tried next.

### Likely judge questions

Prepare new, evidence-backed answers to:

- Who has this problem, and how do you know it matters?
- Why is your chosen approach appropriate for the new constraints?
- What simpler baseline did you compare against?
- How did you prevent leakage or misleading evaluation?
- What happens on uncertain, malicious, malformed, or out-of-distribution input?
- What is the weakest scenario or subgroup and why?
- How are secrets, user data, logs, and generated outputs protected?
- Which approach or optimization did you reject, and what evidence drove that decision?
- Can another person reproduce the result from the submitted repository?
- What would you improve with one more week, and why is that the highest-value next step?

The Phase 2 repository demonstrates the *standard of evidence* expected in these answers, not the answers for the new system.

## 16. How to choose experiments for an unknown new challenge

Do not carry the RideEat improvement backlog into the new phase. Generate the experiment backlog from the new rubric, baseline errors, user workflow, and operating constraints.

Prioritize experiments using:

`priority = expected rubric impact × confidence in evidence × learning value ÷ implementation and validation cost`

For every proposed experiment, record:

- the problem or failure it addresses;
- the hypothesis;
- the unchanged baseline;
- the exact data split or test scenario;
- primary and guardrail metrics;
- compute/time budget;
- acceptance and rollback criteria;
- result, including negative outcomes;
- decision and next action.

Recommended experiment order for most new builds:

1. Establish a deterministic, end-to-end baseline.
2. Validate the data, labels, and evaluation method before tuning.
3. Fix the largest observed error category or user bottleneck.
4. Compare one simpler and one stronger alternative under the same conditions.
5. Test deployment feasibility on representative hardware.
6. Improve reliability, calibration, safety, or human handoff where the product needs it.
7. Optimize cost, latency, or size only after behavior is acceptable.
8. Freeze the candidate and run an untouched final evaluation.

Example format—not a target for the next challenge:

> “Technique X must improve the new primary metric by at least Δ, keep guardrail Y within its allowed regression, fit the latency/cost budget, and pass the same untouched scenario suite. Otherwise retain the baseline.”

## 17. Instructions for future AI-assisted development

When using this document as context, ask the AI to:

- begin from the newly supplied guidelines and explicitly list which old assumptions do not transfer;
- never assume the next task is ticket classification, multilingual NLP, routing, an API service, or AWS-hosted;
- distinguish organizer requirements, implemented facts, measurements, historical plans, and recommendations;
- inspect current source files before changing behavior;
- preserve the **new** official contract and its required validation/error behavior;
- use only features available to the new runtime system;
- keep development/evaluation and production behavior identical where parity matters;
- make no model-quality claim without naming split, sample size, metric, artifact version, and preferably hardware;
- create a locked final evaluation set for the new challenge and never tune on it;
- avoid exposing or inventing API keys;
- add or update tests and the evidence ledger with every material change;
- report failed acceptance criteria and tradeoffs explicitly;
- avoid replacing a measured working component merely because a newer technology sounds more impressive;
- check whether a referenced design document was superseded by implementation.

A useful task prompt pattern is:

> “The attached new-phase files are authoritative. Use `BUILDATHON_MLOPS_PLAYBOOK.md` only for reusable working practices and Phase 2 lessons—not as the new product specification. First summarize the new challenge, rubric, constraints, deliverables, and assumptions that differ from Phase 2. Then implement **[goal]** against measurable acceptance criteria. Add proportionate tests, run production-like verification, update the evidence record, and report both improvements and regressions. Do not expose secrets or tune on the locked final test set.”

## 18. Evidence map

| Evidence area | Primary repository sources |
|---|---|
| Competition rules and deliverables | `Resources/TensorForge2.0_Phase2_MVP_Guidelines.pdf`, `Resources/RESOURCES_SUMMARY.md` |
| API key handling | `TensorForge 2.0 – Phase 2- Official Team API Key & Handling Guidelines.pdf`, server/client/infra documentation |
| Dataset and labels | `Resources/TensorForge 2.0 - MVP Resources DataSet/DATA_NOTES.md`, dataset files, EDA notebook |
| Machine-readable contract | `app/server/contract/`, duplicate organizer copy under `Resources/API specs and schemas/` |
| Training pipeline | `training/notebooks/01–05`, `training/src/tfml/`, `training/README.md` |
| Final model evidence | `training/models/winner/inference_config.json`, `metrics.json`, `training/results/` |
| API behavior and tests | `app/server/tfengine/`, `app/server/tests/`, `app/server/scripts/smoke_test.py` |
| Client workflow and UX | `app/client/src/`, `app/client/README.md`, `app/client/TESTING.md`, test data |
| Infrastructure and operations | `infra/*.yaml`, `infra/scripts/`, `infra/README.md`, `amplify.yml` |
| Final narrative | Phase 2 report DOCX, demo deck PPTX, narration PDF, root `README.md` |
| Historical decisions | `Resources/model_training_plan.md`, `architecture_api_engine.md`, `architecture_frontend.md`, `architecture_aws_deployment.md` |

## 19. Final takeaway

The project’s competitive advantage was **traceability**. A judge could move from a rule to a test, from a metric to a result file, from a model version to a hash, from a dashboard result to the same API response, and from a deployment claim to infrastructure code.

For the next buildathon, preserve that discipline—not the old solution. Start with the new problem and its official rules, create the evidence ledger on day one, keep one authoritative scorecard, make the new product’s risk controls visible, and ensure every pitch claim is reproducible from the exact artifact being shown.
