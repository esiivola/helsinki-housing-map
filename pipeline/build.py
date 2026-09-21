from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
import json
import time
from pathlib import Path

import geopandas as gpd
import pyarrow.parquet as pq
import yaml
from shapely.geometry import Point
from shapely.geometry import mapping

from pipeline.common.validation import validate_public_evidence, validate_source_manifest
from pipeline.export.web_bundle import export
from pipeline.layer_registry import load_layer_registry
from pipeline.layers.buildings import normalize_building
from pipeline.models import (
    BuildingRecord,
    BuildingValue,
    Confidence,
    EvidenceRecord,
    LayerDefinition,
    LayerValueRecord,
    ReleaseArtifact,
    SourceManifest,
    ValueKind,
    ValueMethod,
    ValueState,
)
from pipeline.sources.transit import MORNING_RANGE_ITINERARY_DETAIL_VERSION


def normalize_buildings(records: Iterable[Mapping[str, object]]) -> list[BuildingRecord]:
    return [normalize_building(record) for record in records]


def build_fixture_release(fixture_path: Path, output_dir: Path):
    fixture = json.loads(fixture_path.read_text())
    sources = tuple(SourceManifest(**record) for record in fixture["source_manifests"])
    for source in sources:
        validate_source_manifest(source)

    evidence = tuple(EvidenceRecord(**record) for record in fixture["evidence"])
    for record in fixture["evidence"]:
        validate_public_evidence(record)
    buildings = tuple(normalize_buildings(fixture["buildings"]))
    layer_values = tuple(_layer_value(record) for record in fixture["layer_values"])
    release = ReleaseArtifact(
        schema_version=fixture["schema_version"],
        sources=sources,
        evidence=evidence,
        buildings=buildings,
        layer_values=layer_values,
    )
    _validate_references(release)
    return export(release, output_dir, load_layer_registry(Path(__file__).parent / "config" / "layers.yaml"))


