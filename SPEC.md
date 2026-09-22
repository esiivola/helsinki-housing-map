# Helsinki Metropolitan Apartment Location Explorer

## Product and technical specification

**Status:** Draft for review  
**Date:** 2026-08-26  
**Geographic scope:** Helsinki, Espoo, Vantaa, and Kauniainen  
**Delivery:** Static public website on GitHub Pages  
**Primary language:** Finnish  

This document supersedes the preliminary `spec.md` for implementation planning. The preliminary file remains source material and is not an implementation contract.

## 1. Outcome

Build a free, public, map-first tool for people and investors exploring where to live or buy an apartment in the Helsinki metropolitan area. The user defines acceptable ranges or categories for location-related facts, optionally assigns weights and dealbreakers, and explores:

- an overall suitability overlay on residential building polygons;
- any individual data layer;
- all available layer values, caveats, and provenance for a clicked location.

The product is an exploratory personal decision-support tool. It is not a property listing service, an authoritative title register, a valuation product, or a production-grade public-sector service.

## 2. Product principles

1. **Map first.** The map is the main interface; controls and details support it.
2. **Buildings are the decision unit.** Overall suitability is rendered only for residential building polygons.
3. **Raw facts stay inspectable.** Preferences do not destroy or replace source values.
4. **Simple, general rules.** Prefer one composable rule over layer-specific thresholds or exceptions. Do not introduce arbitrary rules such as ignoring overlaps below 2%.
5. **Unknown is data.** Missing or partial evidence is never silently converted to zero, failure, private ownership, or owned land.
6. **Transparent scoring.** No opaque machine learning or hidden ranking logic.
7. **Evidence over certainty.** Derived land-tenure and owner information must state what the evidence proves and what it does not prove.
8. **Static production.** All downloads, GIS intersections, routing, and aggregation happen offline. The deployed site has no application backend.
9. **Free and publishable inputs.** Production data must be free and permit the intended public use and redistribution. No paid licences or data-opening requests.
10. **Partial coverage is useful.** A layer may ship with visible gaps; there is no arbitrary coverage percentage launch gate.

## 3. Users and core journeys

### 3.1 Users

- A home seeker comparing areas or buildings against personal needs.
- An investor screening residential locations using the same transparent facts.

The app does not provide separate investor and resident modes in release 1.

### 3.2 Primary journey

1. The app opens on the metropolitan area with the overall suitability view.
2. The user enables relevant layers and sets an acceptable numeric range or accepted categories.
3. The user sets non-dealbreaker weights and optional dealbreakers.
4. The map updates building colours in the browser.
5. The user switches between overall suitability and individual layers.
6. The user clicks a building and sees its values, evaluations, source dates, caveats, and missing-data warnings.
7. The user's settings survive a reload in the same browser.

### 3.3 Point inspection

- Clicking a residential building selects the building and reports its aggregated values.
- Clicking a non-residential building or open ground does not produce an overall score. It reports any raw point-queryable source values available at that coordinate and explains that suitability is restricted to residential buildings.
- If several building polygons overlap the click because of source geometry, select the smallest polygon containing the point and disclose the ambiguity.

## 4. Release 1 scope

### 4.1 Required capabilities

- Residential building polygons as the canonical scored and rendered units.
- Overall suitability overlay and individual-layer visualization.
- Numeric ranges, categorical multi-select, weights, and dealbreakers.
- Explicit complete, partial, and unknown states.
- Global dealbreaker missing-data policy: `pass` or `fail`.
- Click inspector with raw values, exact mixed proportions, evaluation, methodology, source, licence, vintage, and caveats.
- Finnish interface; English technical identifiers in code and data schemas.
- Local preference persistence.
- Reproducible local Python data pipeline.
- Static frontend deployed to GitHub Pages.

### 4.2 Initial scored layers

| ID | Finnish label | Kind | Stored building value | Release 1 source strategy |
|---|---|---|---|---|
| `building_year` | Rakennusvuosi | numeric/multi-value | All known construction years associated with the building record | HSY metropolitan buildings |
| `house_type` | Talotyyppi | categorical/multi-value | Canonical values: `omakotitalo`, `paritalo`, `rivitalo`, `kerrostalo` | Helsinki building-register classification join; unmappable codes remain unknown |
| `elevator` | Hissi | categorical | `yes` when the Helsinki building register explicitly marks a lift; otherwise unknown | Helsinki building register only; a blank flag is not inferred to mean no lift |
| `heating_method` | Lämmitystapa | categorical | Canonical main-heating-method value | Helsinki building-register code mapping; unmapped codes remain unknown |
| `heating_energy_source` | Lämmitysenergian lähde | categorical | Canonical main heating-energy-source value | Helsinki building-register code mapping; unmapped codes remain unknown |
| `storey_count` | Kerrosluku | numeric | Registered building storey count | Helsinki building register only |
| `dwelling_count` | Asuinhuoneistojen määrä | numeric | Registered count of dwellings | Helsinki building register only |
| `land_owner_class` | Maanomistus | categorical | `city`, `non_city`, or `unknown` | Helsinki: local derived city-or-other classification. Espoo: positive full-footprint city-land evidence. See Section 7. |
| `noise_day_upper_db` | Päivämelun vyöhykkeen yläraja | numeric | Highest published upper dB bound among compatible daytime noise zones intersecting the footprint | Current municipality-specific strategic noise data where validated; documented fallback only. This is a conservative zone bound, not a building-level maximum. |
| `noise_night_upper_db` | Yömelun vyöhykkeen yläraja | numeric | Highest published upper dB bound among Helsinki `LAeq,22-7` zones intersecting the footprint | Helsinki 2022 national noise model at two-metre calculation height. This is a conservative zone bound, not a building-level maximum. |
| `active_planning_area` | Vireillä olevalla asemakaava-alueella | categorical | `yes` if the building footprint intersects a published active detailed-plan area, otherwise `no` | Helsinki active detailed-plan index only. It does not predict construction timing, scale, or disturbance. |
| `forest_walk_m` | Kävelymatka metsään | numeric | Shortest pedestrian-network distance to a source-designated forest polygon | OSM pedestrian network plus HSY/SYKE/OSM forest geometry |
| `shore_walk_m` | Kävelymatka merenrantaan | numeric | Shortest pedestrian-network distance to an accessible Baltic Sea shoreline destination | OSM pedestrian network and coastline/access evidence |
| `selected_education_service_walk_m` | Kävelymatka valittuihin kouluihin ja päiväkoteihin | numeric | Minimum pedestrian-network distance among user-selected `daycare`, `primary_school`, `lower_secondary_school`, `upper_secondary_school`, and `vocational_school` groups | Service Map snapshot plus OSM pedestrian network; browser combines precomputed group distances |
| `selected_health_service_walk_m` | Kävelymatka valittuihin terveys- ja sosiaalipalveluihin | numeric | Minimum pedestrian-network distance among user-selected health-centre, dental-care, neuvola, mental-health/substance-use, hospital, named-private-provider, other-private-clinic, and social-service groups | PTV physical-service-location snapshot and PTV service connections, supplemented by exact-name OSM locations for the three named private providers, plus OSM pedestrian network; browser combines precomputed group distances |
| `library_walk_m` | Kävelymatka kirjastoon | numeric | Shortest pedestrian-network distance to an OSM `amenity=library` destination | OSM snapshot |
| `transit_central_worst_min` | Pisin paras joukkoliikennematka keskustaan | numeric | Worst of the fastest scheduled journeys sampled every 15 minutes from 07:00 through 18:00 | Offline HSL GTFS routing plus OSM pedestrian network |
| `bike_central_min` | Pyöräilyaika keskustaan | numeric | Shortest bicycle-route travel time | Offline OSM-based bicycle routing |
| `selected_grocery_walk_m` | Kävelymatka valittuihin ruokakauppoihin | numeric | Minimum pedestrian-network distance among the user's selected grocery-store groups | OSM snapshot; browser combines precomputed retailer-group distances |
| `income_median_eur` | Mediaanitulot | numeric | Postal-area median disposable monetary income of households | Statistics Finland Paavo |

