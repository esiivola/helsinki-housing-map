import { createReadStream, createWriteStream } from "node:fs";
import { rename } from "node:fs/promises";
import { basename } from "node:path";
import { spawn } from "node:child_process";
import { Transform } from "node:stream";
import { pipeline } from "node:stream/promises";

const prefix = Buffer.from('{"type":"FeatureCollection","features":[');
const comma = Buffer.from(",");
const defaultPaths = [
  "data/raw/hsy_maanpeite_muu_avoin_matala_kasvillisuus_2024.geojson",
  "data/raw/hsy_maanpeite_puusto_2_10m_2024.geojson",
  "data/raw/hsy_maanpeite_puusto_10_15m_2024.geojson",
  "data/raw/hsy_maanpeite_puusto_15_20m_2024.geojson",
  "data/raw/hsy_maanpeite_puusto_yli20m_2024.geojson",
];

class MissingFirstPageSeparators extends Transform {
  constructor() {
    super();
    this.pending = Buffer.alloc(0);
    this.prefixWritten = false;
    this.featureCount = 0;
    this.inserted = 0;
    this.depth = 0;
    this.inString = false;
    this.escaped = false;
    this.state = "feature";
  }

  _transform(chunk, _encoding, callback) {
    try {
      let input = chunk;
      if (!this.prefixWritten) {
        this.pending = Buffer.concat([this.pending, chunk]);
        if (this.pending.length < prefix.length) return callback();
        if (!this.pending.subarray(0, prefix.length).equals(prefix)) throw new Error("unexpected GeoJSON header");
        this.push(prefix);
        input = this.pending.subarray(prefix.length);
        this.pending = Buffer.alloc(0);
        this.prefixWritten = true;
      }

      const parts = [];
      let start = 0;
      for (let index = 0; index < input.length; index += 1) {
        const byte = input[index];
        if (this.depth > 0) {
          if (this.inString) {
            if (this.escaped) this.escaped = false;
            else if (byte === 92) this.escaped = true;
            else if (byte === 34) this.inString = false;
          } else if (byte === 34) this.inString = true;
          else if (byte === 123 || byte === 91) this.depth += 1;
          else if (byte === 125 || byte === 93) {
            this.depth -= 1;
            if (this.depth === 0) {
              if (byte !== 125) throw new Error("feature does not end with an object");
              this.featureCount += 1;
              this.state = "separator";
            }
          }
          continue;
        }

        if (this.state === "feature") {
          if (byte === 123) {
            this.depth = 1;
            continue;
          }
          if (byte === 93) {
            this.state = "collection-end";
            continue;
          }
          throw new Error(`expected a feature at ${this.featureCount + 1}`);
        }
        if (this.state === "separator") {
          if (byte === 44) {
            if (this.featureCount < 1_000) throw new Error("source already has a separator in the damaged first page");
            this.state = "feature";
            continue;
          }
          if (byte === 123 && this.featureCount < 1_000) {
            parts.push(input.subarray(start, index), comma);
            start = index;
            this.inserted += 1;
            this.depth = 1;
            this.state = "feature";
            continue;
          }
          if (byte === 93) {
            this.state = "collection-end";
            continue;
          }
          throw new Error(`expected a separator after feature ${this.featureCount}`);
        }
        if (this.state === "collection-end") {
          if (byte !== 125) throw new Error("expected GeoJSON collection end");
          this.state = "done";
          continue;
        }
        if (this.state === "done") throw new Error("data after GeoJSON collection end");
      }
      parts.push(input.subarray(start));
      this.push(Buffer.from(parts.length === 1 ? parts[0] : Buffer.concat(parts)));
      callback();
    } catch (error) {
      callback(error);
    }
  }

  _flush(callback) {
    if (!this.prefixWritten) return callback(new Error("file is shorter than the GeoJSON header"));
    if (this.depth !== 0 || this.inString || this.state !== "done") return callback(new Error("incomplete GeoJSON"));
    if (this.featureCount < 1_000 || this.inserted !== 999) return callback(new Error(`expected 999 missing separators in the first page, found ${this.inserted}`));
    callback();
  }
}

const replace = process.argv.includes("--replace");
const paths = process.argv.slice(2).filter((argument) => argument !== "--replace");

for (const path of paths.length ? paths : defaultPaths) {
  const repaired = `${path}.repaired`;
  await pipeline(createReadStream(path), new MissingFirstPageSeparators(), createWriteStream(repaired, { flags: "wx" }));
  await validateGeoJson(repaired);
  if (replace) {
    await rename(repaired, path);
    process.stderr.write(`${basename(path)}: repaired in place\n`);
  } else {
    process.stderr.write(`${basename(path)}: wrote ${basename(repaired)}; inspect it, then rerun with --replace\n`);
  }
}

async function validateGeoJson(path) {
  await new Promise((resolve, reject) => {
    const process = spawn(".venv/bin/python", ["-c", "import pyogrio, sys; pyogrio.read_info(sys.argv[1])", path], { stdio: ["ignore", "ignore", "pipe"] });
    let error = "";
    process.stderr.on("data", (chunk) => { error += chunk; });
    process.on("error", reject);
    process.on("exit", (code) => code === 0 ? resolve() : reject(new Error(`${basename(path)} failed GeoJSON validation: ${error.trim()}`)));
  });
}
