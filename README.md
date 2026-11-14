# Grab & Gojek Intelligence

A public static dashboard that compares manually entered app quotes with historical paid-fare observations. It does not fetch live prices, book rides, connect provider accounts, or run a validated predictive model.

The review branch preserves the classic interface at `docs/old-dashboard.html`, linked from the new dashboard. Both use the same restricted public data and benchmark rules.

## Current evidence

The checked-in history was last refreshed on **10 August 2026**, covering Grab records from 20 January–9 August 2026 and Gojek records from 30 July 2025–9 August 2026. The review did not import new receipts or change retained observed fares. Per-route/per-group dates, fare components and stop verification are absent from the old aggregates and remain unknown.

Eight routes meet the new minimum group size. Small route/provider/service/time groups and fare extremes are withheld. Legacy monthly cells lack sample counts, so monthly detail is withheld pending a reviewed private-history rebuild. Raw source files and the private transaction master are not in this repository. See [the review](REVIEW.md) for evidence, limitations and validation.

## Receipt processing

1. Keep PDFs under ignored `local_data/grab/` and `local_data/gojek/`. Configure ignored `config/private_aliases.json` with `setup_private_aliases.bat`.
2. Text-based Grab statements are read directly with PyMuPDF, including wrapped booking references. Their date window, transaction count and currency total must reconcile exactly. Image-only Grab statements use local Tesseract OCR; row-count mismatches stop the import. Gojek tables are read with pdfplumber; malformed rows stop the import rather than silently dropping transactions.
3. Normalise approved private aliases (`HOME`, `OFFICE`, `V_PLACE`, `COMPASSVALE`). Unknown location text remains private. Unknown currency or service is not guessed.
4. Merge with `local_private/transactions.json`. Exact overlapping records retain their additional source references without double counting. Conflicting values or distinct booking references at the same provider/category/timestamp stop for private reconciliation. The legacy minute timestamp identity can still collide; conflicts must be resolved against source receipts. Each provider's old date-window count and SGD total must reconcile with the existing dashboard before replacement; adding newer rides cannot hide missing older history.
5. Build directional route and provider/service/hour/weekday distributions, then enforce public-label and minimum-sample rules. SGD analytics exclude unknown and non-SGD currencies. Statement totals are not decomposed into invented fees or discounts.
6. Apply matching rounded route distances, validate public output and back up the existing master and analytics locally before replacement. All validation precedes writes. Multiple output-file replacements are sequential, not one database transaction.

Run `refresh_history.bat`, or `python scripts/refresh_history.py`. The old `process_reports.py` entry point delegates to the same validated pipeline. OCR still needs a local Tesseract installation. Review the private report and public diff before committing. Do not publish private backups, receipt filenames, raw text or coordinates.

Recovered private alias rules may use `equals` for exact, case-insensitive cleaned-text matches. This avoids a recovered place name unintentionally matching a longer unrelated address. Keep any source archive, row-level database and private reconciliation report outside the public repository. Retain original PDFs, source hashes and the earlier master when updating history.

## Routes and multi-stop journeys

A reviewed private row can contain `stops` in exact journey order, including its origin and final destination. `HOME → V_PLACE → OFFICE` is different from either direct leg and its reverse. Confirmed direct journeys are also kept separate from legacy endpoint-only groups whose stop coverage is unknown.

Explicit multi-stop markers in unreviewed import text are quarantined for local review. Their paid total remains part of overall spend but cannot contaminate a direct-route benchmark. The importers do **not** reliably reconstruct arbitrary ordered stops from PDFs. Older aggregates cannot be repaired without their sources. Do not mark a journey direct merely because no stop was detected.

New raw history builds calculate date ranges for each group. These cannot be retroactively inferred from the old public statistics.

## Benchmark selection

`docs/evidence.js` supplies the new and classic fare checkers:

1. Same route, provider and selected Grab service, at the requested hour, with at least five observations.
2. Same provider/service, at the requested weekday, if supported.
3. Same provider/service across all observed times, explicitly labelled.
4. Otherwise **insufficient data**. A missing Gojek, Metered or Premium benchmark cannot borrow Grab Fixed or an overall route average.

Hour and weekday are separate marginal groups, not a jointly matched sample. Cross-provider comparisons widen both sides to the same available grouping. Different dates and unobserved booking choices still prevent causal conclusions. Five observations are a display/privacy threshold, not validated predictive confidence.

Typical means historical median; middle 50% means observed p25–p75, not a future-price interval. The new cards round medians to whole dollars and ranges outwards. Quote values remain the amount typed by the user. The arbitrary weekday multiplier and 0–5 booking score have been removed.

## Distance and S$/km

