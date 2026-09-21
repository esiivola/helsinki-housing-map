function decompressedBody(response: Response, path: string): ReadableStream<Uint8Array> {
  if (!response.ok || !response.body) {
    throw new Error(`Static data request failed: ${path}`);
  }
  return response.headers.get("content-encoding") === "gzip"
    ? response.body
    : response.body.pipeThrough(new DecompressionStream("gzip"));
}

export async function loadGzipJson<T>(path: string): Promise<T> {
  const body = decompressedBody(await fetch(path), path);
  try {
    return JSON.parse(await new Response(body).text()) as T;
  } catch (error) {
    throw new Error(`Invalid static data: ${path}`, { cause: error });
  }
}

// Decompress a gzipped JSON asset to a blob: URL without parsing it on the main
// thread. Handing this URL to a MapLibre GeoJSON source lets MapLibre fetch and
// parse the payload inside its own worker, so a large background layer never
// blocks the main thread with a multi-megabyte JSON.parse. Revoke the URL once
// the source has loaded.
export async function loadGzipObjectUrl(path: string): Promise<string> {
  const body = decompressedBody(await fetch(path), path);
  const blob = await new Response(body, { headers: { "content-type": "application/json" } }).blob();
  return URL.createObjectURL(blob);
}