Every initial layer is independently visualizable. A source validation failure may produce unknown values but may not be replaced with fabricated values. Release 1 is complete only when every row has an implemented builder, manifest entry, UI definition, and caveat; sparse data is allowed.

### 4.3 Destination and route definitions

- **Central destination:** Helsinki Central Railway Station, stored as one configured coordinate and named in metadata.
- **Transit sampling:** every 15 minutes from 07:00 through 18:00 inclusive on a configured representative weekday contained in the downloaded GTFS validity window. The local working artifact stores the selected fastest itinerary for every building/sample: duration, transfers, walking time, and explicit failure state. The build manifest records the date, timezone, sampling interval, routing parameters, and failed samples. A building value is unknown if no sample routes successfully; otherwise it is the maximum duration among successful samples and carries a partial warning if any sample failed.
- **Walking origin:** a known building entrance connected to the pedestrian network; otherwise the closest routable point to the building boundary. The fallback is disclosed.
- **Cycling origin:** the closest routable point to the building boundary.
- **Selected grocery stores:** the UI presents Prisma, K-Citymarket, Lidl, S-market, K-Supermarket, Sale, K-Market, Alepa, other supermarkets, and other grocery/convenience stores. The pipeline precomputes one pedestrian-network distance per group. The browser uses the minimum known distance among the checked groups; it is unknown only when no checked group has known routing evidence. The static retailer-group values support this one user-facing composite layer and are not separately selectable.
- **Forest:** any polygon explicitly classified as forest/wood by the selected source. Release 1 applies no arbitrary minimum area.
- **Seashore:** the Baltic Sea coast, not inland lakes. A destination must be reachable on the pedestrian graph; a merely geometrically close but inaccessible shore does not qualify.

## 5. Explicitly out of scope

- Apartment listings, sale prices, price predictions, investment returns, or recommendations to buy.
- Apartment-unit facts such as unit size, condition, floor, maintenance charges, or view.
- A legally authoritative assertion of parcel ownership or lease status.
- Names or personal data of owners, tenants, or leaseholders.
- Authentication, accounts, cloud-saved profiles, collaboration, payments, or analytics requiring personal identifiers.
- Runtime server, database, GIS service, routing service, or required third-party API call.
- Shareable preference URLs in release 1.
- Native mobile apps, offline-first installation, 3D buildings, and real-time transit.
- User-defined scoring curves or machine-learned scores. Release 1 permits only the fixed, explainable two-endpoint linear preference in Section 10 for a layer explicitly declared lower-is-better or higher-is-better.
- Air pollution, safety/crime, language share, apartment-size distribution, bicycle-infrastructure quality, swimming halls, urban heat, flooding, construction disturbance beyond the published planning-area fact, and other proposed layers. They may be added later through the same layer interface.
- Republishing restricted data online.
- Paid Statistics Finland grid data, paid National Land Survey title/ownership products, or any other paid licence.

## 6. Architecture

```text
Free source snapshots
        |
        v
Local Python pipeline
download -> validate -> normalize -> route/intersect -> aggregate -> audit
        |
        v
Versioned static artifacts
building vector tiles + compact attributes + layer/source/distribution manifests
        |
        v
GitHub Pages
        |
        v
Browser
load visible data -> evaluate preferences -> style map -> inspect evidence
```

### 6.1 Runtime boundary

The browser may:

- load static tiles and attribute chunks;
- evaluate preferences and dealbreakers;
- calculate combined scores;
- style the map;
- look up a clicked feature;
- persist settings in `localStorage`.

The browser must not:

- intersect polygons or rasters;
- execute route searches;
- call source WFS/WMS/GTFS services;
- require a secret or API key;
- infer land ownership from missing evidence.

### 6.2 Recommended implementation stack

- Pipeline: Python, GeoPandas/Shapely-compatible geometry processing, Parquet for working data, and Pytest.
- Web: React, TypeScript, Vite, MapLibre GL JS.
- Published geometry: PMTiles or equivalently chunked vector tiles.
- Published attributes: compact, compressed, municipality/tile-partitioned static data with a documented schema.

These are implementation recommendations, not permission to add dependencies without review. The implementing agent must inspect the repository and propose dependencies before installing them.

## 7. Data sources, licences, and publication rules

### 7.1 Verified source catalogue