OneMap geocodes approved aliases and calculates directional driving routes using existing workflow secrets. Public distance is rounded to 0.5 km and is **modelled route distance**, not measured trip distance. Cost/km is a historical fare statistic divided by that distance; it is not a separate prediction.

Missing, zero, nonfinite or invalid distances yield no cost/km. Verified multi-stop distance requires matching ordered stops; the network distance builder skips multi-stop routes until reviewed full-route distances are available. Never substitute a direct endpoint route. Newly calculated distances carry a calculation date; carried-forward values retain their old date and status. Legacy dates are unknown. Enrichment does not change the history refresh date.

Run **Build Route Distances**, then **Enrich Distance Metrics** after a reviewed history update. These are manual workflows. Bot-authored pushes may not trigger a Pages deployment; verify the deployed commit and explicitly run deployment only after approval. No credentials were read and no OneMap requests were made during this review.

## Privacy and deployment

The repository and Pages site are public. Five-record suppression reduces disclosure but does not guarantee anonymity: aggregates can still reveal habits, overlap can allow inference, and historical commits retain previously published data. Making the repository/site private or purging history is a separate owner decision.

Public validation rejects raw record fields, unknown place labels, unsafe fare groups, individual extremes and orphaned distance routes. HTTP response bodies, request URLs and source filenames are not printed by the revised import/distance paths. Existing logs and Git history have not been erased.

Pages publishes `docs/` on a push to main, or a manual run restricted to main. It now validates public artifacts and JavaScript tests before publication. Branches run tests without deployment. Do not merge or deploy the review without owner approval.

## Mobile: current location to historical fare estimate

The revised page has a **Use current location** button, destination selector and **Show historical fare estimate** action. Mobile browsers require a secure HTTPS page and the user's location permission. The existing HTTPS Pages URL can support this after the owner approves deployment. Adding the page to the phone's home screen is optional; there is no native app or offline guarantee.

1. On the first visit, choose starting place and destination manually, or open **Place setup & location privacy**.
2. While physically at Home, Office or another available alias, tap **Use current location**, choose that alias and tap **Set this spot as selected place**. No exact addresses or preloaded private coordinates are published.
3. Leave **Remember configured places on this device** off for session-only use. Turn it on explicitly to retain the configured points in this browser for later visits. Repeat setup when at other places you want recognised. **Forget all configured places** removes this feature's stored points and clears the active reading; it does not revoke browser permission.
4. For a later journey, tap **Use current location**, confirm the starting place, select the destination and show the estimate. This selects the exact directional historical route and the current Singapore hour/day. Multiple journey variants require choosing their ordered stops. The fare rules and sample thresholds above still apply.

`docs/location.js` performs local haversine proximity matching, **not road-distance or fare prediction**. A match must be within a 250 m radius after allowing for both the current and configured reading's reported accuracy; readings worse than 100 m or older than two minutes are rejected. Overlapping possible matches require manual selection. These conservative thresholds are implementation choices, not validated positioning guarantees. A location match expires after two minutes before a new estimate can be requested. Legacy stop uncertainty remains visible.

The dashboard makes one location request only on a tap; it does not watch movement, geocode coordinates, send them to an API, include them in URLs/logs, or store a location trail. The browser/OS may use its own location service. Opt-in storage contains only allowlisted alias/latitude/longitude/accuracy anchors under `ride-place-anchors-v1`; no quotes, trips or current-position history. This storage is not encrypted by the app and is shared with other pages on the same origin. Device/browser backups and access can expose it. Storage errors are reported, including when deletion cannot be confirmed.

Destinations are restricted to published route aliases. An unfamiliar origin, unsupported direction or insufficient provider/service history yields no numeric estimate. GPS does not create evidence for a new route, a live quote, surge conditions or a validated prediction. Actual iOS/Android GPS and permission behaviour still needs an owner check after an approved deployment.

## Manual quote logger: proposal only

Current quote entry is transient page state; no quote/trip logger was introduced. The optional location-anchor storage above is separate. A proposed opt-in, on-device logger could retain alias-only ordered routes, provider/service, quote timestamp or range, fee inclusions, selected option and subsequent final paid fare. It would need export/delete controls, clear device/back-up exposure warnings and explicit approval of logger storage. No GPS in log records, receipt uploads, provider login or background sync. See the proposal in [REVIEW.md](REVIEW.md).

## Checks

```sh
pip install -r requirements.txt
python -m unittest discover -s tests -v
node --test tests/*.test.js
python scripts/validate_public.py
```

Tests use synthetic records and mocked PDF/network/location responses. They cover route direction/stops, service classification, unknown amounts/currencies, duplicate conflicts, suppression, distances, benchmark fallbacks, freshness, GPS failure/ambiguity/expiry, local-storage opt-in/deletion and mobile booking selection. Real receipt OCR and live OneMap accuracy require a separate local review with the private sources.