def build_hsy_release(
    snapshot_path: Path,
    output_dir: Path,
    source_manifest: SourceManifest,
    paavo_snapshot: Path,
    paavo_source_manifest: SourceManifest,
    noise_snapshot: Path,
    noise_source_manifest: SourceManifest,
    vantaa_property_snapshot: Path,
    vantaa_property_source_manifest: SourceManifest,
    osm_snapshot: Path,
    osm_source_manifest: SourceManifest,
    helsinki_buildings_snapshot: Path | None = None,
    helsinki_buildings_source_manifest: SourceManifest | None = None,
    gtfs_source_manifest: SourceManifest | None = None,
    morning_transit_batch_dir: Path | None = None,
    workplace_transit_batch_dir: Path | None = None,
    source_crs: int = 3879,
    night_noise_snapshot: Path | None = None,
    night_noise_source_manifest: SourceManifest | None = None,
    active_plans_snapshot: Path | None = None,
    active_plans_source_manifest: SourceManifest | None = None,
    espoo_city_land_snapshot: Path | None = None,
    espoo_city_land_source_manifest: SourceManifest | None = None,
    vantaa_buildings_snapshot: Path | None = None,
    vantaa_buildings_source_manifest: SourceManifest | None = None,
    main_cycle_network_snapshot: Path | None = None,
    main_cycle_network_source_manifest: SourceManifest | None = None,
    green_cover_snapshots: tuple[Path, ...] = (),
    green_cover_source_manifest: SourceManifest | None = None,
    green_cover_checkpoint_dir: Path | None = None,
    service_map_snapshot: Path | None = None,
    service_map_source_manifest: SourceManifest | None = None,
    ptv_health_snapshot: Path | None = None,
    ptv_health_source_manifest: SourceManifest | None = None,
):
    started_at = time.perf_counter()
    from pipeline.export.web_bundle import export_hsy_attributes
    from pipeline.sources.hsy_buildings import deduplicate_hsy_buildings, normalize_hsy_buildings, read_hsy_buildings
    from pipeline.sources.helsinki_buildings import building_facts_by_vtj, house_types_by_vtj, read_helsinki_buildings
    from pipeline.sources.paavo import assign_income_by_point
    from pipeline.sources.noise import assign_noise_upper_by_intersection, read_noise_zones
    from pipeline.sources.vantaa_property_map import assign_lease_evidence, read_lease_areas
    from pipeline.sources.osm import GROCERY_STORE_GROUPS, HEALTH_PROVIDER_GROUPS, assign_sparse_route_distances, extract_basemap, extract_destinations, extract_pedestrian_sparse_graph
    from pipeline.sources.cycling_quality import assign_cycling_metrics, build_cycling_network
    from pipeline.sources.ptv import HEALTH_SERVICE_GROUPS, extract_health_destinations
    from pipeline.sources.service_map import EDUCATION_SERVICE_GROUPS, extract_education_destinations

    validate_source_manifest(source_manifest)
    validate_source_manifest(paavo_source_manifest)
    validate_source_manifest(noise_source_manifest)
    validate_source_manifest(vantaa_property_source_manifest)
    validate_source_manifest(osm_source_manifest)
    if (night_noise_snapshot is None) != (night_noise_source_manifest is None):
        raise ValueError("Night-noise snapshot and source manifest must be provided together")
    if night_noise_source_manifest is not None:
        validate_source_manifest(night_noise_source_manifest)
    if (active_plans_snapshot is None) != (active_plans_source_manifest is None):
        raise ValueError("Active-plans snapshot and source manifest must be provided together")
    if active_plans_source_manifest is not None:
        validate_source_manifest(active_plans_source_manifest)
    if (espoo_city_land_snapshot is None) != (espoo_city_land_source_manifest is None):
        raise ValueError("Espoo city-land snapshot and source manifest must be provided together")
    if espoo_city_land_source_manifest is not None:
        validate_source_manifest(espoo_city_land_source_manifest)
    if (vantaa_buildings_snapshot is None) != (vantaa_buildings_source_manifest is None):
        raise ValueError("Vantaa buildings snapshot and source manifest must be provided together")
    if vantaa_buildings_source_manifest is not None:
        validate_source_manifest(vantaa_buildings_source_manifest)
    if (helsinki_buildings_snapshot is None) != (helsinki_buildings_source_manifest is None):
        raise ValueError("Helsinki buildings snapshot and source manifest must be provided together")
    if helsinki_buildings_source_manifest is not None:
        validate_source_manifest(helsinki_buildings_source_manifest)
    if gtfs_source_manifest is not None:
        validate_source_manifest(gtfs_source_manifest)
    if (main_cycle_network_snapshot is None) != (main_cycle_network_source_manifest is None):
        raise ValueError("Main-cycle-network snapshot and source manifest must be provided together")
    if main_cycle_network_source_manifest is not None:
        validate_source_manifest(main_cycle_network_source_manifest)
    if bool(green_cover_snapshots) != (green_cover_source_manifest is not None):
        raise ValueError("Green-cover snapshots and source manifest must be provided together")
    if green_cover_source_manifest is not None:
        validate_source_manifest(green_cover_source_manifest)
    if (service_map_snapshot is None) != (service_map_source_manifest is None):
        raise ValueError("Service Map snapshot and source manifest must be provided together")
    if service_map_source_manifest is not None:
        validate_source_manifest(service_map_source_manifest)
    if (ptv_health_snapshot is None) != (ptv_health_source_manifest is None):
        raise ValueError("PTV healthcare snapshot and source manifest must be provided together")
    if ptv_health_source_manifest is not None:
        validate_source_manifest(ptv_health_source_manifest)
    raw_buildings = deduplicate_hsy_buildings(read_hsy_buildings(
        snapshot_path,
        {"vtj_prt", "raktun", "kavu", "kayttarks", "kunta"},
        source_crs=source_crs,
    ))
    normalized = normalize_hsy_buildings(raw_buildings)
    scored_indices = [index for index, building in enumerate(normalized) if building.is_scored]
    buildings = tuple(normalized[index] for index in scored_indices)
    scored_buildings = raw_buildings.iloc[scored_indices].copy()
    scored_buildings["building_id"] = [building.building_id for building in buildings]
    helsinki_registry = read_helsinki_buildings(helsinki_buildings_snapshot) if helsinki_buildings_snapshot is not None else None
    helsinki_house_types = house_types_by_vtj(helsinki_registry) if helsinki_registry is not None else {}
    from pipeline.sources.vantaa_buildings import house_types_by_vtj as vantaa_house_types_by_vtj
    vantaa_house_types = vantaa_house_types_by_vtj(vantaa_buildings_snapshot) if vantaa_buildings_snapshot is not None else {}
    helsinki_building_facts = building_facts_by_vtj(helsinki_registry) if helsinki_registry is not None else {}
    paavo_areas = gpd.read_file(paavo_snapshot)
    if paavo_areas.crs is None or "tr_mtu" not in paavo_areas:
        raise ValueError("Paavo snapshot requires a CRS and tr_mtu field")
    income_by_building = assign_income_by_point(scored_buildings.to_crs(3067), paavo_areas.to_crs(3067))
    noise_buildings = scored_buildings.loc[scored_buildings["kunta"] == "091"].to_crs(3067)
    noise_by_building = assign_noise_upper_by_intersection(noise_buildings, read_noise_zones(noise_snapshot).to_crs(3067))
    night_noise_by_building = (
        assign_noise_upper_by_intersection(noise_buildings, read_noise_zones(night_noise_snapshot).to_crs(3067))
        if night_noise_snapshot is not None
        else {}
    )
    from pipeline.sources.planning import active_plan_properties, read_active_plan_areas
    # Active detailed-plan areas ship only as a tickable vector map overlay (below),
    # not as a per-building scoreable layer, so we keep the polygons but no longer
    # assign a per-building in-plan-area status.
    active_plan_areas = read_active_plan_areas(active_plans_snapshot).to_crs(3067) if active_plans_snapshot is not None else None
    vantaa_buildings = scored_buildings.loc[scored_buildings["kunta"] == "092"].to_crs(3067)
    lease_by_building = assign_lease_evidence(vantaa_buildings, read_lease_areas(vantaa_property_snapshot).to_crs(3067))
    from pipeline.sources.espoo_city_land import assign_city_owner_evidence, read_city_land_areas
    espoo_buildings = scored_buildings.loc[scored_buildings["kunta"] == "049"].to_crs(3067)
    city_owner_by_building = (
        assign_city_owner_evidence(espoo_buildings, read_city_land_areas(espoo_city_land_snapshot).to_crs(3067))
        if espoo_city_land_snapshot is not None
        else {}
    )
    osm_nodes, osm_coordinates, osm_graph = extract_pedestrian_sparse_graph(osm_snapshot)
    destinations = extract_destinations(osm_snapshot)
    grocery_store_layer_ids = tuple(f"grocery_store_{group}_walk_m" for group in GROCERY_STORE_GROUPS)
    education_layer_ids = tuple(f"education_service_{group}_walk_m" for group in EDUCATION_SERVICE_GROUPS)
    health_layer_ids = tuple(f"health_service_{group}_walk_m" for group in HEALTH_SERVICE_GROUPS)
    osm_values = {
        **{layer_id: assign_sparse_route_distances(scored_buildings, osm_nodes, osm_coordinates, osm_graph, list(destinations[layer_id.removesuffix("_walk_m")].geometry)) for layer_id in grocery_store_layer_ids},
        "forest_walk_m": assign_sparse_route_distances(scored_buildings, osm_nodes, osm_coordinates, osm_graph, list(destinations["forest"].geometry)),
        "shore_walk_m": assign_sparse_route_distances(scored_buildings, osm_nodes, osm_coordinates, osm_graph, list(destinations["shore"].geometry)),
        "daycare_walk_m": assign_sparse_route_distances(scored_buildings, osm_nodes, osm_coordinates, osm_graph, list(destinations["daycare"].geometry)),
        "school_walk_m": assign_sparse_route_distances(scored_buildings, osm_nodes, osm_coordinates, osm_graph, list(destinations["school"].geometry)),
        "healthcare_walk_m": assign_sparse_route_distances(scored_buildings, osm_nodes, osm_coordinates, osm_graph, list(destinations["healthcare"].geometry)),
        "library_walk_m": assign_sparse_route_distances(scored_buildings, osm_nodes, osm_coordinates, osm_graph, list(destinations["library"].geometry)),
    }
    education_destinations = extract_education_destinations(service_map_snapshot) if service_map_snapshot is not None else {}
    education_values = {
        f"education_service_{group}_walk_m": assign_sparse_route_distances(scored_buildings, osm_nodes, osm_coordinates, osm_graph, list(points.geometry))
        for group, points in education_destinations.items()
    }
    health_destinations = extract_health_destinations(ptv_health_snapshot) if ptv_health_snapshot is not None else {}
    health_values = {
        f"health_service_{group}_walk_m": assign_sparse_route_distances(
            scored_buildings, osm_nodes, osm_coordinates, osm_graph,
            [*points.geometry, *(destinations[f"health_provider_{group}"].geometry if group in HEALTH_PROVIDER_GROUPS else ())],
        )
        for group, points in health_destinations.items()
    }
    routing = yaml.safe_load((Path(__file__).parent / "config" / "routing.yaml").read_text())
    workplace_destinations = [*routing["workplace_destinations"], {"id": "rautatieasema", **routing["central_destination"]}]
    # One parse of the cycling network serves both the travel-time layers and the
    # route-measured ease layers; the enriched network is the same graph plus the
    # surface, junction-degree and traffic-signal attributes the ease score needs.
    cycling_network = build_cycling_network(osm_snapshot)
    bike_nodes, bike_coordinates, bike_graph = cycling_network.nodes, cycling_network.coordinates, cycling_network.graph
    workplace_cycling = {
        destination["id"]: assign_cycling_metrics(
            scored_buildings, cycling_network, Point(destination["longitude"], destination["latitude"]), routing["cycling_speed_kmh"],
        )
        for destination in workplace_destinations
    }
    ready_workplace_destination_ids = complete_workplace_transit_destinations(
        workplace_transit_batch_dir,
        [str(destination["id"]) for destination in workplace_destinations],
        [building.building_id for building in buildings],
        sample_count=61,
        itinerary_detail_version=MORNING_RANGE_ITINERARY_DETAIL_VERSION,
    ) if workplace_transit_batch_dir else set()
    workplace_transit_values = load_workplace_transit_batches(workplace_transit_batch_dir, sorted(ready_workplace_destination_ids), [building.building_id for building in buildings]) if ready_workplace_destination_ids else {}
    from pipeline.sources.green_cover import green_cover_300m
    green_cover_values = green_cover_300m(scored_buildings, list(green_cover_snapshots), green_cover_checkpoint_dir) if green_cover_snapshots else {}

    geometry_by_municipality: dict[str, list[dict[str, object]]] = {}
    for building, geometry in zip(buildings, scored_buildings.to_crs(4326).geometry, strict=True):
        geometry_by_municipality.setdefault(building.municipality, []).append(
            {
                "type": "Feature",
                "properties": {"building_id": building.building_id},
                "geometry": mapping(geometry),
            }
        )
    evidence = EvidenceRecord(
        evidence_id="hsy-building-characteristics",
        source_id=source_manifest.source_id,
        source_url=source_manifest.source_url,
        retrieved_at=source_manifest.retrieved_at,
        vintage=source_manifest.vintage,
        claim="building characteristics",
        method=ValueMethod.DIRECT,
        confidence=Confidence.HIGH,
        caveat_ids=("older-records-may-be-uncertain",),
    )
    helsinki_house_type_evidence = (
        EvidenceRecord(
            evidence_id="helsinki-building-class",
            source_id=helsinki_buildings_source_manifest.source_id,
            source_url=helsinki_buildings_source_manifest.source_url,
            retrieved_at=helsinki_buildings_source_manifest.retrieved_at,
            vintage=helsinki_buildings_source_manifest.vintage,
            claim="building class mapped to canonical house type",
            method=ValueMethod.DIRECT,
            confidence=Confidence.HIGH,
            caveat_ids=("unmapped-codes-are-unknown",),
        )
        if helsinki_buildings_source_manifest is not None
        else None
    )
    helsinki_building_facts_evidence = (
        EvidenceRecord(
            evidence_id="helsinki-building-facts",
            source_id=helsinki_buildings_source_manifest.source_id,
            source_url=helsinki_buildings_source_manifest.source_url,
            retrieved_at=helsinki_buildings_source_manifest.retrieved_at,
            vintage=helsinki_buildings_source_manifest.vintage,
            claim="building lift, heating, storey, and dwelling facts",
            method=ValueMethod.DIRECT,
            confidence=Confidence.HIGH,
            caveat_ids=("helsinki-only-building-register", "unmapped-codes-are-unknown"),
        )
        if helsinki_buildings_source_manifest is not None
        else None
    )
    vantaa_house_type_evidence = (
        EvidenceRecord("vantaa-building-class", vantaa_buildings_source_manifest.source_id, vantaa_buildings_source_manifest.source_url,
            vantaa_buildings_source_manifest.retrieved_at, vantaa_buildings_source_manifest.vintage,
            "building class mapped to canonical house type", ValueMethod.DIRECT, Confidence.HIGH,
            ("unmapped-codes-are-unknown",))
        if vantaa_buildings_source_manifest is not None else None
    )
    paavo_evidence = EvidenceRecord(
        evidence_id="paavo-postal-area-income",
        source_id=paavo_source_manifest.source_id,
        source_url=paavo_source_manifest.source_url,
        retrieved_at=paavo_source_manifest.retrieved_at,
        vintage=paavo_source_manifest.vintage,
        claim="postal-area median disposable household income",
        method=ValueMethod.DIRECT,
        confidence=Confidence.MEDIUM,
        caveat_ids=("postal-area-context", "suppressed-values-unknown"),
    )
    noise_evidence = EvidenceRecord(
        evidence_id="helsinki-noise-day-upper-bound",
        source_id=noise_source_manifest.source_id,
        source_url=noise_source_manifest.source_url,
        retrieved_at=noise_source_manifest.retrieved_at,
        vintage=noise_source_manifest.vintage,
        claim="daytime traffic-noise zone upper bound",
        method=ValueMethod.AGGREGATED,
        confidence=Confidence.MEDIUM,
        caveat_ids=("modeled-indicative", "zone-upper-bound-not-building-maximum"),
    )
    night_noise_evidence = (
        EvidenceRecord(
            evidence_id="helsinki-noise-night-upper-bound",
            source_id=night_noise_source_manifest.source_id,
            source_url=night_noise_source_manifest.source_url,
            retrieved_at=night_noise_source_manifest.retrieved_at,
            vintage=night_noise_source_manifest.vintage,
            claim="nighttime traffic-noise zone upper bound",
            method=ValueMethod.AGGREGATED,
            confidence=Confidence.MEDIUM,
            caveat_ids=("modeled-indicative", "zone-upper-bound-not-building-maximum", "helsinki-only-noise"),
        )
        if night_noise_source_manifest is not None
        else None
    )
    active_plans_evidence = (
        EvidenceRecord(
            evidence_id="helsinki-active-planning-area",
            source_id=active_plans_source_manifest.source_id,
            source_url=active_plans_source_manifest.source_url,
            retrieved_at=active_plans_source_manifest.retrieved_at,
            vintage=active_plans_source_manifest.vintage,
            claim="building intersects a published active detailed-plan area",
            method=ValueMethod.AGGREGATED,
            confidence=Confidence.HIGH,
            caveat_ids=("planning-area-not-construction", "helsinki-only-planning"),
        )
        if active_plans_source_manifest is not None
        else None
    )
    lease_evidence = EvidenceRecord(
        evidence_id="vantaa-lease-area", source_id=vantaa_property_source_manifest.source_id,
        source_url=vantaa_property_source_manifest.source_url,
        retrieved_at=vantaa_property_source_manifest.retrieved_at, vintage=vantaa_property_source_manifest.vintage,
        claim="positive lease-area evidence", method=ValueMethod.AGGREGATED,
        confidence=Confidence.MEDIUM, caveat_ids=("evidence-based-not-title-search",),
    )
    city_owner_evidence = (
        EvidenceRecord(
            evidence_id="espoo-city-land", source_id=espoo_city_land_source_manifest.source_id,
            source_url=espoo_city_land_source_manifest.source_url,
            retrieved_at=espoo_city_land_source_manifest.retrieved_at, vintage=espoo_city_land_source_manifest.vintage,
            claim="building footprint fully covered by published Espoo city-owned land",
            method=ValueMethod.AGGREGATED, confidence=Confidence.HIGH,
            caveat_ids=("evidence-based-not-title-search",),
        )
        if espoo_city_land_source_manifest is not None
        else None
    )
    osm_evidence = EvidenceRecord("hsl-osm-routing", osm_source_manifest.source_id, osm_source_manifest.source_url, osm_source_manifest.retrieved_at, osm_source_manifest.vintage, "offline OSM pedestrian routing", ValueMethod.DERIVED, Confidence.MEDIUM, ("routing-origin-fallback", "osm-completeness"))
    transit_evidence = EvidenceRecord("hsl-gtfs-transit-routing", gtfs_source_manifest.source_id, gtfs_source_manifest.source_url, gtfs_source_manifest.retrieved_at, gtfs_source_manifest.vintage, "offline sampled multimodal route to Helsinki Central", ValueMethod.DERIVED, Confidence.MEDIUM, ("representative-weekday", "failed-samples-visible")) if gtfs_source_manifest else None
    green_cover_evidence = EvidenceRecord("hsy-green-cover-300m", green_cover_source_manifest.source_id, green_cover_source_manifest.source_url, green_cover_source_manifest.retrieved_at, green_cover_source_manifest.vintage, "vegetated land-cover share within 300 metres", ValueMethod.AGGREGATED, Confidence.MEDIUM, ("land-cover-resolution",)) if green_cover_source_manifest else None
    main_cycle_network_evidence = EvidenceRecord("helsinki-main-cycle-route-access", main_cycle_network_source_manifest.source_id, main_cycle_network_source_manifest.source_url, main_cycle_network_source_manifest.retrieved_at, main_cycle_network_source_manifest.vintage, "distance to published Helsinki main cycle routes", ValueMethod.DERIVED, Confidence.MEDIUM, ("helsinki-only-cycling-network",)) if main_cycle_network_source_manifest else None
    service_map_evidence = EvidenceRecord("service-map-education-destination", service_map_source_manifest.source_id, service_map_source_manifest.source_url, service_map_source_manifest.retrieved_at, service_map_source_manifest.vintage, "published education and daycare service location", ValueMethod.DIRECT, Confidence.HIGH, ("service-category-classification",)) if service_map_source_manifest else None
    ptv_health_evidence = EvidenceRecord("ptv-healthcare-destination", ptv_health_source_manifest.source_id, ptv_health_source_manifest.source_url, ptv_health_source_manifest.retrieved_at, ptv_health_source_manifest.vintage, "published healthcare service location", ValueMethod.DIRECT, Confidence.MEDIUM, ("voluntary-private-provider-coverage", "service-category-classification")) if ptv_health_source_manifest else None
    layers = load_layer_registry(Path(__file__).parent / "config" / "layers.yaml")
    layers.update(_workplace_layers(workplace_destinations, ready_workplace_destination_ids))
    if green_cover_source_manifest:
        layers["green_cover_300m_pct"] = _environment_layer("green_cover_300m_pct", "Vihreän peitteen osuus 300 metrin säteellä", "%", (0, 100), "Vegetated land-cover area within a 300 m radius.", "Offline intersection of HSY 2024 vegetation classes with a 300 m point buffer.", ("land-cover-resolution",), (green_cover_source_manifest.source_id,))
    if service_map_source_manifest:
        layers.update(_service_distance_layers("education_service", EDUCATION_SERVICE_GROUPS, "Palvelukartta", (service_map_source_manifest.source_id, osm_source_manifest.source_id)))
        layers["daycare_walk_m"] = replace(layers["daycare_walk_m"], visible=False)
        layers["school_walk_m"] = replace(layers["school_walk_m"], visible=False)
    if ptv_health_source_manifest:
        layers.update(_service_distance_layers("health_service", HEALTH_SERVICE_GROUPS, "Palvelutietovaranto", (ptv_health_source_manifest.source_id, osm_source_manifest.source_id)))
        layers["healthcare_walk_m"] = replace(layers["healthcare_walk_m"], visible=False)
    values = tuple(
        value
        for building in buildings
        for value in (
            LayerValueRecord(
                building_id=building.building_id,
                layer_id="building_year",
                value=BuildingValue(
                    state=ValueState.KNOWN if building.construction_years else ValueState.UNKNOWN,
                    kind=ValueKind.MULTI,
                    value=None,
                    values=building.construction_years,
                    coverage=1 if building.construction_years else 0,
                    evidence_ids=(evidence.evidence_id,) if building.construction_years else (),
                    method=ValueMethod.DIRECT,
                    confidence=Confidence.HIGH,
                ),
            ),
            LayerValueRecord(
                building_id=building.building_id,
                layer_id="house_type",
                value=BuildingValue(
                    state=ValueState.KNOWN if building.building_id in (helsinki_house_types if building.municipality == "Helsinki" else vantaa_house_types if building.municipality == "Vantaa" else {}) else ValueState.UNKNOWN,
                    kind=ValueKind.SCALAR,
                    value=(helsinki_house_types if building.municipality == "Helsinki" else vantaa_house_types if building.municipality == "Vantaa" else {}).get(building.building_id),
                    coverage=1 if building.building_id in (helsinki_house_types if building.municipality == "Helsinki" else vantaa_house_types if building.municipality == "Vantaa" else {}) else 0,
                    evidence_ids=((helsinki_house_type_evidence.evidence_id,) if building.municipality == "Helsinki" and building.building_id in helsinki_house_types and helsinki_house_type_evidence else (vantaa_house_type_evidence.evidence_id,) if building.municipality == "Vantaa" and building.building_id in vantaa_house_types and vantaa_house_type_evidence else ()),
                    method=ValueMethod.DIRECT,
                    confidence=Confidence.HIGH if building.building_id in (helsinki_house_types if building.municipality == "Helsinki" else vantaa_house_types if building.municipality == "Vantaa" else {}) else Confidence.LOW,
                ),
            ),
            *(
                LayerValueRecord(
                    building_id=building.building_id,
                    layer_id=layer_id,
                    value=_helsinki_building_fact_value(
                        helsinki_building_facts.get(building.building_id),
                        field,
                        building.municipality,
                        helsinki_building_facts_evidence.evidence_id if helsinki_building_facts_evidence else None,
                    ),
                )
                for layer_id, field in (
                    ("elevator", "elevator"),
                    ("heating_method", "heating_method"),
                    ("heating_energy_source", "heating_energy_source"),
                    ("storey_count", "storey_count"),
                    ("dwelling_count", "dwelling_count"),
                )
            ),
            *(
                LayerValueRecord(
                    building_id=building.building_id,
                    layer_id=layer_id,
                    value=BuildingValue(
                        state=ValueState.UNKNOWN,
                        kind=ValueKind.MULTI if layer.kind.value == "categorical" else ValueKind.SCALAR,
                        value=None,
                        method=ValueMethod.DERIVED,
                        confidence=Confidence.LOW,
                    ),
                )
                for layer_id, layer in layers.items()
                if layer_id not in {"building_year", "house_type", "elevator", "heating_method", "heating_energy_source", "storey_count", "dwelling_count", "income_median_eur", "noise_day_upper_db", "noise_night_upper_db", "plot_tenure", "land_owner_class", *grocery_store_layer_ids, *education_layer_ids, *health_layer_ids, "forest_walk_m", "shore_walk_m", "daycare_walk_m", "school_walk_m", "healthcare_walk_m", "library_walk_m"} and not layer_id.startswith(("bike_workplace_", "transit_workplace_"))
            ),
            LayerValueRecord(
                building_id=building.building_id,
                layer_id="income_median_eur",
                value=_with_evidence(income_by_building[building.building_id], paavo_evidence.evidence_id),
            ),
            *(LayerValueRecord(building.building_id, layer_id, _with_evidence(osm_values[layer_id][building.building_id], osm_evidence.evidence_id)) for layer_id in (*grocery_store_layer_ids, "forest_walk_m", "shore_walk_m", "daycare_walk_m", "school_walk_m", "healthcare_walk_m", "library_walk_m")),
            *((LayerValueRecord(building.building_id, layer_id, _with_evidence_ids(education_values[layer_id][building.building_id], (service_map_evidence.evidence_id, osm_evidence.evidence_id))) for layer_id in education_layer_ids) if service_map_evidence else ()),
            *((LayerValueRecord(building.building_id, layer_id, _with_evidence_ids(health_values[layer_id][building.building_id], (ptv_health_evidence.evidence_id, osm_evidence.evidence_id))) for layer_id in health_layer_ids) if ptv_health_evidence else ()),
            *((LayerValueRecord(building.building_id, "green_cover_300m_pct", _with_evidence(green_cover_values[building.building_id], green_cover_evidence.evidence_id)),) if green_cover_evidence else ()),
            *(LayerValueRecord(building.building_id, f"bike_workplace_{destination['id']}_effective_min", _with_evidence(workplace_cycling[destination["id"]][1][building.building_id], osm_evidence.evidence_id)) for destination in workplace_destinations),
            *(LayerValueRecord(building.building_id, f"transit_workplace_{destination['id']}_{statistic}_min", _with_evidence(workplace_transit_values[destination["id"]][statistic][building.building_id], transit_evidence.evidence_id)) for destination in workplace_destinations if destination["id"] in ready_workplace_destination_ids for statistic in ("min", "median", "max")),
            *(LayerValueRecord(building.building_id, f"transit_workplace_{destination['id']}_median_boarding", _with_evidence(workplace_transit_values[destination["id"]]["median_boarding"][building.building_id], transit_evidence.evidence_id)) for destination in workplace_destinations if destination["id"] in ready_workplace_destination_ids),
            *((LayerValueRecord(building.building_id, "transit_workplace_median_first_boarding_walk_m", _with_evidence(workplace_transit_values["_all"]["median_first_boarding_walk_m"][building.building_id], transit_evidence.evidence_id)),) if {str(destination["id"]) for destination in workplace_destinations}.issubset(ready_workplace_destination_ids) else ()),
            LayerValueRecord(
                building_id=building.building_id, layer_id="plot_tenure",
                value=_with_evidence(lease_by_building.get(building.building_id, BuildingValue(ValueState.UNKNOWN, ValueKind.DISTRIBUTION, None)), lease_evidence.evidence_id),
            ),
            LayerValueRecord(
                building_id=building.building_id,
                layer_id="land_owner_class",
                value=_with_evidence(city_owner_by_building[building.building_id], city_owner_evidence.evidence_id)
                if building.building_id in city_owner_by_building and city_owner_evidence
                else BuildingValue(ValueState.UNKNOWN, ValueKind.SCALAR, None, method=ValueMethod.AGGREGATED, confidence=Confidence.LOW),
            ),
            LayerValueRecord(
                building_id=building.building_id,
                layer_id="noise_day_upper_db",
                value=_with_evidence(
                    noise_by_building.get(
                        building.building_id,
                        BuildingValue(ValueState.UNKNOWN, ValueKind.SCALAR, None, method=ValueMethod.AGGREGATED, confidence=Confidence.MEDIUM),
                    ),
                    noise_evidence.evidence_id,
                ),
            ),
            LayerValueRecord(
                building_id=building.building_id,
                layer_id="noise_night_upper_db",
                value=_with_evidence(
                    night_noise_by_building.get(
                        building.building_id,
                        BuildingValue(ValueState.UNKNOWN, ValueKind.SCALAR, None, method=ValueMethod.AGGREGATED, confidence=Confidence.MEDIUM),
                    ),
                    night_noise_evidence.evidence_id,
                ) if night_noise_evidence else BuildingValue(ValueState.UNKNOWN, ValueKind.SCALAR, None, method=ValueMethod.AGGREGATED, confidence=Confidence.MEDIUM),
            ),
        )
    )
    sources = tuple(source for source in (source_manifest, paavo_source_manifest, noise_source_manifest, night_noise_source_manifest, active_plans_source_manifest, vantaa_property_source_manifest, vantaa_buildings_source_manifest, espoo_city_land_source_manifest, osm_source_manifest, helsinki_buildings_source_manifest, gtfs_source_manifest, main_cycle_network_source_manifest, green_cover_source_manifest, service_map_source_manifest, ptv_health_source_manifest) if source is not None)
    published_source_ids = {source.source_id for source in sources}
    layers = {
        layer_id: replace(layer, source_ids=tuple(source_id for source_id in layer.source_ids if source_id in published_source_ids))
        for layer_id, layer in layers.items()
    }
    release = ReleaseArtifact(
        schema_version="1.0.0",
        sources=sources,
        evidence=tuple(item for item in (evidence, helsinki_house_type_evidence, vantaa_house_type_evidence, helsinki_building_facts_evidence, paavo_evidence, noise_evidence, night_noise_evidence, active_plans_evidence, lease_evidence, city_owner_evidence, osm_evidence, transit_evidence, green_cover_evidence, main_cycle_network_evidence, service_map_evidence, ptv_health_evidence) if item is not None),
        buildings=buildings,
        layer_values=values,
    )
    _validate_references(release)
    overlays = {}
    if active_plan_areas is not None:
        overlays["active-plans"] = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": active_plan_properties(area), "geometry": mapping(area.geometry)}
                for _, area in active_plan_areas.to_crs(4326).iterrows()
                if area.geometry is not None and not area.geometry.is_empty
            ],
        }
    if main_cycle_network_snapshot is not None:
        cycle_geometry = gpd.read_file(main_cycle_network_snapshot).to_crs(4326).geometry
        overlays["main-cycle-routes"] = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": mapping(geometry)} for geometry in cycle_geometry if geometry is not None and not geometry.is_empty]}
    overlays["service-destinations"] = _service_destination_overlay(destinations, education_destinations, health_destinations, GROCERY_STORE_GROUPS, HEALTH_PROVIDER_GROUPS)
    bundle = export_hsy_attributes(release, output_dir, geometry_by_municipality, layers, extract_basemap(osm_snapshot), overlays or None)
    audit_path = output_dir / "audit.json"
    audit = json.loads(audit_path.read_text())
    audit["performance"] = {"release_build_seconds": round(time.perf_counter() - started_at, 3)}
    audit_path.write_text(json.dumps(audit, sort_keys=True, separators=(",", ":")))
    return bundle


