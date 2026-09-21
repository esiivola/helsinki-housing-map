# Decisions and regression notes

## 2026-09-21 — no-layer keyboard inspection

- Type: browser-test regression fix
- Symptom: the fixture browser test expected keyboard selection to open a building inspector when no map layer was active.
- Root cause: hiding every building feature for `Ei karttatasoa` correctly leaves no rendered building to select.
- Fix: assert the no-building panel for the no-layer keyboard path, then select `Sopivuus` before the fixture's building-inspection checks.
- Rule for next time: keyboard-inspection expectations must respect the currently rendered map layers.

## 2026-09-21 — unique accessible map label

- Type: accessibility regression fix
- Symptom: the browser verification could not distinguish the focusable map from its settings section because both used the accessible name `Karttanäkymä`; returning focus after closing the inspector could also target the settings section.
- Root cause: the new compact map-control menu reused the map canvas label.
- Fix: name the control section `Karttanäkymän asetukset` and retain `Karttanäkymä` exclusively for the interactive map. Guarded by the fixture browser check in `web/scripts/verify-e2e.mjs`.
- Rule for next time: adjacent interactive regions must not share an accessible name when focus restoration needs a specific target.

## 2026-09-21 — scoped map-menu browser selectors

- Type: browser-test regression fix
- Symptom: E2E interaction with the map menu became ambiguous after adding the nested `Lisätiedot kartalla` disclosure.
- Root cause: the test selected every descendant `summary` instead of the menu's direct disclosure control.
- Fix: scope the selector to `:scope > summary`. Guarded by the complete fixture browser proof in `scripts/verify_e2e.sh`.
- Rule for next time: browser-test selectors for nested disclosures must target the intended depth.

## 2026-09-21 — mobile map menu pins to the bottom edge

- Type: responsive-layout regression fix
- Symptom: the open map menu did not reach the bottom edge at phone width.
- Root cause: its desktop `top: 16px` still applied alongside the mobile bottom-sheet positioning rule.
- Fix: reset `top` to `auto` while the menu is open on mobile. Guarded by the phone-viewport check in `scripts/verify_e2e.sh`.
- Rule for next time: a responsive bottom sheet must explicitly unset inherited opposite-edge positioning.

## 2026-09-21 — inspector copy test follows semantic markup

- Type: frontend regression fix
- Symptom: the frontend test failed after the area inspector moved headline numbers into semantic `strong` elements and shortened the open-ground wording.
- Root cause: assertions expected contiguous plain text and a retired sentence instead of the rendered semantic structure and approved copy.
- Fix: assert the rendered metric markup and the exact concise no-score message. Guarded by `web/src/app/App.test.tsx::shows area facts as values instead of a summary sentence` and `web/src/app/App.test.tsx::does not claim a score for open ground`.
- Rule for next time: when copy becomes structured UI, test the semantic output rather than a flattened prose sentence.

## 2026-09-20 — public layer-source provenance

- Type: release-validation bug fix
- Symptom: public layer metadata named sources that were absent from the published source manifest, leaving the service-information panel incomplete.
- Root cause: the release builder retained source IDs from generic layer definitions when their optional source snapshots were not admitted, and release verification checked evidence references but not layer references.
- Fix: filter published layer source IDs to admitted source manifests, make release verification reject unlisted layer sources, and align the checked-in public catalogues. Guarded by `tests/pipeline/test_release_verification.py::test_verify_release_rejects_a_layer_with_an_unlisted_source` and `tests/pipeline/test_hsy_release.py::test_hsy_release_exports_only_residential_buildings_and_year_evidence`.
- Rule for next time: every source ID in a published layer catalogue must be present in the same release's source manifest.

## 2026-09-12 — invalid geometry in sparse walking routes

- Type: data-coverage regression fix
- Symptom: an invalid source building geometry could receive a route distance of several thousand kilometres instead of an unknown value.
- Root cause: Shapely converted a non-finite geometry to a `(0, 0)` representative point before the sparse-route validity check.
- Fix: validate the source geometry before calculating its representative point; invalid or non-finite origins stay unknown. The direct route helper also rejects missing or non-finite points.
- Rule for next time: validate source geometry before deriving a representative coordinate for any nearest-node or routing calculation.

## 2026-09-10 — Prisma Tripla routing destination

