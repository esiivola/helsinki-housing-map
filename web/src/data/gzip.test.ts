import { afterEach, describe, expect, it, vi } from "vitest";

import { loadGzipJson, loadGzipObjectUrl } from "./gzip";

afterEach(() => vi.unstubAllGlobals());

describe("loadGzipJson", () => {
  it("reads a gzip-compressed local static artifact", async () => {
    const bytes = await new Response(
      new Blob(['{"source":"local"}']).stream().pipeThrough(new CompressionStream("gzip")),
    ).arrayBuffer();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(bytes)));

    await expect(loadGzipJson<{ source: string }>("data/fixture.json.gz")).resolves.toEqual({
      source: "local",
    });
  });

  it("does not decompress a response the local server has already decoded", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"source":"local"}', {
      headers: { "content-encoding": "gzip" },
    })));

    await expect(loadGzipJson<{ source: string }>("data/fixture.json.gz")).resolves.toEqual({
      source: "local",
    });
  });

  it("reports a scoped request failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 404 })));

    await expect(loadGzipJson("data/missing.json.gz")).rejects.toThrow(
      "Static data request failed: data/missing.json.gz",
    );
  });

  it("identifies a malformed static artifact", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{')));

    await expect(loadGzipJson("data/broken.json.gz")).rejects.toThrow(
      "Invalid static data: data/broken.json.gz",
    );
  });
});

describe("loadGzipObjectUrl", () => {
  it("decompresses to a blob URL without parsing the payload on the caller thread", async () => {
    const payload = '{"type":"FeatureCollection","features":[]}';
    const bytes = await new Response(
      new Blob([payload]).stream().pipeThrough(new CompressionStream("gzip")),
    ).arrayBuffer();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(bytes)));
    let captured: Blob | undefined;
    const createObjectURL = vi.spyOn(URL, "createObjectURL").mockImplementation((blob) => {
      captured = blob as Blob;
      return "blob:mock-url";
    });

    const url = await loadGzipObjectUrl("data/background.geojson.gz");
    expect(url).toBe("blob:mock-url");
    expect(await captured!.text()).toBe(payload);
    createObjectURL.mockRestore();
  });

  it("reports a scoped request failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 404 })));

    await expect(loadGzipObjectUrl("data/missing.geojson.gz")).rejects.toThrow(
      "Static data request failed: data/missing.geojson.gz",
    );
  });
});