def _service_destination_overlay(
    osm_destinations: Mapping[str, gpd.GeoDataFrame],
    education_destinations: Mapping[str, gpd.GeoDataFrame],
    health_destinations: Mapping[str, gpd.GeoDataFrame],
    grocery_store_groups: Iterable[str],
    health_provider_groups: Iterable[str],
) -> dict[str, object]:
    health_provider_group_set = set(health_provider_groups)
    groups: list[tuple[str, Iterable[gpd.GeoDataFrame]]] = [
        *((f"grocery_store_{group}_walk_m", (osm_destinations[f"grocery_store_{group}"],)) for group in grocery_store_groups),
        ("daycare_walk_m", (osm_destinations["daycare"],)),
        ("school_walk_m", (osm_destinations["school"],)),
        ("healthcare_walk_m", (osm_destinations["healthcare"],)),
        ("library_walk_m", (osm_destinations["library"],)),
        *((f"education_service_{group}_walk_m", (points,)) for group, points in education_destinations.items()),
        *((f"health_service_{group}_walk_m", (points, osm_destinations[f"health_provider_{group}"]) if group in health_provider_group_set else (points,)) for group, points in health_destinations.items()),
    ]
    features = []
    for layer_id, frames in groups:
        for frame in frames:
            for _, row in frame.iterrows():
                geometry = row.geometry
                if geometry is not None and geometry.geom_type == "Point" and not geometry.is_empty:
                    name = str(row.get("name", "")).strip()
                    features.append({"type": "Feature", "properties": {"layer_id": layer_id, "name": name or layer_id}, "geometry": mapping(geometry)})
    return {"type": "FeatureCollection", "features": features}