- Type: data-coverage regression fix
- Symptom: Prisma Tripla was absent from the Prisma distance layer because the local 2026-08-25 OSM routing snapshot does not contain its node.
- Root cause: the store classifier used the snapshot as its only destination source, so a known source omission became a missing routing target.
- Fix: add the verified OSM point to the Prisma input only when the snapshot has no Prisma within roughly 25 metres; the same point is exported to the service-destination map overlay.
- Rule for next time: a verified material omission in an immutable routing snapshot must be an explicit, deduplicated supplementary destination with a regression test until the refreshed snapshot contains it.

## 2026-09-10 — keyboard map-selection fixture target

- Type: browser-test correction
- Symptom: the fixture-browser check timed out while expecting the empty-point panel after activating the map with Enter.
- Root cause: the fixture's default map centre is inside `fixture-building-1`, so keyboard selection correctly opens the building inspector rather than the empty-point panel.
- Fix: assert the building inspector and its Escape dismissal for the keyboard path.
- Rule for next time: derive a map-interaction assertion from the fixture geometry and map centre, rather than assuming the centre is empty.

## 2026-09-10 — Modal keyboard focus

- Type: accessibility bug fix
- Symptom: Settings and the service-information dialog left focus on their triggers and allowed keyboard navigation into the map behind them; Settings also ignored Escape.
- Root cause: the panels had incomplete dialog semantics and no focus-management behavior.
- Fix: use modal dialog semantics, trap Tab within the open dialog, move focus to its close button during the layout phase, retain the actual triggering control for focus restoration, and close both dialogs with Escape; `web/scripts/verify-e2e.mjs` checks the full interaction.
- Rule for next time: every modal surface must define its focus entry point, Tab boundary, Escape behavior, and focus restoration before release.

## 2026-09-10 — MapLibre control stylesheet and Finnish controls

- Type: bug fix
- Symptom: MapLibre zoom and compass controls rendered as unstyled, tiny elements and exposed English compass text.
- Root cause: `MapView` created MapLibre controls without importing the library's required base stylesheet.
- Fix: import the MapLibre stylesheet with the lazy map component, set Finnish control labels, and guard control size and labels in `web/scripts/verify-e2e.mjs` and `web/src/map/MapView.test.ts`.
- Rule for next time: a component that instantiates a third-party visual control must import or otherwise publish that control's required base styles in the same delivery path.

## 2026-09-09 — discrete morning-commute boarding legend

- Type: bug fix
- Symptom: the morning-commute median-boardings view combined distinct counts into overlapping numeric ranges such as `≤ 1` and `1–2`.
- Root cause: the shared numeric visualization treated a count-like boarding metric as a continuous, quantile-scaled value.
- Fix: render each supported boarding count (0–4 in this release) with its own half-step colour class and exact legend label, and publish future boarding values as distinct breaks; `web/src/map/MapView.test.ts::gives every median boarding count its own map-legend class` and `tests/pipeline/test_hsy_release.py::test_visualization_breaks_use_the_published_value_distribution` guard it.
- Rule for next time: count-valued layers whose individual values affect the decision must use discrete classes rather than continuous intervals.

## 2026-09-08 — transit-only morning range profile

- Type: bug fix
- Symptom: the first version-3 range batches stored almost entirely unknown minute samples because OTP returned only a direct walking itinerary at the range start.
- Root cause: the `planConnection` request left direct street routing enabled, allowing its itinerary filter to suppress the relevant transit alternatives.
- Fix: require `modes: {transitOnly: true}` in the range request and bump the batch detail version to 4; `tests/pipeline/test_transit.py::test_otp_range_query_pages_itineraries_until_the_search_window_is_complete` asserts the request mode.
- Rule: a transit layer's range query must require transit legs; never rely on the planner's default mode selection.

## 2026-09-08 — YAML date in morning transit range routing

- Type: bug fix
- Symptom: the range-routing batch stopped before its first route because `date.fromisoformat()` received the YAML-decoded `date` object.
- Root cause: the new range adapter assumed its service date was always a string, while `yaml.safe_load()` converts the configured ISO date to `datetime.date`.
- Fix: accept either form at the adapter boundary; `tests/pipeline/test_transit.py::test_range_router_accepts_the_service_date_type_loaded_from_yaml` covers the production configuration type.
- Rule: routing adapters receiving YAML configuration must accept the decoded Python type or normalize it before calling a string-only parser.

