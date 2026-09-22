const labels: Record<string, string> = {
  omakotitalo: "omakotitalo",
  paritalo: "paritalo",
  rivitalo: "rivitalo",
  kerrostalo: "kerrostalo",
  yes: "kyllä",
  water_central: "vesikeskuslämmitys",
  air_central: "ilmakeskuslämmitys",
  direct_electric: "suora sähkölämmitys",
  stove: "uunilämmitys",
  no_fixed_heating: "ei kiinteää lämmityslaitetta",
  district_or_local_heat: "kauko- tai aluelämpö",
  light_fuel_oil: "kevyt polttoöljy",
  heavy_fuel_oil: "raskas polttoöljy",
  electricity: "sähkö",
  gas: "kaasu",
  coal_or_coke: "kivihiili, koksi tms.",
  wood: "puu",
  peat: "turve",
  ground_source_heat: "maalämpö tms.",
  other: "muu",
  owned: "oma",
  leased: "vuokrattu",
  mixed: "sekoittunut",
  city: "kaupunki",
  city_owned: "kaupungin omistama",
  lease_area: "vuokra-alue",
  non_city: "muu omistaja",
  unknown: "tuntematon",
};

const caveats: Record<string, string> = {
  "accessibility-evidence": "Rannan saavutettavuus perustuu reitti- ja käyttöoikeusnäyttöön.",
  "configured-cycling-speed": "Pyöräilyaika perustuu asetettuun keskinopeuteen.",
  "evidence-based-not-title-search": "Tulos perustuu myönteiseen lähdenäyttöön, ei viralliseen omistusoikeusselvitykseen.",
  "derived-owner-classification": "Muu omistaja on johdettu jäännösluokka, ei kiinteistörekisterin omistajatieto.",
  "failed-samples-visible": "Epäonnistuneet reittinäytteet säilyvät osittaisena tietona.",
  "helsinki-only-building-register": "Rakennusrekisteritieto on saatavilla vain Helsingistä.",
  "helsinki-only-noise": "Yömelumalli on saatavilla vain Helsingistä.",
  "helsinki-only-planning": "Vireillä olevien asemakaavojen tieto on saatavilla vain Helsingistä.",
  "incompatible-vintages-not-merged": "Eri laskentatapoja tai vuosikertoja ei yhdistetä numeerisesti.",
  "land-cover-resolution": "Maapeitteen luokitus ja tarkkuus rajoittavat tulosta.",
  "local-only-data": "Tämä tieto on käytettävissä vain tällä koneella eikä sisälly julkiseen julkaisuun.",
  "modeled-indicative": "Melu on mallinnettu, suuntaa-antava arvio.",
  "older-records-may-be-uncertain": "Vanhoissa rakennustiedoissa voi olla epävarmuutta.",
  "osm-completeness": "OSM-aineiston kattavuus ja reititettävyys vaihtelevat alueittain.",
  "postal-area-context": "Arvo kuvaa postinumeroaluetta, ei yksittäistä rakennusta.",
  "planning-area-not-construction": "Vireillä oleva asemakaava-alue ei ennusta rakentamisen ajankohtaa, laajuutta tai häiriötä.",
  "representative-weekday": "Joukkoliikenne perustuu yhteen edustavaan arkipäivään.",
  "routing-origin-fallback": "Lähtöpiste voi olla rakennuksen sisäisen sisäänkäynnin sijaan lähin reititettävä piste.",
  "suppressed-values-unknown": "Salattu lähdearvo esitetään tuntemattomana.",
  "unmapped-codes-are-unknown": "Lähdekoodia ei voitu luokitella, joten arvo on tuntematon.",
  "zone-upper-bound-not-building-maximum": "Arvo on osuvan meluvyöhykkeen yläraja, ei rakennuksessa mitattu enimmäismelu.",
};

const licences: Record<string, string> = {
  "CC-BY-4.0": "CC BY 4.0",
  "ODbL-1.0": "OpenStreetMap ODbL",
  open: "avoin data",
};

const sourceSummaries: Record<string, { title: string; description: string }> = {
  hsy_buildings: { title: "Rakennukset · HSY", description: "Rakennusten sijainti, talotyyppi, rakennusvuosi, lämmitys, hissi ja kerrosluku." },
  paavo_income: { title: "Mediaanitulot · Tilastokeskus (Paavo)", description: "Postinumeroalueen tulotaso – kontekstitieto, ei rakennuskohtainen." },
  helsinki_noise_2022: { title: "Päivämelu · Helsingin kaupunki", description: "Tieliikenteen päivämelun vyöhykkeet (vain Helsinki)." },
  helsinki_noise_night_2022: { title: "Yömelu · Helsingin kaupunki", description: "Tieliikenteen yömelun vyöhykkeet (vain Helsinki)." },
  helsinki_active_plans: { title: "Asemakaavat · Helsingin kaupunki", description: "Vireillä olevat asemakaava-alueet (vain Helsinki)." },
  vantaa_property_map: { title: "Tontit · Vantaan kaupunki", description: "Vantaan kiinteistökartan hallinta- ja lisätiedot." },
  hsl_osm_extract: { title: "Katu- ja pyöräverkko · OpenStreetMap", description: "Kävely- ja pyörämatkojen reititys sekä taustakartta." },
  hsl_gtfs: { title: "Joukkoliikenne · HSL", description: "Aikataulut aamun joukkoliikennematkojen laskentaan." },
  helsinki_cycle_network: { title: "Pääpyöräreitit · Helsingin kaupunki", description: "Helsingin pääpyöräverkko (vain Helsinki)." },
  hsy_green_cover_2024: { title: "Vihreä peite · HSY (maapeite 2024)", description: "Vihreän peitteen osuus rakennuksen ympäristössä." },
};

