export function serializeFeatures(features, first) {
  return features.map((feature, index) => `${first && index === 0 ? "" : ","}${JSON.stringify(feature)}`).join("");
}