## 2026-09-05 — commute picker reflects the selected published layer

- Context: the completed release now includes the three Helsinki Central Station morning-commute layers, making 11 published destinations. The general map-layer picker also previously displayed `Sopivuus` while a commute layer was active.
- Root cause: the picker merged destination IDs from bike and transit layers before filtering by the selected mode, while the general picker removed every commute layer including the active one.
- Fix: derive destinations and the displayed count from the selected mode's published layer IDs, and retain the active commute layer in the general picker; `web/src/data/layers.test.ts` covers both behaviours and the 11-destination Central Station set.
- Rule: controls for optional derived layers must enumerate only the values represented by the currently selected published layer family, including the active value.

## 2026-09-05 — required split-tile availability index

- Symptom: release verification accepted a split-tile manifest that omitted the per-layer tile availability index.
- Root cause: the verifier substituted an empty index when the manifest field was absent.
- Fix: require the index for every split-tile release and test the rejected manifest shape.
- Rule: a release validator must require every field used to determine which published artifacts the browser may request.

## 2026-09-05 — split-tile audit metric

- Symptom: a release using split core and per-layer tiles reported its largest attribute tile as zero bytes.
- Root cause: the audit still searched the retired combined `tiles/attributes` directory.
- Fix: calculate the metric from both `tiles/core` and `tiles/layers`, with a release-export regression assertion.
- Rule: release audits must be updated together with every published artifact-path migration.

## 2026-09-05 — tile-index release compatibility

- Symptom: a frontend built with the per-layer tile availability index treated a prior release manifest with no index as if every layer had zero tiles.
- Root cause: manifest parsing collapsed an absent index into an empty object, losing the distinction between older complete layer tiles and an explicitly empty new index.
- Fix: preserve an absent index as `undefined`; then load requested layer tiles without index filtering only for that manifest shape.
- Rule: optional manifest fields that change loading semantics must preserve absence instead of substituting a value with a different meaning.

## 2026-09-05 — macOS-compatible resumable web release copy

- Symptom: the resumable web release stopped immediately after compiling because macOS `openrsync` rejected `--info=progress2`.
- Root cause: the script used a progress option available in newer rsync versions without checking the macOS-provided implementation.
- Fix: use the supported `--progress` flag while retaining `--partial --no-whole-file` for resumable delta transfer; add a shell regression check.
- Rule: release scripts must use options supported by the bundled macOS command-line implementation, unless they explicitly provision a newer tool.

## 2026-09-04 — completed workplace-commute publication

- Symptom: the release catalogue exposed morning-commute selectors for destinations whose batch files were still incomplete, yielding all-unknown map layers.
- Root cause: layer publication was based on the configured destination list rather than complete batch coverage.
- Fix: publish a transit destination only when its validated Parquet rows cover every scored building and every stored morning-departure sample; retain cycling layers for all configured destinations.
- Rule: a published transit layer must represent a completed destination batch, never an in-progress calculation.

## 2026-09-03 — resumable transit batches

- Symptom: restarting an interrupted workplace-commute calculation could recompute finished batches after an execution-only worker-count change; an interruption during a write could leave an invalid final file.
- Root cause: batch validation compared every routing configuration key, including `workers`, and wrote Parquet directly to its final path.
- Fix: validate outcome-affecting parameters only and write each new batch to a temporary Parquet file before atomically replacing its final path.
- Rule: execution settings must not invalidate derived results; resumable batch outputs must become visible only after a complete atomic write.

## 2026-09-03 — resumable green-cover aggregation

- Symptom: a late green-cover topology failure discarded hours of already calculated building values.
- Root cause: the release builder reused spatial indexes but retained all 300 m aggregation values only in memory.
- Fix: persist each completed 2 km building tile atomically under the local work directory; reuse it only when both source metadata and the tile's building geometry fingerprint match.
- Rule: expensive local spatial aggregation must checkpoint independently reproducible tiles outside the public release artifact.

## 2026-09-03 — invalid green-cover polygons

- Symptom: green-cover aggregation failed with a GEOS topology exception while unioning vegetation polygons.
- Root cause: a source polygon became invalid after projection, and the aggregation passed it unchanged to GEOS.
- Fix: repair only invalid candidate polygons before their union, with a bow-tie source-polygon regression test.
- Rule: externally supplied polygon geometry must be validated and repaired before topology operations; valid source geometry remains unchanged.

