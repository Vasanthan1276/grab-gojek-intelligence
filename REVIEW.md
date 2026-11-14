# Booking evidence and privacy review — 14 November 2026

Base commit: `e5f3d4340e2b1b1b45acd92351660087dce7901f` (10 August 2026). Review branch: `review/booking-evidence-privacy`. Owner approved publication, merge and deployment on 14 November 2026; release completion is recorded in the pull request.

## What was inspected

Repository source, public analytics, distance config, README/install notes, commit history, current Actions runs, and the live Pages interface. GitHub reports public visibility; the live site loads without authentication. The issue search returned no project issues. No raw PDFs, local private master, private aliases or backups exist in this checkout. No personal accounts or OneMap credentials were accessed.

The latest observed Actions were successful manual distance calculation/enrichment runs on 10 August. The latest observed Pages run used `950d6f8`, preceding two later distance commits on main. A successful distance workflow therefore is not proof that Pages serves that commit.

## Existing design and confirmed problems

| Area | Finding | Resolution / limit |
|---|---|---|
| Import | Grab uses column-oriented OCR with a date/amount row-count check. Gojek reads table cells and previously skipped malformed rows. | Gojek now fails with page/row references without receipt content; unknown currency stays unknown. OCR fidelity still requires private source validation. |
| Historical master | Local merge fingerprints use provider, minute timestamp, amount, currency and category, intentionally excluding address labels. Only analytics was backed up. | Conflicting timestamp matches now stop for reconciliation; existing master is also backed up. Minute collisions remain a documented limitation. |
| Directions | Routes used ordered origin/destination, so reverse directions were separate. | Direction retained and covered by tests. Reviewed full stop sequences now have distinct identities. |
| Multi-stop / V Place | V Place was an alias, but there was no ordered-stop field or multi-stop key; Gojek retained only the first cell line. | Full cell markers are checked before truncation. Ambiguous journeys are quarantined. Reviewed ordered stops supported; old records are explicitly unverified. Automatic stop reconstruction remains incomplete. |
| Classification | Metered text was recognised before Standard, but unrecognised Grab service text defaulted to Fixed. | Unrecognised service becomes Unknown. Existing aggregate classification cannot be revalidated without receipts. |
| Provider fallback | Alternative advice labelled its output Gojek/Grab even when selection returned route-wide statistics. Service fallback could also mix Fixed and Metered. | Strict same-provider/service selection. No numeric substitute on missing data. |
| Weekday scaling | Hourly statistics could be multiplied by a weekday mean ratio capped at ±15%, with no validation. | Removed along with the 0–5 score. Historical quantiles remain unadjusted. |
| Confidence | Sample count alone was labelled high/good confidence. | New sample-size labels and explicit absence of predictive validation. Classic timing wording also changed to observations. |
| Distance | All 56 public route keys had stored OneMap distance; values were rounded to 0.5 km. No actual journey distances or per-record calculation dates were available. | Preserve known distances; do not invent dates. Invalid/missing inputs are withheld. New calculation/carry-forward metadata supported. Multi-stop endpoint substitution prevented. |
| Privacy | 34 of 56 published routes contained one trip. Nested provider/hour/day groups also exposed singleton paid fares; historical trust bypassed sample thresholds. Unknown readable location labels could pass permissive checks. | Explicit approved location set, minimum five for fare groups, no individual min/max, no trust bypass. Eight routes remain public. |
| Other aggregates | Monthly cells had no sample counts; non-SGD subtotal included a known singleton; restaurant names were not checked against a public allowlist. | Withhold unverified monthly detail and small currency/restaurant detail. Overall supported spend totals remain. Reviewed builds can restore supported monthly cells using recorded counts. Missing cells are never zero. |
| Workflow safety | Deployment uploaded docs without checks. API error bodies and chained exceptions could expose sensitive request context. | Artifact checks and benchmark tests precede Pages publication. Sanitised distance errors, no response bodies or raw source filenames. Branch workflow runs tests only. |

The public-data change is a privacy migration of existing aggregates, **not a historical refresh**. Retained numeric fare observations and original history dates were not recomputed or overwritten. Old public data remains in Git history; this branch does not erase earlier exposure. Suppression is a mitigation, not formal anonymity or differential privacy.

## Dashboard behaviour