def _helsinki_building_fact_value(facts, field: str, municipality: str, evidence_id: str | None) -> BuildingValue:
    value = getattr(facts, field, None) if municipality == "Helsinki" else None
    return BuildingValue(
        state=ValueState.KNOWN if value is not None else ValueState.UNKNOWN,
        kind=ValueKind.SCALAR,
        value=value,
        coverage=1 if value is not None else 0,
        evidence_ids=(evidence_id,) if value is not None and evidence_id else (),
        method=ValueMethod.DIRECT,
        confidence=Confidence.HIGH if value is not None else Confidence.LOW,
    )


def _workplace_layers(destinations: list[dict[str, object]], transit_destination_ids: set[str]) -> dict[str, LayerDefinition]:
    layers: dict[str, LayerDefinition] = {}
    for destination in destinations:
        destination_id = str(destination["id"])
        name = str(destination["name"])
        layers[f"bike_workplace_{destination_id}_effective_min"] = LayerDefinition(
            layer_id=f"bike_workplace_{destination_id}_effective_min", finnish_label=f"Pyörämatkan kesto: {name}", description=f"Pyörämatkan koettu kesto kohteeseen {name}: ajoaika sekä liikennevalojen, käännösten ja hitaan pinnoitteen viive.", kind="numeric", unit="min", formatter="integer", allowed_categories=(), allowed_min=0, allowed_max=None, default_enabled=False, default_weight=1, visualization_scale="sequential", visualization_range=(0, 120), methodology="Reitti valitaan koettua aikaa minimoiden: ajoaika (hidas pinnoite ja jalankulkijoiden kanssa jaettu väylä 0,65x), 30 s per liikennevalo, 10 s per käännös ja 2 s per valo-ohjaamaton suojatie. Perustuu CROW- ja Fietsbalans-kriteereihin; käännösten määrä on kalibroitu BRouter-reitittimeen (1,2x).", caveat_ids=("routing-origin-fallback", "osm-completeness"), source_ids=("hsl_osm_extract",),
        )
        for statistic, label in (("min", "minimi"), ("median", "mediaani"), ("max", "maksimi")) if destination_id in transit_destination_ids else ():
            layers[f"transit_workplace_{destination_id}_{statistic}_min"] = LayerDefinition(
                layer_id=f"transit_workplace_{destination_id}_{statistic}_min", finnish_label=f"Aamumatka: {name}, {label}", description=f"Aamun 07:00–08:00 joukkoliikennematkojen {label} kohteeseen {name}.", kind="numeric", unit="min", formatter="integer", allowed_categories=(), allowed_min=0, allowed_max=None, default_enabled=False, default_weight=1, visualization_scale="sequential", visualization_range=(0, 120), methodology="Offline sampled HSL routing; minimi, mediaani ja maksimi ovat lähtöaikojen yhteenvetoja.", caveat_ids=("representative-weekday", "failed-samples-visible"), source_ids=("hsl_gtfs",),
            )
        if destination_id in transit_destination_ids:
            layers[f"transit_workplace_{destination_id}_median_boarding"] = LayerDefinition(
                layer_id=f"transit_workplace_{destination_id}_median_boarding", finnish_label=f"Aamumatka: {name}, ajoneuvoihin nousut", description=f"Aamun 07:00–08:00 nopeimman saapumisen reittien ajoneuvoihin nousujen mediaani kohteeseen {name}.", kind="numeric", unit="nousua", formatter="one_decimal", allowed_categories=(), allowed_min=0, allowed_max=None, default_enabled=False, default_weight=1, visualization_scale="sequential", visualization_range=(0, 4), methodology="Offline HSL range routing; kävelyä ei lasketa nousuksi.", caveat_ids=("representative-weekday", "failed-samples-visible"), source_ids=("hsl_gtfs",),
            )
    if {str(destination["id"]) for destination in destinations}.issubset(transit_destination_ids):
        layers["transit_workplace_median_first_boarding_walk_m"] = LayerDefinition(
            layer_id="transit_workplace_median_first_boarding_walk_m", finnish_label="Aamumatka: kävelymatka ensimmäiselle pysäkille", description="Aamun 07:00–08:00 nopeimman saapumisen reittien kävelymatkan mediaani ensimmäiseen nousuun kaikissa työmatkakohteissa.", kind="numeric", unit="m", formatter="integer", allowed_categories=(), allowed_min=0, allowed_max=None, default_enabled=False, default_weight=1, visualization_scale="sequential", visualization_range=(0, 1500), methodology="Offline HSL range routing; sisältää vain matkat, joilla noustaan joukkoliikennevälineeseen.", caveat_ids=("representative-weekday", "failed-samples-visible"), source_ids=("hsl_gtfs",),
        )
    return layers


