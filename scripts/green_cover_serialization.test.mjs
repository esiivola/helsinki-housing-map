import test from "node:test";
import assert from "node:assert/strict";

import { serializeFeatures } from "./green_cover_serialization.mjs";

test("serializes every feature after the first with a separator", () => {
  assert.equal(
    serializeFeatures([{ id: 1 }, { id: 2 }], true),
    '{"id":1},{"id":2}',
  );
});

test("serializes a later page with a leading separator", () => {
  assert.equal(serializeFeatures([{ id: 3 }], false), ',{"id":3}');
});
