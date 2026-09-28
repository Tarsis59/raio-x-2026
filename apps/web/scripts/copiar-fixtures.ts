/**
 * Copia apps/web/fixtures/dados -> apps/web/public/dados, forçando meta.fixture=true.
 * Usado em desenvolvimento enquanto o job `exportar` do ETL real não existe.
 *
 * Rodar: pnpm --filter web dados:fixture
 */
import { cp, rm, readFile, writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const ORIGEM = path.join(AQUI, "..", "fixtures", "dados");
const DESTINO = path.join(AQUI, "..", "public", "dados");

async function principal() {
  await rm(DESTINO, { recursive: true, force: true });
  await mkdir(DESTINO, { recursive: true });
  await cp(ORIGEM, DESTINO, { recursive: true });

  const metaPath = path.join(DESTINO, "meta.json");
  const meta = JSON.parse(await readFile(metaPath, "utf8"));
  meta.fixture = true;
  await writeFile(metaPath, JSON.stringify(meta));

  console.log(`Fixtures copiadas para ${DESTINO} (meta.fixture=true)`);
}

await principal();