## 2026-09-02 — green-cover GeoJSON page separators

- Symptom: the local green-cover release build rejected every downloaded HSY GeoJSON snapshot as malformed.
- Root cause: the downloader omitted separators between the first 1,000 features of each file's first WFS page while the output file still had the expected header and closing bytes.
- Fix: serialize a page with a separator before every feature except the first feature of a new file, and cover both the first and later-page cases with a Node regression test.
- Rule: a resumable GeoJSON writer must serialize every page as a valid continuation of the existing feature array.

## 2026-09-01 — resumable green-cover snapshots

- Symptom: the downloader could misidentify a completed GeoJSON and start its layer again; it also accepted an unexpected empty WFS page as completion.
- Root cause: the header buffer was shorter than the expected GeoJSON prefix, and resumption did not validate partial-state continuity or the WFS matched-feature count.
- Fix: derive the prefix buffer size from the actual prefix, validate state plus partial contents before resuming, reject empty pages before the advertised final feature, and retry transient WFS gateway errors with bounded exponential backoff.
- Rule: resumable downloads must validate both their local byte boundary and the source’s advertised record boundary before finalizing.

## 2026-09-01 — removable criterion groups

- Symptom: users could add a criterion group but could not remove it, including an accidental empty group.
- Root cause: the replacement group editor implemented only criterion-level deletion.
- Fix: add a group-level delete action and a rendering regression check.
- Rule: every repeatable settings unit must provide its inverse action.

## 2026-09-01 — group soft-preference editing

- Symptom: entering one endpoint of a group’s linear soft preference could persist an incomplete or reversed interval and make scoring throw.
- Root cause: the group editor converted every keystroke directly into a persisted numeric preference, unlike the validated draft used by the retired layer editor.
- Fix: keep the two endpoint fields in local string state and write the preference only after both finite endpoints have the directionally valid order.
- Rule: multi-field numeric preferences must validate their complete value before being persisted or evaluated.

## 2026-08-31 — named profiles and mobile map controls

- Symptom: loading a named profile after a layer was retired restored invalid criteria; at phone width the map-layer picker covered a wrapped app-header description.
- Root cause: named-profile loading bypassed the existing layer-catalogue reconciliation, and the mobile picker used a desktop-sized fixed top offset.
- Fix: reconcile a loaded profile before making it the active draft; place the mobile picker below the maximum wrapped header height.
- Rule: every persisted preference document must be reconciled when applied to the active layer catalogue; mobile fixed controls must accommodate wrapped fixed-header content.

## 2026-08-31 — overlapping categorical source polygons

- Symptom: overlapping categorical source polygons could report building coverage above 100%.
- Root cause: categorical aggregation summed each polygon intersection independently, including duplicate same-category coverage.
- Fix: union source geometries within each category before intersecting the building footprint.
- Rule: categorical spatial coverage counts the union of same-category geometry, never the sum of overlapping features.

## 2026-08-30 — suitability legend and dealbreaker-only scoring

- Symptom: the visible suitability legend omitted the red hard-failure state and used a striped missing-data swatch while map fills were solid charcoal. Buildings with only passing hard requirements had no suitability score.
- Root cause: the continuous legend rendered only score steps and a CSS-only missing swatch; the scoring denominator intentionally excluded dealbreakers without defining an all-dealbreaker result.
- Fix: render red failure and solid-charcoal missing states in the same suitability legend list used by the map, and assign 100% only when every configured criterion is a known passing dealbreaker.
- Rule: each map display status must have an exact legend swatch; a complete set of passing hard requirements yields full suitability when no weighted criterion is configured.

## 2026-08-27 — zero-area building geometries

- Symptom: the Helsinki noise release crashed while calculating footprint coverage.
- Root cause: a projected HSY building geometry had zero area and the noise aggregator divided by its area.
- Fix: zero-area or empty buildings produce an explicit unknown noise value.
- Rule: every footprint-based layer must treat empty or zero-area geometry as unknown before calculating coverage.

## 2026-08-27 — individual transit router failures