| Source | Intended use | Coverage | Publication basis and caveat |
|---|---|---|---|
| [HSY metropolitan buildings](https://hri.fi/data/fi/dataset/paakaupunkiseudun-rakennukset) | Building polygons, residential filtering, year, use/type | All four cities | CC BY 4.0; updated about every two weeks. The source notes uncertainty in some older building records. |
| [Helsinki open geographic data](https://www.hel.fi/en/decision-making/information-on-helsinki/maps-and-geospatial-data/make-better-use-of-geospatial-data/open-geographic-data) | Helsinki open geometry and supporting layers | Helsinki | City Survey open datasets are normally CC BY 4.0 unless a dataset says otherwise. A layer is usable only when its own catalogue entry confirms it is open. |
| [Vantaa property map](https://hri.fi/data/fi/dataset/vantaan-kiinteistokartta) | Positive lease-area evidence | Vantaa | CC BY 4.0, WFS/WMS. The map includes property, parcel, lease-area, and right-of-use boundaries, but its published attributes must be validated before classification. |
| [Helsinki traffic-noise zones](https://hri.fi/data/en_GB/dataset/helsingin-kaupungin-meluselvitys-2017) | 2022 daytime noise | Helsinki | CC BY 4.0; modeled zones are indicative and method/height must be shown. |
| [Espoo noise zones](https://hri.fi/data/en/dataset/espoon-melualueet) | 2022 daytime noise | Espoo | CC BY 4.0; modeled and indicative. |
| [Metropolitan traffic-noise zones](https://hri.fi/data/en_GB/dataset/paakaupunkiseudun-liikennemeluvyohykkeet) | Fallback only when a compatible current municipal layer is unavailable | All four cities | CC BY 4.0 but published in 2012. It must never be silently presented as current or mixed with incompatible metrics. |
| [HSY metropolitan land cover](https://hri.fi/data/en_GB/dataset/paakaupunkiseudun-maanpeiteaineisto) | Forest/vegetation evidence | All four cities | Open vector/raster data; use the exact release's stated attribution and licence. The 2022 product has classification and minimum-mapping-unit caveats. |
| [HSL open data](https://www.hsl.fi/en/hsl/open-data) | GTFS schedules and transport metadata | HSL service area | HSL data is CC BY 4.0; OSM-derived geometry/address content is ODbL. GTFS is published daily. |
| [OpenStreetMap copyright/licence](https://www.openstreetmap.org/copyright) | Walking/cycling network, coast, and service POIs | Study area | ODbL. Published derivative databases and attribution must comply with ODbL; the build records the extract date. |
| [Statistics Finland Paavo](https://stat.fi/fi/palvelut/tilastodatapalvelut/paikkatietoaineistot/postinumeroalueittainen-paikkatieto-paavo) | Median income | Postal areas | Free postal-area statistics. Suppressed values are marked `-1` and must become unknown. Postal-area values are coarse context, not building-level measurements. |
| [SYKE downloadable geospatial data](https://www.syke.fi/fi/ymparistotieto/ladattavat-paikkatietoaineistot) | Optional compatible environmental geometry | Finland/study area | Use only a dataset whose own metadata confirms an open licence and applicable vintage. |
| [Naapurustot.fi methodology](https://naapurustot.fi/en/data-sources/) | UX/methodology benchmark only | Postal areas | Not a production source. Useful precedent for visible provenance and renormalizing scores over available evidence. |

### 7.1.1 Concrete data, API, and supporting-evidence links

Metadata pages remain authoritative for licence and caveat checks. The following links are the concrete inputs or supporting references expected by source adapters. A service endpoint is not by itself proof that every layer exposed by that service is publishable; the adapter must still pass the source admission gate in Section 7.2.

| Source ID / purpose | Concrete links | Adapter note |
|---|---|---|
| `hsy_buildings` | [HSY dataset page](https://www.hsy.fi/ymparistotieto/avoindata/avoin-data---sivut/paakaupunkiseudun-rakennukset/), [HRI WFS resource](https://hri.fi/data/fi/dataset/paakaupunkiseudun-rakennukset/resource/81241625-f096-41c0-ad49-43fba2d92b9e), [HSY WFS](https://kartta.hsy.fi/geoserver/wfs), [WFS usage guide](https://www.hsy.fi/4a7f06/globalassets/ymparistotieto/tiedostot/hsy-rajapintaohje-wfs-saavutettava.pdf) | Request the `pks_rakennukset_paivittyva` layer. Resolve the current qualified feature name from GetCapabilities rather than assuming a namespace. |
| `helsinki_buildings` | [Dataset catalogue](https://avoindata.suomi.fi/data/fi/dataset/helsingin-rakennukset), [field metadata](https://kartta.hel.fi/avoindata/dokumentit/Rakennusrekisteri_avoindata_metatiedot_20160601.pdf), [code lists](https://kartta.hel.fi/avoindata/dokumentit/2017-01-10_Rakennusaineisto_avoindata_koodistot.pdf), [Helsinki WFS](https://kartta.hel.fi/ws/geoserver/avoindata/wfs) | Join by `vtj_prt`. Use `c_hissi`, `c_lammtapa`, `c_poltaine`, `i_kerrlkm`, and `i_asuinhuoneistojen_lkm` directly. This source covers Helsinki only; missing or unmapped values remain unknown. |
| `helsinki_active_plans` | [Dataset catalogue](https://avoindata.suomi.fi/data/fi/dataset/helsingin-kaupungin-ajantasa-asemakaava), [Helsinki WFS](https://kartta.hel.fi/ws/geoserver/avoindata/wfs) | Use `Kaavahakemisto_alue_kaava_vireilla` and preserve its active-plan status as an area fact, not a development forecast. |
| `helsinki_parcels` | [Dataset and field documentation](https://hri.fi/data/fi/dataset/helsingin-kiinteistot-alueina), [Helsinki WFS](https://kartta.hel.fi/ws/geoserver/avoindata/wfs), [Helsinki WMS](https://kartta.hel.fi/ws/geoserver/avoindata/wms), [published WFS layer list](https://kartta.hel.fi/avoindata/dokumentit/Aineistolista_wfs_avoindata.html) | WFS layer `Kiinteisto_alue` supplies parcel geometry and identifiers, not owner or tenure. |
| `vantaa_property_map` | [Vantaa WFS GetCapabilities](https://gis.vantaa.fi/geoserver/wfs?request=getCapabilities), [Vantaa WMS GetCapabilities](https://gis.vantaa.fi/geoserver/wms?request=GetCapabilities), [interface documentation](https://gis.vantaa.fi/rajapinnat/), [map view](https://kartta.vantaa.fi/link/76pfBf) | WFS/WMS layer `gis:kiinteistokartta`. Validate the `taso`/`teksti` encoding and isolate lease-area features; do not treat every property boundary as tenure evidence. |
| `helsinki_noise_2022` | [Noise dataset and layer names](https://hri.fi/data/en_GB/dataset/helsingin-kaupungin-meluselvitys-2017), [Helsinki WFS](https://kartta.hel.fi/ws/geoserver/avoindata/wfs), [Helsinki WMS](https://kartta.hel.fi/ws/geoserver/avoindata/wms) | Select a documented 2022 national daytime `LAeq,7-22` layer. Do not combine it numerically with `Lden` or a different calculation height/method. |
| `helsinki_noise_night_2022` | [Noise dataset and layer names](https://hri.fi/data/en_GB/dataset/helsingin-kaupungin-meluselvitys-2017), [Helsinki WFS](https://kartta.hel.fi/ws/geoserver/avoindata/wfs), [metadata](https://kartta.hel.fi/paikkatietohakemisto/metadata/?id=33) | Use the 2022 national combined-noise `LAeq,22-7` layer at two-metre calculation height. Do not combine it numerically with `Ln`, `Lden`, day values, or a different calculation method. |
| `espoo_noise_2022` | [Noise dataset](https://hri.fi/data/en/dataset/espoon-melualueet), [Espoo WMS GetCapabilities](https://kartat.espoo.fi/teklaogcweb/wms.ashx?request=GetCapabilities), [interface documentation](https://kartat.espoo.fi/Paikkatieto/files/WMS-ja_WFS-rajapintakuvaukset.pdf) | Select the documented 2022 national daytime road/rail layers and record how overlapping sources are combined. |
| `metro_noise_2012_fallback` | [Dataset](https://hri.fi/data/en_GB/dataset/paakaupunkiseudun-liikennemeluvyohykkeet), [downloadable Esri Shapefile resource](https://hri.fi/data/en_GB/dataset/paakaupunkiseudun-liikennemeluvyohykkeet/resource/c86e8a11-3ee7-4da7-bccc-f0675e1684a1) | All-four-city fallback with a prominent 2012-vintage warning. |
| `hsy_land_cover_2022` | [Dataset and resources](https://hri.fi/data/en_GB/dataset/paakaupunkiseudun-maanpeiteaineisto) | Prefer the native vector product where available. Record source resolution and mapping-unit caveats. |
| `syke_environment_candidates` | [Downloadable geospatial catalogue](https://www.syke.fi/fi/ymparistotieto/ladattavat-paikkatietoaineistot), [open environmental systems](https://www.syke.fi/fi/ymparistotieto/kartta-ja-tietopalvelut/avoimet-ymparistotietojarjestelmat), [Ryhti map](https://ryhti-palvelut.syke.fi/kartta), [Corine Land Cover 2018](https://luontotieto.syke.fi/aineisto/corine-maanpeite-2018/) | Candidate catalogue, not a blanket licence. Admit only the exact selected dataset after checking its own metadata and licence. |
| `hsl_gtfs` | [Current HSL GTFS ZIP](https://infopalvelut.storage.hsldev.com/gtfs/hsl.zip), [HSL open-data documentation and terms](https://www.hsl.fi/en/hsl/open-data) | Snapshot the ZIP and its retrieval time; route offline against a configured valid weekday. |
| `hsl_osm_extract` | [HSL-area OSM PBF](https://karttapalvelu.storage.hsldev.com/hsl.osm/hsl.osm.pbf), [OpenStreetMap copyright/licence](https://www.openstreetmap.org/copyright) | One reproducible OSM snapshot can supply pedestrian/cycling networks, service POIs, and coastline evidence. Preserve ODbL attribution and derivative-database obligations. |
| `paavo_income` | [Paavo dataset documentation](https://stat.fi/fi/palvelut/tilastodatapalvelut/paikkatietoaineistot/postinumeroalueittainen-paikkatieto-paavo), [Paavo WFS](https://geo.stat.fi/geoserver/postialue/wfs), [Paavo WMS](https://geo.stat.fi/geoserver/postialue/wms), [Paavo 2026 data description](https://stat.fi/media/uploads/tup/paavo/paavo2026_kuvaus_en.pdf) | Use the latest documented income field and convert protected value `-1` to unknown. Record the statistic year separately from the publication year. |
| `hri_terms` | [HRI terms of use](https://hri.fi/fi/kayttoehdot/), [CC BY 4.0 licence text](https://creativecommons.org/licenses/by/4.0/) | Retain dataset-specific attribution exactly; HRI catalogue inclusion does not override a resource-specific exception. |

No qualifying free, publishable Kauniainen plot-tenure or city-owner dataset was verified during specification work. The absence of a link is intentional: both land layers remain unknown there until a concrete source passes Section 7.2.

All source status and URLs were checked on 2026-08-26. Source services can change; each pipeline run must revalidate response shape and record the actual terms used.

### 7.2 Source admission gate

A source may enter a public build only if its manifest records:

- stable source ID and human-readable name;
- source and licence URLs;
- licence identifier and required attribution;
- retrieval timestamp and data vintage/validity period;
- geographic coverage;
- raw file checksum;
- source schema/version where available;
- processing method and caveats;
- redistribution decision: `allowed`, `derived_only`, or `excluded`, with rationale.

If licence or redistribution status is unclear, the source is excluded from the public build. An individual factual statement from an official public decision is not permission to republish an entire document database.

The public source manifest is the website's complete attribution and provenance list. Every source ID referenced by a published layer catalogue entry, including hidden input layers and map overlays, must occur exactly once in that manifest. A release with a missing, excluded, or unverified referenced source is invalid and must not be deployed.

Non-admitted inputs, and all raw, extracted, and derived artifacts from them, are excluded from public artifacts, including static web bundles, manifests, tiles, attributes, evidence, audit reports, and source downloads.

### 7.3 Land evidence model

The public map has one land layer: `land_owner_class`, with `city`, `non_city`, or `unknown`.

Finnish UI labels are **kaupunki**, **muu omistaja**, and **ei tietoa**. This reports a source-backed owner class; it does not report plot tenure, lease status, cadastral title, or a natural-person owner.

Helsinki values come from the local `building_ownership.csv` classification joined by building ID. Its rental details are derived from [Helsinki's public decision portal](https://paatokset.hel.fi/fi/). `kaupunki` is direct derived city evidence; `muu omistaja` is the maintainer's residual class and is deliberately shown with low confidence. The raw CSV and decision documents stay local. A public release may include only its building-level derived class, its checksum, and complete public-source provenance.

Espoo publishes `kaupunki` only where a licensed city-land polygon covers the complete building footprint. Absence from that polygon remains unknown, never `muu omistaja`. Vantaa and Kauniainen remain unknown until an admitted owner-class source is available.

Evidence precedence, highest first:

1. **Direct official statement:** a licensed/open record explicitly identifies the owner class.
2. **Official spatial overlay:** a licensed municipal polygon unambiguously intersects the relevant parcel/building.
3. **Documented derivation:** a maintained building-ID classification with auditable public-source provenance.
4. **No evidence:** unknown.

Rules:

- A licensed municipality-owned polygon supports `land_owner_class=city` only for complete building-footprint coverage.
- Helsinki's local classification can support `non_city` only with the derived-residual caveat and low confidence.
- Absence from any source remains unknown.
- Private individuals or organizations are never named in the public artifact.
- Conflicting positive evidence remains unresolved; the public builder must not choose silently.

## 8. Canonical spatial and value model

### 8.1 Building unit

`building_id` is the stable public identifier for a completed source building. Prefer the national permanent building identifier when present; otherwise generate a deterministic source-scoped identifier. Only buildings mapped to a supported residential house type or residential use are scored.

Building polygons remain in their source geometry. Do not replace them with a coarse grid. Raster or vector source layers remain in their native useful resolution until the offline aggregation step. Upsampling a coarse raster may aid geometry operations but must not imply greater information resolution; repeated/interpolated values retain the original resolution in metadata.

### 8.2 General spatial aggregation

For a source feature `s` and building footprint `b`:

`intersection_weight(s,b) = area(intersection(s,b)) / area(b)`

The pipeline calculates intersections once offline.

- Numeric polygon/raster values become an area-weighted mean over the building footprint's covered share.
- `noise_day_upper_db` is an explicit exception: its source supplies only interval bounds, so the pipeline stores the highest intersecting `db_hi` value. It never presents that value as an exact or measured building-level maximum.
- Categorical values become an exact distribution of category to footprint share.
- Uncovered footprint share is stored as `unknown_share`.
- One known category remains that category even if coverage is partial; the partial coverage is separately visible.
- Multiple conflicting known categories produce the canonical category `mixed`; exact proportions remain inspectable.
- No overlap is discarded merely because it is small.
- Invalid geometry is repaired by one documented common routine or quarantined as unknown; it is not handled with layer-specific guesses.

For point-derived, route-derived, or administrative-area values, the layer builder declares its own documented assignment operation. The frontend receives the result and does not repeat GIS computation.

### 8.3 Value representation

Each building-layer value has:

| Field | Meaning |
|---|---|
| `state` | `known`, `partial`, `unknown`, or `conflict` |
| `kind` | `scalar`, `multi`, or `distribution` |
| `value` | Canonical scalar/category when one exists |
| `values` | Exact source values for a multi-value fact |
| `distribution` | Category/value shares for spatial mixtures |
| `coverage` | Share from 0 through 1 supported by known source data |
| `evidence_ids` | References into the evidence table |
| `method` | `direct`, `aggregated`, `derived`, or `inferred` |
| `confidence` | `high`, `medium`, or `low`, with layer-defined meaning |

No numeric sentinel is used for missing values. Source sentinels such as Paavo `-1` are normalized to `state=unknown`.

### 8.4 Multi-value semantics

If a building contains exact values such as construction years 1940 and 1970, both are stored and shown. A configured acceptable range passes when **any** exact value is inside it. It therefore passes both 1930–1950 and 1960–1980, and fails 1950–1960. The UI labels this rule “at least one value matches.”

Spatially mixed categorical facts are not evaluated with hidden percentage thresholds. Their canonical value is `mixed`, which the user may explicitly accept; the inspector shows all shares.

## 9. Layer and source interfaces

These logical interfaces are implementation contracts; exact syntax may follow the selected language conventions.

### 9.1 Pipeline interfaces

| Interface | Responsibility |
|---|---|
| `SourceAdapter.fetch(snapshot_config) -> RawArtifact[]` | Download/cache immutable raw inputs and return checksums plus metadata. |
| `SourceAdapter.validate(raw_artifacts) -> ValidationReport` | Verify schema, CRS, required fields, coverage, licence metadata, and known sentinels. |
| `LayerBuilder.build(build_context) -> LayerArtifact` | Normalize one layer and produce building values plus evidence. |
| `SpatialAggregator.numeric(buildings, source) -> BuildingValue[]` | Apply common area-weighted numeric aggregation. |
| `SpatialAggregator.categorical(buildings, source) -> BuildingValue[]` | Apply common categorical distribution aggregation. |
| `ArtifactValidator.validate(release) -> ReleaseReport` | Enforce schemas, referential integrity, ranges, provenance, and public-data rules. |
| `WebExporter.export(release) -> StaticBundle` | Produce tiles, attribute chunks, manifests, and attribution used by the frontend. |

Every layer builder is registered declaratively. Adding a normal numeric or categorical layer must not require changing scoring or generic control components.

### 9.2 Frontend interfaces

| Interface | Responsibility |
|---|---|
| `loadManifest() -> AppManifest` | Load schema version, layer catalogue, release metadata, and data partitions. |
| `loadBuildings(viewport) -> BuildingFeature[]` | Load only geometry needed by the visible map and supported zooms. |
| `loadAttributes(partitionIds) -> BuildingAttributes` | Load compact values for the needed partitions. |
| `evaluateLayer(value, definition, preference, missingPolicy) -> LayerEvaluation` | Return configured state, pass/fail/unknown, and binary score. |
| `evaluateBuilding(attributes, preferences, missingPolicy) -> BuildingEvaluation` | Return eligibility, weighted score, missing warnings, and per-layer evaluations. |
| `inspectPoint(lngLat) -> InspectionResult` | Resolve a building or raw point result without network requests. |
| `serializePreferences()` / `restorePreferences()` | Persist versioned local settings and safely migrate or reset incompatible data. |

### 9.3 Core frontend records

- `LayerDefinition`: ID, Finnish label, description, kind, unit, formatter, allowed categories/range, default preference, visualization scale, fixed numeric visualization range, methodology, caveat IDs, and source IDs.
- `LayerPreference`: enabled flag, acceptable minimum/maximum or accepted categories, weight, and dealbreaker flag.
- `BuildingEvaluation`: eligibility, score or null, failed dealbreakers, missing enabled layers, and per-layer results.
- `EvidenceRecord`: evidence ID, source ID, source URL, retrieved/vintage dates, method, confidence, normalized factual claim, and caveat IDs.
- `AppManifest`: schema and release versions, build timestamp, study boundary, partition index, layer definitions, source manifest link, and attribution text.

Schema compatibility is explicit. The frontend must reject an unsupported major schema version with a readable message instead of partially rendering it.

## 10. Preference and scoring semantics

### 10.1 Configured participation

A layer may be enabled for visualization without affecting suitability. It participates in evaluation only when:

- a numeric acceptable range contains at least one bound, or a valid two-endpoint soft preference is present; or
- a categorical acceptable set contains at least one value.

An unconfigured layer is labelled “not scored,” is omitted from dealbreakers and the weighted denominator, and remains available for visualization and inspection.

### 10.2 Layer score

- A known scalar inside the inclusive acceptable numeric range scores `1`; outside scores `0`.
- A known category in the accepted set scores `1`; outside scores `0`.
- A multi-value fact scores `1` when any value matches; otherwise `0`.
- A spatial categorical mixture uses its canonical `mixed` category; no component share is silently treated as the building's category.

### 10.3 Fixed linear soft preference

A numeric layer declared `lower-is-better` or `higher-is-better` may additionally use the fixed two-endpoint soft preference. It has no user-selectable curve or shape:

- **Täysi etu** is the value scoring `1`.
- **Ei etua enää** is the value scoring `0`.
- Between the endpoints, the score changes linearly. The UI states: `Piste vähenee tasaisesti välillä X–Y min.`
- For lower-is-better, `full_score_at < zero_score_at`; values at or below the first endpoint score `1` and values at or above the second score `0`.
- For higher-is-better, `zero_score_at < full_score_at`; values at or below the first endpoint score `0` and values at or above the second score `1`.
- The numeric acceptable range and a soft preference are separate configured criteria. When a soft preference is present, its linear score is the layer score used in the weighted average; it does not weaken an enabled dealbreaker range.

### 10.4 Combined score

Dealbreakers determine eligibility and do not enter the weighted average. For eligible buildings:

`combined_score = sum(layer_score * layer_weight) / sum(participating_known_layer_weights)`

- Only configured, enabled, non-dealbreaker layers with usable evidence enter the default denominator.
- Weight must be a finite non-negative value. A zero-weight layer is inspectable but contributes nothing.
- If the denominator is zero, overall score is `null` and the map labels the building “no scored evidence.”
- The display converts scores to 0–100 without implying statistical probability.

### 10.5 Dealbreakers and missing data

The app has one global control applying only to configured dealbreakers:

- **Missing dealbreaker data: pass** (default): missing evidence does not make the building ineligible, but the building keeps an unknown warning.
- **Missing dealbreaker data: fail:** any wholly or partly missing dealbreaker value makes the building ineligible.

A known dealbreaker value outside the acceptable selection always fails. When a partially covered value is allowed by the `pass` policy, its known component is still evaluated normally. The inspector explains every failed or unevaluated dealbreaker.

## 11. Map and interface behavior

### 11.1 Published numeric distributions

For every numeric layer, the pipeline publishes a versioned static distribution artifact. Its bins are aligned exactly with that layer's published visualization breaks and colour classes; unknown and non-finite values are excluded and the known-value count reconciles with the bin counts. The browser loads this artifact locally and never derives a distribution from visible tiles alone.

The map-layer selector shows the selected numeric layer's compact histogram. A combined shop, education, or health-service layer shows the histogram recomputed from exactly the checkbox groups currently selected. The suitability layer shows the current score distribution across all scored buildings. A numeric criterion shows the same histogram, its accepted range, and, when configured, the full-score and no-benefit endpoints. These guides do not alter raw values, evaluation, the fixed map scale, or the linear scoring formula.

### 11.1 Layout

- Desktop: narrow scrollable preference sidebar, full-height map, compact selected-building inspector.
- Mobile: full map, controls in a drawer or bottom sheet, inspector in a bottom sheet.
- The layer selector and criterion picker group layers under Finnish headings such as `Liikkuminen`, `Lähipalvelut`, `Ympäristö`, `Asuminen ja rakennus`, and `Aluetiedot`.
- Layer rows are collapsed by default and summarize their active acceptable selection, weight, dealbreaker state, and missing warning.
- When a service-distance layer is selected, the map shows the same published destination points used by that layer as red markers. Nearby points cluster at low zoom and split into individual markers as the map is enlarged; selected retailer and service-group checkboxes limit the displayed points to the same groups used for the distance value. Hovering or clicking a marker shows its name, or all names represented by a cluster; it never changes the map zoom or selection.
- When the active detailed-plan overlay is visible, clicking an area opens a compact popup with its published plan number, available approval entry, and a link to Helsinki’s official plan map. The popup does not select a building or predict construction timing, scale, or disturbance.

### 11.2 Layer control

Numeric layer:

- optional inclusive minimum and maximum fields;
- clear/reset action;
- weight control when not a dealbreaker;
- dealbreaker toggle;
- nearby caveat affordance that opens methodology, source date, resolution, and limitations.

Selected grocery-store layer:

- the same numeric range, weight, dealbreaker, and caveat controls as another numeric layer;
- the same retailer checkboxes in both the individual map-layer control and criterion editor;
- its value is the minimum known walking distance among checked retailer groups, calculated only from published static attributes;
- if no retailer is selected, the layer is unconfigured and does not affect suitability; if all selected retailer groups are unknown for a building, the value is unknown.

Categorical layer:

- checkboxes for accepted categories;
- `mixed` is shown where the data model permits it;
- `unknown` is not an accepted category and is governed by missing policy;
- the same weight, dealbreaker, and caveat behavior.

The UI must not expose source codes in place of canonical Finnish labels.

### 11.3 Overall map states

The style must visually distinguish:

- eligible, scored buildings, using a restrained sequential suitability scale;
- buildings failing a dealbreaker;
- buildings with missing or partial data for any configured layer, using a hatch, outline, or similarly visible secondary encoding;
- eligible buildings with no scored evidence;
- non-residential buildings, which receive no suitability fill.

Colour alone may not be the only indication of fail or unknown. The legend explains every visible state.

### 11.4 Individual-layer map

- Numeric layers use a unit-labelled sequential legend based on raw values, not user score.
- Each numeric layer declares one fixed visualization range in the published layer catalogue. Values outside the range clamp to an endpoint; panning or zooming must not alter the displayed scale.
- Categorical layers use a discrete legend including `mixed` and `unknown`.
- Partial data remains visibly marked.
- Switching visualization does not alter preferences.
- The layer caveat and source vintage remain reachable from the legend.
- The map offers an offline area search over its published municipality and city-centre shortcuts; it never calls a geocoding service at runtime.

### 11.5 Inspector

For a selected residential building, show:

- address when publishable and available, otherwise building ID;
- overall score or reason it is absent;
- eligibility and failed dealbreakers;
- missing/partial-data warning summary;
- for every layer: raw value(s), unit, accepted selection, pass/fail/unknown, binary layer score if participating, weight if applicable, coverage, method, confidence, source vintage, caveats, and evidence links;
- exact area proportions for `mixed` values;
- a plain-language disclaimer that tenure/owner layers are evidence-based and not an authoritative title search.

## 12. Accessibility, privacy, and safety

- Keyboard users can open controls, change preferences, navigate the layer selector, and close the inspector.
- Controls have programmatic labels; legends and status states have textual equivalents.
- Text and essential map-state distinctions meet WCAG 2.1 AA contrast where applicable.
- Respect reduced-motion preferences; no essential information depends on animation.
- The app stores only preferences locally. It sends no selected location, preference, or click history to an application backend.
- Published artifacts contain no owner, tenant, or other natural-person names.
- External source links are clearly marked.

## 13. Performance and static data delivery

- Initial map navigation must not require loading attributes for every building in the metropolitan area.
- Geometry and attributes are partitioned spatially and compressed. Raw source GeoJSON is never shipped as the primary whole-region browser payload.
- After currently visible building attributes are loaded, changing a preference updates visible building styling within 200 ms at the 95th percentile on the project's reference laptop and dataset.
- After relevant data is loaded, a building click opens its basic inspector within 100 ms at the 95th percentile.
- Map pan/zoom remains interactive while partitions load; loading and unavailable states are distinct.
- A failed partition request may be retried and produces a visible local error without crashing already loaded map areas.
- The release report records compressed asset sizes, building count, partition count, and the timings from the repeatable performance check.

The reference machine and browser version are recorded in the release report so these targets remain testable rather than universal promises.

## 14. Pipeline behavior and failure modes

### 14.1 Reproducibility

- Raw snapshots are immutable and checksummed.
- Re-running from identical snapshots and configuration produces semantically identical normalized values and deterministic IDs.
- Downloads are cached; a partial download is never treated as complete.
- Every output references its source and build configuration versions.
- CRS transformations are explicit. Area intersections use a suitable projected CRS, not longitude/latitude degrees.

### 14.2 Validation failures

- Source unavailable: use an explicitly selected cached snapshot or fail that source; never silently substitute another vintage.
- Schema drift: fail the affected adapter with a field-level report.
- Missing licence: exclude from public export.
- Invalid geometry: apply the documented common repair; if repair fails, quarantine the record and emit unknown plus an audit entry.
- Incompatible noise method/vintage: keep municipality data separate or mark unknown; never merge values as if comparable.
- Routing graph/GTFS mismatch: report failed origins/samples and produce partial or unknown values under the transit rules.
- Unroutable destination: unknown, not straight-line zero or an arbitrary cap.
- Suppressed demographic value: unknown.
- Conflicting land evidence: preserve records and emit conflict/mixed; never overwrite by input order.
- Orphan attribute/building/evidence reference: public build fails.

### 14.3 Audit output

Each build report includes per source and layer:

- input/output record counts;
- known, partial, unknown, and conflict counts by municipality;
- geometry repair and quarantine counts;
- unmapped building-use/type codes;
- routing failure counts;
- land-evidence counts by method and confidence;
- source dates, checksums, licences, and attributions;
- warnings about stale or mixed vintages.

These are diagnostics, not release coverage gates.

## 15. Files and ownership

The implementation should use this structure unless existing repository conventions justify a reviewed change:

```text
SPEC.md                         normative product/technical contract
README.md                       setup, data acquisition, build, test, deploy
pyproject.toml                  Python project and test configuration
pipeline/
  __main__.py                   pipeline command entry point
  build.py                      ordered build orchestration
  models.py                     canonical pipeline records
  source_registry.py            adapter registration
  layer_registry.py             layer registration
  config/
    sources.yaml                source URLs, snapshots, licences, attribution
    layers.yaml                 definitions and build parameters
    study_area.geojson          four-city boundary/config reference
  sources/                      one adapter module per upstream source
  layers/                       one builder module per layer or coherent family
  common/
    download.py                 cached immutable download behavior
    geometry.py                 CRS, repair, intersection, aggregation
    routing.py                  shared walking/cycling/transit primitives
    evidence.py                 provenance and land-evidence logic
    validation.py               schema and release checks
  export/
    web_bundle.py               tiles, attributes, and manifests
data/
  raw/                          ignored local source snapshots
  intermediate/                 ignored derived working data
  processed/                    ignored local release staging
  manifests/                    reviewable source/release manifests
web/
  package.json                  frontend commands and dependencies
  vite.config.ts                GitHub Pages base-path build
  public/data/                  generated static release artifacts
  src/
    app/                        application shell and persistence
    map/                        MapLibre map, styles, selection, legends
    layers/                     generic layer controls and metadata views
    scoring/                    pure evaluation functions
    inspector/                  building and point inspection
    data/                       manifest, partition, and schema loading
    types/                      shared frontend record definitions
tests/
  pipeline/                     Pytest unit/integration tests
  fixtures/                     tiny licensed/synthetic spatial fixtures
scripts/
  verify_e2e.sh                 production-build end-to-end proof
.github/workflows/pages.yml     static build/deployment after local validation
```

Generated bulk data is not committed unless its size, update workflow, and licence are explicitly reviewed. `web/public/data` may be populated during release packaging. Do not modify `/config` or `/infrastructure`; configuration is intentionally under `pipeline/config`.

## 16. Test strategy

### 16.1 Pipeline unit tests

- Numeric area-weighted aggregation, including partial coverage.
- Categorical distributions and `mixed` without arbitrary overlap thresholds.
- Geometry repair/quarantine behavior.
- Multi-value any-match semantics.
- Paavo sentinel normalization.
- Residential and canonical house-type mapping.
- Evidence precedence, conflicts, and the prohibition on negative inference.
- Deterministic IDs and checksums.
- Route sampling and partial/unknown results.
- Licence admission and public-field allowlist.

### 16.2 Frontend unit tests

- Inclusive numeric bounds and open-ended ranges.
- Category selection and `mixed` handling.
- Unconfigured enabled layers omitted from scoring.
- Weighted binary score calculation.
- Dealbreakers excluded from weighted average.
- Missing-dealbreaker pass/fail policy.
- Zero denominator returns no score.
- Preference persistence/version reset.
- Unsupported schema rejection.

### 16.3 Integration and UI tests

Use a small deterministic fixture containing:

- one fully known eligible residential building;
- one building failing a dealbreaker;
- one partially covered building;
- one building with conflicting parcel categories and exact proportions;
- one building with two construction years;
- one building with all configured weighted values missing;
- one non-residential building and one open-ground click.

Verify scoring, map styles, legend, selection, caveats, persistence, and individual-layer switching against this fixture before testing the full release data.

## 17. Acceptance criteria

Each statement is mandatory and testable for release 1.

### Data and pipeline

1. Given valid configured snapshots, one documented pipeline command produces a release manifest, building tiles, attribute partitions, evidence data, attributions, and an audit report without manual GIS editing.
2. A second build from identical snapshots/configuration produces the same stable building IDs and semantically identical values.
3. Every public layer value references at least one admitted source/evidence record or is explicitly unknown.
4. No public artifact contains owner/tenant natural-person names or a source marked `excluded`.
5. The release includes only completed residential buildings in the suitability overlay.
6. A synthetic 60% value-10 / 40% value-20 footprint aggregates to numeric value 14 with coverage 1.
7. A synthetic categorical footprint split 60% `city` / 40% `non_city` is `mixed` and retains both exact proportions.
8. A 1% valid overlap is retained; it is not removed by a hard-coded percentage threshold.
9. A 70% known / 30% uncovered footprint reports coverage 0.7 and partial state.
10. No unmatched land-evidence record becomes `owned` or `non_city`.
11. Every source manifest contains licence, attribution, retrieval/vintage dates, checksum, and redistribution decision.
12. Audit counts reconcile with exported building/layer/evidence records and are broken down by municipality.

### Scoring

13. A numeric scalar on an inclusive bound passes and scores 1; a value outside scores 0.
14. A building with years `[1940, 1970]` passes 1930–1950 and 1960–1980, and fails 1950–1960.
15. A categorical `mixed` value passes only when `mixed` is selected.
16. A layer with no accepted range/categories does not alter eligibility or combined score.
17. The combined score equals the documented weighted mean of configured, known, non-dealbreaker binary scores.
18. A known failed dealbreaker makes the building ineligible and identifies that layer.
19. A missing or partially missing dealbreaker follows the global pass/fail control and remains visibly marked unknown/partial in both modes.
20. A building with no participating known weighted layer has no overall score rather than zero.

### User interface

21. The user can view overall suitability and every user-facing layer without reloading the page.
22. The overall map visually distinguishes scored, failed-dealbreaker, missing/partial, no-score, and non-residential states, with a text legend.
23. Clicking a residential building shows every available raw value, exact multi-values/distributions, evaluation, coverage, source vintage, methodology, and caveat.
24. Clicking outside a residential building shows no overall score and returns available raw point values or a clear no-data message.
25. A caveat is reachable directly from every layer control and individual-layer legend.
26. Changing an acceptable selection or weight restyles loaded visible buildings without a network request.
27. Preferences, dealbreakers, weights, selected visualization, and global missing policy survive reload in the same browser.
28. Keyboard-only use can configure a layer, switch visualization, inspect a selected building, and close the inspector.
29. The land inspector states that results are evidence-based, shows evidence method/confidence, and does not present unknown as owned/private.
30. The frontend works at the configured GitHub Pages subpath with no runtime server or secret.

### Reliability and performance

31. Missing/corrupt attribute partitions show a scoped error while already loaded map areas remain usable.
32. Unsupported manifest major versions stop data rendering and show a readable compatibility error.
33. Full-region geometry/attributes are spatially partitioned and compressed; the initial view does not fetch all attribute partitions.
34. The recorded reference performance run meets the 200 ms preference-update and 100 ms loaded-inspector targets at the 95th percentile.
35. All Pytest, frontend unit, integration/UI, production build, static-link, and end-to-end checks pass before deployment.
36. Given any checked grocery-store groups, the map, criterion evaluation, inspector, and overview use the same minimum known walking distance; unchecked groups do not contribute.

## 18. Implementation sequence

Keep each task independently verifiable and avoid redesigning the core for each layer.

1. Establish schemas, manifests, evidence rules, source admission checks, and a synthetic fixture.
2. Build HSY building ingestion, residential classification, house type, building year, tiles, and compact attribute export.
3. Implement pure frontend loading, generic controls, binary scoring, missing policy, overall/individual styling, inspector, and persistence against the fixture.
4. Implement common numeric/categorical spatial aggregation and noise.
5. Implement the owner-class layer municipality by municipality with evidence tests and public-field allowlisting.
6. Implement OSM/HSY environmental and service destinations plus walking/cycling routing.
7. Implement HSL transit sampling and failure reporting.
8. Implement Paavo income and suppression handling.
9. Run full audit, performance tuning, accessibility checks, attribution review, and GitHub Pages end-to-end verification.

If a step requires changing more than five files, the implementing agent must first propose the exact file set and split the work where practical, as required by repository instructions.

## 19. End-to-end proof

The release is proven to work only when `scripts/verify_e2e.sh` (or an equivalently documented single command) performs all of the following from a clean checkout with reviewed dependencies already installed:

1. Runs all pipeline and frontend tests.
2. Builds the deterministic small fixture through the real pipeline interfaces.
3. Builds the production frontend for the configured GitHub Pages subpath.
4. Starts a local static server with no application backend.
5. Opens the app in an automated browser and confirms the fixture buildings appear.
6. Configures building year to 1960–1980 and confirms the `[1940, 1970]` building passes by the documented any-match rule.
7. Sets the daytime-noise zone upper bound as a dealbreaker, confirms a known failing building becomes ineligible, and confirms the inspector names noise as the cause.
8. Toggles missing-dealbreaker policy from pass to fail and confirms the partially missing fixture building changes eligibility while retaining its missing warning.
9. Selects `land_owner_class`, confirms city and other-owner categories have distinct styles, and confirms the inspector reports the value, confidence, and evidence.
10. Changes two non-dealbreaker weights and confirms the displayed combined score equals the independently calculated expected weighted mean.
11. Switches to an individual numeric layer and verifies raw-value legend and caveat access.
12. Clicks open ground and verifies no suitability score is claimed.
13. Reloads and confirms saved preferences and visualization return.
14. Verifies no runtime request targets an application API, WFS/WMS, GTFS, routing service, or secret-bearing endpoint.
15. Runs the release schema, attribution, broken-link, public-field, asset-size, and recorded performance checks.

The command exits non-zero on any failure. A passing run, its release manifest, audit report, and deployed GitHub Pages smoke test together constitute the end-to-end evidence that the app works.
