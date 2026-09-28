"""Cliente do DivulgaCandContas (TSE) via Chromium real.

O TSE fica atrás do Akamai Bot Manager, que bloqueia clientes HTTP comuns e o Chromium
"HeadlessChrome". O que funciona (verificado em 27/09/2026): Chromium no modo *new headless*
(channel="chromium") com user-agent de Chrome normal, fazendo `fetch` de dentro de uma aba
aberta no próprio domínio. Veja docs/fontes/TSE.md.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import logging
import random
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

log = logging.getLogger("raiox.tse")

BASE = "https://divulgacandcontas.tse.jus.br"
API = f"{BASE}/divulga/rest/v1"

_JS_TEXTO = """async (url) => {
  const r = await fetch(url, {headers: {accept: 'application/json'}});
  const t = await r.text();
  return [r.status, t];
}"""

_JS_BYTES = """async (url) => {
  const r = await fetch(url);
  if (!r.ok) return [r.status, null, null];
  const buf = new Uint8Array(await r.arrayBuffer());
  let bin = '';
  for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
  return [r.status, r.headers.get('content-type'), btoa(bin)];
}"""


class ErroTSE(Exception):
    def __init__(self, status: int, url: str):
        super().__init__(f"TSE respondeu {status} para {url}")
        self.status = status
        self.url = url


class ClienteTSE:
    """Uso:

        async with ClienteTSE(concorrencia=8) as tse:
            dados = await tse.json("/candidatura/listar/2026/SP/20322002026/6/candidatos")
    """

    def __init__(self, concorrencia: int = 8, headless: bool = True):
        self.concorrencia = concorrencia
        self.headless = headless
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._ctx: BrowserContext | None = None
        self._paginas: asyncio.Queue[Page] = asyncio.Queue()

    async def __aenter__(self) -> ClienteTSE:
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=self.headless,
            channel="chromium",
            args=["--disable-blink-features=AutomationControlled"],
        )
        versao = self._browser.version.split(".")[0]
        ua = (f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              f"Chrome/{versao}.0.0.0 Safari/537.36")
        self._ctx = await self._browser.new_context(locale="pt-BR", user_agent=ua)
        for _ in range(self.concorrencia):
            await self._paginas.put(await self._nova_pagina())
        return self

    async def _nova_pagina(self) -> Page:
        assert self._ctx is not None
        pagina = await self._ctx.new_page()
        r = await pagina.goto(f"{API}/eleicao/ordinarias", wait_until="domcontentloaded")
        if r is None or r.status != 200:
            await pagina.close()
            raise ErroTSE(r.status if r else 0, "sessão inicial")
        return pagina

    async def __aexit__(self, *exc: Any) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    async def _chamar(self, js: str, url: str, tentativas: int = 5) -> list[Any]:
        ultimo: Exception | None = None
        for tentativa in range(tentativas):
            pagina = await self._paginas.get()
            devolver = pagina
            try:
                resultado = await pagina.evaluate(js, url)
                status = resultado[0]
                if status in (403, 429) or status >= 500:
                    ultimo = ErroTSE(status, url)
                    await asyncio.sleep(2 ** tentativa + random.random() * 2)
                    if status == 403:  # Akamai revogou a sessão: recria a aba
                        await pagina.close()
                        devolver = await self._nova_pagina()
                    continue
                return resultado
            except Exception as e:  # noqa: BLE001 — erro de navegação/avaliação: recria a página
                ultimo = e
                with contextlib.suppress(Exception):
                    await pagina.close()
                await asyncio.sleep(2 ** tentativa)
                devolver = await self._nova_pagina()
            finally:
                await self._paginas.put(devolver)
        raise ultimo or ErroTSE(0, url)

    async def json(self, caminho: str) -> Any | None:
        """GET em `API + caminho` (ou URL absoluta). Retorna None em 404."""
        url = caminho if caminho.startswith("http") else f"{API}{caminho}"
        status, texto = await self._chamar(_JS_TEXTO, url)
        if status == 404:
            return None
        if status != 200:
            raise ErroTSE(status, url)
        return json.loads(texto) if texto else None

    async def arquivo(self, id_arquivo: int) -> tuple[bytes, str | None] | None:
        """Baixa um documento do registro. None se indisponível ou aguardando anonimização."""
        return await self.binario(f"{BASE}/divulga/rest/arquivo/doc/{id_arquivo}")

    async def binario(self, url: str) -> tuple[bytes, str | None] | None:
        status, mime, b64 = await self._chamar(_JS_BYTES, url)
        if status != 200 or b64 is None:
            return None
        conteudo = base64.b64decode(b64)
        return (conteudo, mime) if conteudo else None