- Symptom: one local routing timeout aborted the entire transit batch.
- Root cause: per-sample router exceptions escaped the building worker.
- Fix: route errors become failed samples, yielding partial or unknown values.
- Rule: a source query failure must remain local to its affected building/sample.

## 2026-08-28 — MapLibre worker missing from the static build

- Symptom: the local production build requested `maplibre-gl-worker.mjs` and received 404.
- Root cause: MapLibre's default relative worker URL does not cause Vite to emit the dependency worker asset.
- Fix: import the worker with Vite's `?url` asset handling and configure MapLibre with the emitted URL.
- Rule: every browser-worker dependency used by the static app must be emitted and verified from the production build.
# Static tile availability index

The tiled release publishes its finite z16 tile-key index in the manifest. Viewport loading filters requested keys through that index because a viewport naturally includes empty tiles; treating their absence as a failed data request stalls an otherwise valid load.

## 2026-08-28 — transit batch resumability

- Symptom: completed transit batches were recomputed on every script run.
- Root cause: the batch JSON validation block was accidentally placed after `json_safe()`'s return.
- Fix: restore validation inside `_valid_batch()` and test matching versus mismatching record counts.
- Rule: a resumability predicate must have a direct test for both reuse and recomputation.

## 2026-08-28 — transit GraphQL escaping

- Symptom: every transit sample became unknown despite valid local routing data.
- Root cause: the GraphQL query emitted literal backslashes before its date and time string quotes.
- Fix: emit GraphQL string quotes directly and fail visibly on top-level GraphQL errors.
- Rule: tests for generated GraphQL must assert the decoded outgoing query, not only mocked response handling.

## 2026-08-28 — retained transit samples

- Decision: sample the configured representative weekday every 15 minutes and retain the selected fastest itinerary locally in Parquet.
- Rationale: the current maximum journey metric and future minimum, transfer, and walking metrics can be derived without rerouting.
- Rule: the static release remains aggregate-only; per-sample routing artifacts remain local working data.

## 2026-08-29 — static E2E server missing assets

- Symptom: the performance-recording run crashed when the browser requested a missing optional static asset.
- Root cause: the local E2E server sent a successful response header before its asynchronous file read completed, then attempted to send a 404 after the read failed.
- Fix: read the file before sending the response header.
- Rule: a static file server must decide the response status only after the file read succeeds or fails.

## 2026-08-29 — performance report path

- Symptom: the otherwise successful fixture E2E run could not write its performance report.
- Root cause: the recorder passed a project-relative output path to a command executed from `web/`.
- Fix: resolve the retained report path before entering the web directory.
- Rule: pass absolute paths when a nested command is responsible for a repository-level artifact.

## 2026-08-29 — OTP internal routing errors in a transit batch

- Symptom: an OTP internal `/plan` error aborted an in-progress transit batch after completed batches had been written.
- Root cause: the detailed per-sample routing worker caught transport failures but not the adapter's explicit `RuntimeError` for a GraphQL error response.
- Fix: contain `RuntimeError` at both per-sample routing entry points and retain the affected sample as unknown.
- Rule: an individual local router response failure must not abort unrelated buildings or discard completed batches.

## 2026-08-29 — end-to-end proof command permissions

- Symptom: invoking `scripts/verify_e2e.sh` directly failed with `permission denied`.
- Root cause: the script's executable file mode was missing.
- Fix: restore executable mode and verify it with `test -x scripts/verify_e2e.sh`.
- Rule: the documented single-command release proof must remain executable.

## 2026-08-29 — nested layer information disclosure

- Symptom: the end-to-end test could not open a layer row after an `i` disclosure was added inside it.
- Root cause: its selector matched both the outer layer summary and the nested information summary.
- Fix: target the layer row's direct summary.
- Rule: UI tests must scope selectors when a control intentionally contains nested interactive disclosures.

## 2026-08-29 — settings panel placement

- Symptom: desktop settings opened on the opposite side of the map from their trigger, making opening and closing needlessly laborious.
- Root cause: the panel was anchored to the left while its trigger was fixed to the right.
- Fix: anchor the panel beneath the right-side trigger and provide an in-panel close button.
- Rule: a fixed panel must open beside its trigger and expose a local dismissal action.

## 2026-08-29 — fractional map zoom overview gaps

