import defineConfig from "openapi-typescript";
export default defineConfig({
  input: "http://localhost:8000/openapi.json",
  output: "./lib/api/generated-types.ts",
});
