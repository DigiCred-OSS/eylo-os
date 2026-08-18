import { mkdir, rename, writeFile } from "node:fs/promises";
import path from "node:path";

import openapiTS, { astToString } from "openapi-typescript";

const source = new URL(
  process.env.EYLO_OPENAPI_URL ?? "http://127.0.0.1:8000/openapi.json",
);
const outputDirectory = path.resolve("src/api/generated");
const outputPath = path.join(outputDirectory, "schema.d.ts");
const temporaryPath = `${outputPath}.tmp`;

try {
  const schema = await openapiTS(source);
  const declaration = astToString(schema);

  await mkdir(outputDirectory, { recursive: true });
  await writeFile(temporaryPath, declaration, "utf8");
  await rename(temporaryPath, outputPath);

  console.log(
    `Generated ${path.relative(process.cwd(), outputPath)} from ${source}`,
  );
} catch (error) {
  const reason = error instanceof Error ? error.message : String(error);
  console.error(
    `Unable to generate the API contract from ${source}: ${reason}`,
  );
  process.exitCode = 1;
}