- Symptom: no overview was shown between integer zoom levels 12–13 and 15–16.
- Root cause: overview tiers used inclusive integer upper bounds while MapLibre reports fractional zoom values.
- Fix: an overview tier remains active until the next integer zoom level.
- Rule: map visibility tests must include fractional zoom boundaries.

## 2026-08-29 — map-layer control and units

- Symptom: changing map layers required opening Settings and then switching modes; numeric values could be selected or inspected without their unit.
- Root cause: map visualization was coupled to the preference panel, and unit rendering was not applied consistently outside the legend.
- Fix: expose one persistent map-layer selector and render numeric units in range controls, selected summaries, accepted ranges, and raw inspector values.
- Rule: map visualization remains a direct map control, and every user-facing numeric value includes its declared unit.

## 2026-08-29 — low-zoom layer summaries and visual language

- Symptom: overview cells showed only data coverage, so neither numeric values nor categorical composition could be compared at low zoom; raw-layer colors also implied an arbitrary direction.
- Root cause: overview exports omitted aggregate values, and one generic visual scale was used for unrelated measurement types.
- Fix: export numeric medians and categorical modes per overview cell, preserve tied modes as `mixed` with their share, use green-to-gray only for directional numeric layers, blue-to-gray for construction year, and a fixed non-subjective categorical palette.
- Rule: overview cells summarize raw evidence rather than suitability; every raw layer declares a visual meaning that is independent of user preferences.

## 2026-08-29 — local gzip data loading

- Symptom: the locally served map stayed gray and reported `Failed to fetch` for every gzip-compressed map artifact.
- Root cause: Vite automatically decoded `.gz` files while retaining the `Content-Encoding: gzip` response header; the browser loader then attempted a second decompression.
- Fix: read HTTP-decoded gzip responses directly and decompress only artifacts served as raw gzip bytes.
- Rule: static artifact loading must work both from production's raw gzip server and Vite's HTTP-decoded local development server.

## 2026-08-29 — overview legend and aggregation

- Decision: numeric overview tiles provide min, median, and max; median is the persisted default.
- Decision: numeric legends use one compact vertical scale with exact fixed-range values and a separate gray missing-data swatch; partial-coverage is not a legend state.
- Decision: categorical legends show each canonical category in the fixed qualitative palette, with `Sekoitus` and missing data in neutral grays.

## 2026-08-29 — distribution-based numeric map colours

- Symptom: equal-interval numeric ramps made most mapped values nearly indistinguishable, while the pale missing-data swatch resembled low values.
- Root cause: the visual range was driven by broad extrema rather than the released value distribution, and unknown evidence used a low-contrast neutral.
- Fix: publish fixed percentile stops from the release data; render stepped sequential scales, recalculate overview stops from the complete selected summary set, and use a patterned charcoal unknown swatch. Hard-criterion failures remain a distinct red state rather than being converted to zero points.
- Rule: numeric colours must use a fixed, non-viewport distribution scale; unknown and ineligible states must never share a colour with valid low values.

## 2026-08-30 — suitability overview, morning commute, and basemap

- Symptom: the low-zoom suitability view showed coverage rather than the active preference score, and the completed morning-commute calculation was not exposed in the service.
- Fix: overview cells carry compact per-building score inputs and calculate the selected minimum, median, or maximum suitability using the active preferences; building and overview suitability share the same green score scale, charcoal unknown state, and red hard-failure state. The completed 07.00–08.00, five-minute transit batches are published as a separate morning-commute layer.
- Decision: use CARTO Positron's vector basemap when a build-time `VITE_CARTO_KEY` is configured. The key is never included in the static source bundle; local development retains the bundled fallback basemap without it.

## 2026-08-30 — adaptive overview grid and good-value detail

- Symptom: overview cells were visually oversized at the upper end of their zoom range, while a five-class scale did not separate the most relevant good locations clearly enough.
- Fix: use 1,000 m cells at zoom 10, 500 m cells at zooms 11–12, 250 m cells at zooms 13–14, and building polygons from zoom 15. Continuous layers use seven classes; directional layers allocate more class boundaries toward the better end of their values.
- Decision: keep the grid no smaller than 250 m because it still summarizes multiple buildings (median four) and avoids turning the overview into a slower, less meaningful substitute for building polygons. Reinforce the basemap with coastline context while reducing overlay opacity.

## 2026-08-30 — stable range editing and contextual basemap