def _environment_layer(layer_id: str, label: str, unit: str, visualization_range: tuple[float, float], description: str, methodology: str, caveats: tuple[str, ...], source_ids: tuple[str, ...]) -> LayerDefinition:
    return LayerDefinition(layer_id=layer_id, finnish_label=label, description=description, kind="numeric", unit=unit, formatter="one_decimal", allowed_categories=(), allowed_min=0, allowed_max=None, default_enabled=False, default_weight=1, visualization_scale="sequential", visualization_range=visualization_range, methodology=methodology, caveat_ids=caveats, source_ids=source_ids)


def _service_distance_layers(prefix: str, groups: tuple[str, ...], source_name: str, source_ids: tuple[str, ...]) -> dict[str, LayerDefinition]:
    labels = {
        "daycare": "Päiväkoti",
        "primary_school": "Ala-aste",
        "lower_secondary_school": "Yläaste",
        "upper_secondary_school": "Lukio",
        "vocational_school": "Ammattikoulu",
        "health_centre": "Terveyskeskus",
        "dental_care": "Hammashoito",
        "maternity_and_child_health_clinic": "Neuvola",
        "mental_health_and_substance_use_services": "Mielenterveys- ja päihdepalvelut",
        "university_or_central_hospital": "Yliopisto- tai keskussairaala",
        "mehilainen": "Mehiläinen",
        "terveystalo": "Terveystalo",
        "pihlajalinna": "Pihlajalinna",
        "other_private_clinic": "Muut yksityiset lääkäriasemat",
        "social_services": "Sosiaalipalvelut",
    }
    return {
        f"{prefix}_{group}_walk_m": LayerDefinition(
            layer_id=f"{prefix}_{group}_walk_m", finnish_label=f"{labels[group]}: kävelymatkan taustataso",
            description=f"Valittavan palveluryhmän {labels[group].lower()} kävelymatkan taustatieto.", kind="numeric", unit="m", formatter="integer",
            allowed_categories=(), allowed_min=0, allowed_max=None, default_enabled=False, default_weight=1,
            visualization_scale="sequential", visualization_range=(0, 10000), methodology=f"Offline pedestrian-network distance to a {source_name} service location.",
            caveat_ids=("routing-origin-fallback", "service-category-classification"), source_ids=source_ids, visible=False,
        )
        for group in groups
    }