export function finnishValue(value: string): string {
  return labels[value] ?? value;
}

export function finnishCaveat(value: string): string {
  return caveats[value] ?? value;
}

const units: Record<string, string> = {
  year: "",
};

const methodologies: Record<string, string> = {
  "Direct Helsinki building-register code mapping for the main heating energy source.": "Suora koodikartoitus Helsingin rakennusrekisteristä päälämmitysenergian lähteelle.",
  "Direct Helsinki building-register code mapping for the main heating method.": "Suora koodikartoitus Helsingin rakennusrekisteristä päälämmitystavalle.",
  "Direct Helsinki building-register dwelling count.": "Suora asuinhuoneistojen määrä Helsingin rakennusrekisteristä.",
  "Direct Helsinki building-register lift indicator; a blank indicator remains unknown.": "Suora hissitieto Helsingin rakennusrekisteristä; tyhjä tieto jää tuntemattomaksi.",
  "Direct Helsinki building-register storey count.": "Suora kerrosluku Helsingin rakennusrekisteristä.",
  "Direct building-record value with at-least-one-value matching.": "Suora rakennustietue, jossa vähintään yksi arvo täsmää.",
  "Direct municipal Building Classification 2018 mapping where available; unmapped classes remain unknown.": "Suora kuntien rakennusluokitus 2018 -kartoitus, kun saatavilla; luokittelemattomat luokat jäävät tuntemattomiksi.",
  "Offline GTFS routing every 5 minutes from 07:00 through 08:00 on a representative weekday.": "GTFS-reititys viiden minuutin välein klo 07:00–08:00 edustavana arkipäivänä.",
  "Offline bicycle-network route time to Helsinki Central Railway Station.": "Pyöräverkon ajoaika Helsingin päärautatieasemalle.",
  "Offline building-footprint intersection with Helsinki active detailed-plan areas.": "Rakennuksen pohjan leikkaus Helsingin vireillä olevien asemakaava-alueiden kanssa.",
  "Offline cycling-network route length divided by 15 km/h.": "Pyöräverkon reitin pituus jaettuna nopeudella 15 km/h.",
  "Offline intersection of HSY 2024 vegetation classes with a 300 m point buffer.": "HSY:n 2024 kasvillisuusluokkien leikkaus 300 m puskurin kanssa.",
  "Offline maximum db_hi of Helsinki LAeq 22-7 zones intersecting the footprint.": "Suurin db_hi Helsingin LAeq 22–7 -yövyöhykkeistä, jotka leikkaavat rakennuksen.",
  "Offline maximum db_hi of compatible LAeq 7-22 zones intersecting the footprint.": "Suurin db_hi yhteensopivista LAeq 7–22 -päivävyöhykkeistä, jotka leikkaavat rakennuksen.",
  "Offline pedestrian-network distance to OSM amenity=clinic, doctors, or hospital.": "Kävelyverkon etäisyys OSM-kohteisiin klinikka, lääkäri tai sairaala.",
  "Offline pedestrian-network distance to OSM amenity=kindergarten or amenity=childcare.": "Kävelyverkon etäisyys OSM-kohteisiin päiväkoti tai lastenhoito.",
  "Offline pedestrian-network distance to OSM amenity=library.": "Kävelyverkon etäisyys OSM-kirjastoon.",
  "Offline pedestrian-network distance to OSM amenity=school.": "Kävelyverkon etäisyys OSM-kouluun.",
  "Offline pedestrian-network distance to OSM grocery, convenience, or supermarket POI.": "Kävelyverkon etäisyys OSM:n ruoka-, lähi- tai supermarketkohteeseen.",
  "Offline pedestrian-network distance to a source-designated forest polygon.": "Kävelyverkon etäisyys lähteen määrittämään metsäalueeseen.",
  "Offline pedestrian-network distance to an OSM supermarket POI.": "Kävelyverkon etäisyys OSM-supermarkettiin.",
  "Offline pedestrian-network distance to an accessible Baltic Sea shoreline.": "Kävelyverkon etäisyys saavutettavaan Itämeren rantaviivaan.",
  "Offline postal-area assignment; suppressed source values are unknown.": "Postinumeroalueen määritys; salatut lähdearvot ovat tuntemattomia.",
  "Offline sampled HSL routing; minimi, mediaani ja maksimi ovat lähtöaikojen yhteenvetoja.": "Otospohjainen HSL-reititys; minimi, mediaani ja maksimi ovat lähtöaikojen yhteenvetoja.",
  "Offline straight-line distance from building representative point to the published route network.": "Linnuntie-etäisyys rakennuksen edustavasta pisteestä julkaistuun reittiverkkoon.",
  "Helsinki uses a local derived city-or-other-owner classification; Espoo uses full-footprint city-land evidence only.": "Helsingissä käytetään paikallista johdettua kaupunki–muu omistaja -luokitusta; Espoossa vain koko rakennuksen kattavaa kaupungin maan näyttöä.",
};

export function finnishLicence(value: string): string {
  return licences[value] ?? value;
}

export function finnishUnit(value: string | null): string {
  if (value === null) return "";
  return units[value] ?? value;
}

export function unitSuffix(value: string | null): string {
  const label = finnishUnit(value);
  return label ? ` ${label}` : "";
}

export function finnishMethodology(value: string): string {
  return methodologies[value] ?? value;
}

export function finnishSource(sourceId: string, fallbackName: string): { title: string; description: string } {
  return sourceSummaries[sourceId] ?? { title: fallbackName, description: "" };
}