- Symptom: editing a newly selected numeric criterion could lose focus as its control moved between the available and configured lists; raw floating-point values also leaked into user-facing text.
- Root cause: configured status was derived immediately from the edited value, allowing the control to change list while it retained focus; formatting was applied inconsistently at individual display call sites.
- Fix: retain a criterion in its original list until focus leaves the control and apply Finnish one-decimal formatting to rendered numeric evidence, ranges, and percentage legends.
- Decision: retain CARTO Positron as the subdued thematic basemap, but promote coastline/lake outlines, rivers, canals, and railways from the offline OSM context data. Major roads remain present but subdued. The obsolete all-day transit layer is removed; the morning-commute layer is the single public-transit criterion.

## 2026-08-30 — workplace destination coordinates

- Symptom: manual validation against the local HSL GTFS stop snapshot showed that Keilaniemi, Aviapolis, and Tikkurila points were respectively off the named station/hub; Aviapolis incorrectly landed by Leppäsilta.
- Root cause: the initial workplace coordinates were entered from memory rather than verified against the routing snapshot.
- Fix: use the corresponding HSL GTFS station/hub coordinates and assert them in the transit configuration test.
- Rule: a configured transit destination must be checked against its named stop or hub in the same GTFS snapshot before a long batch computation starts.

## 2026-08-30 — transit batch parameter-aware resumption

- Symptom: after correcting a workplace destination, the resume check would have accepted a completed batch based solely on its row count.
- Root cause: the batch validator did not compare the stored routing parameters with the current destination coordinates.
- Fix: workplace batch validation now requires an exact match of the stored, JSON-normalized routing parameters; mismatched batches are recomputed while matching completed batches remain resumable.
- Rule: resumable derived-data artifacts must validate both their expected shape and the parameters that determine their values.

## 2026-09-01 — durable local OTP tool path

- Symptom: a resumable transit job could not restart because its OTP JAR had been kept under `/private/tmp`, which macOS cleared.
- Root cause: the documented command used ephemeral system storage for a required local build tool.
- Fix: document the official Maven Central JAR in `data/tools`, add its published checksum, and fail before reading input data when the JAR is missing.
- Rule: a documented local build-tool path must survive normal operating-system temporary-directory cleanup.

## 2026-09-05 — lazy overview score inputs

- Symptom: the default low-zoom map remained on the overview loading state while rendering thousands of cells.
- Root cause: overview merging allocated empty per-building score-input objects even when no selected visualization or criterion required them.
- Fix: omit `score_inputs` unless at least one overview layer partition is active; preserve them only for views that need preference evaluation.
- Rule: overview data paths must not allocate per-building state for inactive layers.

## 2026-09-08 — morning-range transit batch version guard

- Symptom: a stopped or pre-fix morning-range batch could have the expected row count while using an incompatible itinerary interpretation.
- Fix: release assembly requires the minute-level sample count and current itinerary-detail version before publishing workplace transit layers.
- Rule: derived routing artifacts must validate both their shape and their metric-definition version before publication.

## 2026-09-09 — streaming workplace-transit release aggregation

- Symptom: building the completed 11-destination morning-commute release spent its time repeatedly scanning the full building-ID list for every itinerary row, with no staging artifacts produced.
- Root cause: per-sample membership used a list instead of a set, making the aggregation quadratic in the number of buildings; it also retained all destination rows in memory.
- Fix: use a building-ID set and aggregate each Parquet batch immediately, retaining only the metrics needed for the published layers.
- Rule: a release reader over per-building batch data must use constant-time ID membership and must not retain raw rows after their batch has been summarized.

## 2026-09-09 — explicit distributions for fully unknown numeric layers

- Symptom: release verification rejected a complete export when a numeric layer had no known values and therefore no distribution entry.
- Root cause: distribution export skipped empty numeric layers, despite the verifier requiring every numeric layer to be represented.
- Fix: emit a zero-known distribution using the layer's established visualization bounds.
- Rule: a numeric layer with entirely unknown evidence remains a published, inspectable unknown layer and must retain explicit display metadata.

## 2026-09-09 — E2E inspector disclosure and provenance flow