def load_transit_batches(directory: Path, building_ids: list[str]) -> dict[str, BuildingValue]:
    values = {
        building_id: BuildingValue(ValueState.UNKNOWN, ValueKind.SCALAR, None, method=ValueMethod.DERIVED, confidence=Confidence.MEDIUM)
        for building_id in building_ids
    }
    for path in sorted(directory.glob("transit-*.json")):
        for building_id, item in json.loads(path.read_text()).get("values", {}).items():
            if building_id not in values:
                continue
            state = ValueState(item.get("state", "unknown"))
            value = item.get("value") if state is not ValueState.UNKNOWN else None
            values[building_id] = BuildingValue(state, ValueKind.SCALAR, value, coverage=float(item.get("coverage", 0)), method=ValueMethod.DERIVED, confidence=Confidence.MEDIUM)
    samples_by_building: dict[str, list[dict[str, object]]] = {}
    for path in sorted(directory.glob("transit-*.parquet")):
        for sample in pq.read_table(path).to_pylist():
            building_id = sample["building_id"]
            if building_id in values:
                samples_by_building.setdefault(building_id, []).append(sample)
    for building_id, samples in samples_by_building.items():
        successful = [sample["duration_seconds"] for sample in samples if sample["state"] == "known" and sample["duration_seconds"] is not None]
        if not successful:
            continue
        values[building_id] = BuildingValue(
            ValueState.KNOWN if len(successful) == len(samples) else ValueState.PARTIAL,
            ValueKind.SCALAR,
            max(successful) / 60,
            coverage=len(successful) / len(samples),
            method=ValueMethod.DERIVED,
            confidence=Confidence.MEDIUM,
        )
    return values