- Frequent routes lead to directional comparisons of Grab Fixed, Grab Metered and Gojek.
- Every supported card shows observation count, group used, middle 50%, median and date availability. Broader all-time fallbacks are labelled.
- Like-for-like provider comparisons use a shared hour/day/overall grouping; mismatched dates and conditions are stated. No causal best-time or always-cheaper claim.
- The stale-history banner separates receipt refresh from distance enrichment. Missing route dates, fare components and legacy stops are visible.
- A quote typed on the page is neither fetched nor saved. It is compared descriptively; absent service data returns insufficient data.
- Distance source, rounding, calculation status and S$/km limitations are visible.
- The Old Dashboard link retains classic route tables, charts, food summary and Ask My Data, with the same restricted dataset and corrected fare checker.

## Quote-logger proposal — not implemented

Recommended initial scope is an explicit opt-in on-device log. Record route aliases and ordered stops only; provider/service; observation timestamp; a quote amount or metered range; whether taxes/tolls/fees are included; promotions; selected option; and a separately recorded actual fare and date. Use a random local pair ID to associate near-simultaneous quotes and the later fare. Keep unbooked quotes rather than learning only from the chosen service.

The user must choose/approve persistent storage before implementation. Browser storage has device-access, shared-profile and backup risks and is not encrypted by this app. Include one-action delete/export controls and retention limits. Do not collect exact addresses, GPS, receipt images or provider credentials. Do not sync or publish log records. Missing actual fares stay missing; prediction/quote calibration needs enough paired observations and a held-out assessment.

## Added mobile location request

The follow-up request is implemented on the same local review branch. The page requests one GPS reading only after a tap, matches it against user-configured on-device place anchors, and uses the selected destination, exact direction/stop variant and current Singapore hour/day to select historical benchmarks. The optional remember checkbox stores only configured place points in this browser; it defaults off and has a forget control. No public coordinates, geocoding service, new backend, quote logger, provider connection or booking action was introduced. The dashboard sends no location data; browser/OS location services are outside its control.

Private aliases cannot be recognised from the public dataset alone: the user must identify them while at those places, or use manual selection. Locations worse than 100 m reported accuracy, older than two minutes, overlapping possible anchors or outside the conservative 250 m matching area do not silently select an origin. Unknown routes and missing service samples produce no fare. GPS proximity is not a driving distance or predictive model; all prior historical-data limitations remain.

Browser checks covered the manual starting-place/destination flow, current Singapore time selection, automatic focus/scroll to comparisons, privacy disclosure, unchecked-by-default remember control and forgetting. Desktop width was 1348 px; phone frames were 390/320 px (375/305 px content widths), with no horizontal overflow, including expanded setup. Actual GPS collection was not requested in the remote browser. Synthetic unit/integration tests cover GPS success and all error codes, ambiguity, expiry, fresh-read options, storage sanitisation/errors, explicit opt-in/deletion, unsupported routes and stop variants. A physical iPhone/Android permission and positioning check remains after approved deployment.

## Verification

28 Python tests and 38 JavaScript tests pass (66 total), using synthetic fixtures only. Public artifact validation and JavaScript syntax checks pass. Covered calculations, quantiles, currency separation, zero/missing/nonfinite values, direction, ordered stops, unverified stops, classification, duplicate conflicts, PDF parse failures, provider/service fallback, unchanged weekday statistics, privacy suppression, carried-forward distance dates, stale-history detection and the mobile-location cases above.

Browser checks cover the new desktop dashboard, quote comparison, absent-service state, route selection and classic route explorer. Responsive inspection uses browser-rendered 390 px and 320 px iframe viewports (content widths 375/305 px after scrollbars), not physical devices. Both have no horizontal page overflow. No Grab/Gojek application console errors were observed. The shared preview briefly switched to a different project; it was restored and final checks repeated. Errors from the other project and browser extension were excluded. Real receipt OCR, private-source reconciliation and live OneMap geocoding accuracy were not tested.

## Decisions still with the owner

1. Review and approve the branch before merging; merge to main triggers the existing Pages deployment workflow.
2. Decide whether to make the repository/site private or separately remediate old Git/log/cache exposure. This review does not change visibility or rewrite history.
3. Rebuild and reconcile locally with source receipts to verify stop sequences, service categories, currency and fare totals, and recover group date ranges/monthly sample counts.
4. Approve the quote logger's storage and retention approach before it is built.

Visual evidence is included in the downloadable review package and uses only the synthetic dataset in `tests/fixtures/dashboard-synthetic.json`; screenshot numbers are illustrative, not personal fares. Browser captures are kept out of the deployed site and source tree.