- Symptom: the local browser E2E proof timed out after the map click succeeded, first for the fixture ID and then for its provenance link.
- Root cause: the assertions targeted content inside a collapsed raw-values disclosure, obsolete inline-provenance and criterion-group layouts, and left Settings open over the inspector. The current UI intentionally uses the service-information dialog for source links and presents individual criteria.
- Fix: assert the inspector heading first, open the disclosure, then verify the current land-ownership label and its source in the information dialog; close Settings before starting the independent inspector flow and exercise one individual mandatory criterion.
- Rule: browser tests must open a disclosure before asserting hidden content, exercise current accessible flows rather than retired markup, and close overlays before interacting with covered controls.

## 2026-09-09 — repeatable static loading baseline

- Result: the documented deterministic release-fixture run completed with 11 static requests and 1,717,527 bytes at cold start; switching among already loaded layers issued zero further static requests. On the Apple Silicon MacBook Pro reference machine, preference-update p95 was 14.36 ms and loaded-inspector p95 was 0.80 ms.
- Decision: retain the split building core/selected-layer tiles and split overview geometry/selected-layer summaries. The benchmark finds no evidence that a more complex binary format is warranted now.
- Scope: this is a repeatable local fixture baseline recorded in the release audit, not a measurement of a specific internet host, connection, or browser cache policy.

## 2026-09-10 — versioned service-destination staging requirement

- Symptom: the normal release script could reuse a verified staging bundle that predated the service-destination overlay and Prisma Tripla supplement.
- Root cause: staging reuse checked only the generic release shape and an unrelated health layer, not the new derived destination artifact or its routing input.
- Fix: require the service-destination overlay and the published Prisma Tripla point before reusing staging; otherwise rebuild it before synchronizing public data.
- Rule: a resumable static-data release must validate the feature-defining derived artifact and its concrete input, not only generic bundle validity.

## 2026-09-10 — shell wrapper invocation

- Symptom: `update_public_release.sh` stopped immediately with a permission error on a release helper.
- Root cause: the wrapper executed helper paths directly even though the documented workflow invokes them through `bash` and their executable bits are not guaranteed.
- Fix: invoke both helpers explicitly through `bash` and assert that invocation in the shell regression check.
- Rule: a shell wrapper must invoke project helper scripts through their documented interpreter unless executable permission is an explicit contract.

## 2026-09-10 — green-cover release preflight

- Symptom: a public-data rebuild spent several minutes exporting tiles before failing on a missing green-cover GeoJSON snapshot.
- Root cause: the release helper passed all configured green-cover paths to the pipeline without validating the local resumable downloads first.
- Fix: validate the five snapshots before any staging work and print the resumable downloader command on failure.
- Rule: an expensive release must validate every required local snapshot before creating or replacing staging artifacts.

## 2026-09-10 — one-command resumable public release

- Symptom: recovering from an interrupted green-cover download required manually running a downloader and then a separate release command.
- Root cause: the public-release wrapper started only after the required green-cover snapshots already existed.
- Fix: the wrapper resumes the green-cover downloader first, then reuses a validated data staging bundle and rsync's only changed web artifacts on later runs.
- Rule: a documented end-to-end release command must include every resumable prerequisite and preserve completed stages on rerun.

## 2026-09-11 — persistent HSY WFS retry

- Symptom: a green-cover download stopped after eight consecutive transient HSY 504 responses, requiring manual reruns despite its resumable checkpoint.
- Root cause: the downloader had a fixed retry limit for errors that are expected while HSY's WFS is under load.
- Fix: retry transient 429/502/503/504 and transport failures indefinitely with exponential backoff capped at 30 seconds; non-transient HTTP responses still fail immediately.
- Rule: a resumable bulk downloader must not give up on explicitly transient source-server failures while a safe user interrupt remains available.
## 2026-09-13 — Destination routing access and map explanation

Known point destinations use nearby pedestrian-network candidates within 150 metres. The reported walking distance includes the destination-to-network access leg, so this avoids isolated or wrong-side-of-road graph nodes without shortening a route. Destination overlays retain their published names and expose them in non-navigating marker and cluster popups. Composite-service and suitability histograms are calculated from the same full static building values and current preferences that drive the map.

## 2026-09-14 — Active-plan popup details

The active detailed-plan overlay publishes only the plan number, type, status, area, available approval entry, and source update date. Clicking a visible plan area shows these fields in a popup and takes precedence over building selection. The popup is descriptive only: it does not imply a construction timetable, scope, or disturbance forecast.