def load_workplace_transit_batches(directory: Path, destination_ids: list[str], building_ids: list[str]) -> dict[str, dict[str, dict[str, BuildingValue]]]:
    """Read each available destination folder; absent or unfinished values remain unknown."""
    unknown = lambda: BuildingValue(ValueState.UNKNOWN, ValueKind.SCALAR, None, method=ValueMethod.DERIVED, confidence=Confidence.MEDIUM)
    known_building_ids = set(building_ids)
    result = {destination_id: {statistic: {building_id: unknown() for building_id in building_ids} for statistic in ("min", "median", "max", "median_boarding")} for destination_id in destination_ids}
    all_walks: dict[str, list[float]] = {}
    all_row_counts: dict[str, int] = {}
    for destination_id in destination_ids:
        for path in sorted((directory / destination_id).glob("transit-*.parquet")):
            samples: dict[str, list[dict[str, object]]] = {}
            for sample in pq.read_table(path, columns=["building_id", "state", "duration_seconds", "boardings", "first_boarding_walk_m"]).to_pylist():
                if sample["building_id"] in known_building_ids:
                    samples.setdefault(sample["building_id"], []).append(sample)
            for building_id, rows in samples.items():
                durations = sorted(float(row["duration_seconds"]) / 60 for row in rows if row["state"] == "known" and row["duration_seconds"] is not None)
                if durations:
                    state = ValueState.KNOWN if len(durations) == len(rows) else ValueState.PARTIAL
                    values = {"min": durations[0], "median": _median(durations), "max": durations[-1]}
                    for statistic, value in values.items():
                        result[destination_id][statistic][building_id] = BuildingValue(state, ValueKind.SCALAR, value, coverage=len(durations) / len(rows), method=ValueMethod.DERIVED, confidence=Confidence.MEDIUM)
                boardings = sorted(float(row["boardings"]) for row in rows if row["state"] == "known" and row.get("boardings") is not None)
                if boardings:
                    result[destination_id]["median_boarding"][building_id] = BuildingValue(ValueState.KNOWN if len(boardings) == len(rows) else ValueState.PARTIAL, ValueKind.SCALAR, _median(boardings), coverage=len(boardings) / len(rows), method=ValueMethod.DERIVED, confidence=Confidence.MEDIUM)
                all_row_counts[building_id] = all_row_counts.get(building_id, 0) + len(rows)
                all_walks.setdefault(building_id, []).extend(float(row["first_boarding_walk_m"]) for row in rows if row["state"] == "known" and row.get("first_boarding_walk_m") is not None)
    result["_all"] = {"median_first_boarding_walk_m": {building_id: unknown() for building_id in building_ids}}
    for building_id, walks in all_walks.items():
        walks.sort()
        if walks:
            result["_all"]["median_first_boarding_walk_m"][building_id] = BuildingValue(ValueState.KNOWN if len(walks) == all_row_counts[building_id] else ValueState.PARTIAL, ValueKind.SCALAR, _median(walks), coverage=len(walks) / all_row_counts[building_id], method=ValueMethod.DERIVED, confidence=Confidence.MEDIUM)
    return result


def _median(values: list[float]) -> float:
    middle = len(values) // 2
    return values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2


def complete_workplace_transit_destinations(
    directory: Path,
    destination_ids: list[str],
    building_ids: list[str],
    sample_count: int | None = None,
    itinerary_detail_version: int | None = None,
) -> set[str]:
    complete: set[str] = set()
    for destination_id in destination_ids:
        paths = sorted((directory / destination_id).glob("transit-*.parquet"))
        try:
            metadata = [pq.read_metadata(path) for path in paths]
            stored_sample_counts = {
                len(json.loads(item.metadata[b"transit_parameters"])["samples"])
                for item in metadata
                if item.metadata and b"transit_parameters" in item.metadata
            }
            stored_detail_versions = {
                json.loads(item.metadata[b"transit_parameters"]).get("itinerary_detail_version")
                for item in metadata
                if item.metadata and b"transit_parameters" in item.metadata
            }
            expected_sample_count = sample_count if sample_count is not None else next(iter(stored_sample_counts)) if len(stored_sample_counts) == 1 else None
            correct_version = itinerary_detail_version is None or stored_detail_versions == {itinerary_detail_version}
            if paths and expected_sample_count is not None and correct_version and sum(item.num_rows for item in metadata) == len(building_ids) * expected_sample_count:
                complete.add(destination_id)
        except (OSError, ValueError, KeyError, pa.ArrowException):
            continue
    return complete


def _with_evidence(value: BuildingValue, evidence_id: str) -> BuildingValue:
    if value.state is ValueState.UNKNOWN:
        return value
    return BuildingValue(
        state=value.state,
        kind=value.kind,
        value=value.value,
        values=value.values,
        distribution=value.distribution,
        coverage=value.coverage,
        evidence_ids=(evidence_id,),
        method=value.method,
        confidence=value.confidence,
    )


def _with_evidence_ids(value: BuildingValue, evidence_ids: tuple[str, ...]) -> BuildingValue:
    if value.state is ValueState.UNKNOWN:
        return value
    return BuildingValue(
        state=value.state,
        kind=value.kind,
        value=value.value,
        values=value.values,
        distribution=value.distribution,
        coverage=value.coverage,
        evidence_ids=evidence_ids,
        method=value.method,
        confidence=value.confidence,
    )


def _layer_value(record: Mapping[str, object]) -> LayerValueRecord:
    return LayerValueRecord(
        building_id=record["building_id"],
        layer_id=record["layer_id"],
        value=BuildingValue(
            state=ValueState(record["state"]),
            kind=ValueKind(record["kind"]),
            value=record["value"],
            values=tuple(record.get("values", ())),
            distribution=dict(record.get("distribution", {})),
            coverage=record["coverage"],
            evidence_ids=tuple(record["evidence_ids"]),
            method=ValueMethod(record["method"]),
            confidence=Confidence(record["confidence"]),
        ),
    )


def _validate_references(release: ReleaseArtifact) -> None:
    source_ids = {source.source_id for source in release.sources}
    evidence_ids = {record.evidence_id for record in release.evidence}
    building_ids = {building.building_id for building in release.buildings}
    for evidence in release.evidence:
        if evidence.source_id not in source_ids:
            raise ValueError(f"orphan source for evidence {evidence.evidence_id}")
    for building in release.buildings:
        if building.source_id not in source_ids:
            raise ValueError(f"orphan source for building {building.building_id}")
    for layer_value in release.layer_values:
        if layer_value.building_id not in building_ids:
            raise ValueError(f"orphan building for layer value {layer_value.layer_id}")
        if layer_value.value.state is not ValueState.UNKNOWN and not layer_value.value.evidence_ids:
            raise ValueError(f"known layer value {layer_value.layer_id} has no evidence")
        for evidence_id in layer_value.value.evidence_ids:
            if evidence_id not in evidence_ids:
                raise ValueError(f"orphan evidence {evidence_id}")
