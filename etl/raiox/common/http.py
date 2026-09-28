"""Cliente HTTP padrão para fontes que não bloqueiam robôs (BCB, IBGE, Câmara, Senado, CGU, DataJud)."""

from __future__ import annotations

import ssl

import httpx
import truststore
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

USER_AGENT = "RaioX2026-ETL/1.0 (dados publicos, uso civico)"

# Usa o repositório de certificados do sistema operacional (necessário em máquinas com
# antivírus/proxy que inspecionam TLS; no Linux do CI é equivalente ao padrão).
_SSL = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


def cliente(**kw) -> httpx.Client:
    headers = {"user-agent": USER_AGENT, "accept": "application/json"}
    headers.update(kw.pop("headers", {}))
    return httpx.Client(headers=headers, timeout=kw.pop("timeout", 60), follow_redirects=True,
                        verify=_SSL, **kw)


def _transitorio(e: BaseException) -> bool:
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code in (408, 429, 500, 502, 503, 504)
    return isinstance(e, httpx.TransportError)


@retry(retry=retry_if_exception(_transitorio), stop=stop_after_attempt(5),
       wait=wait_exponential(min=2, max=60), reraise=True)
def get_json(c: httpx.Client, url: str, **kw):
    r = c.get(url, **kw)
    r.raise_for_status()
    return r.json()


@retry(retry=retry_if_exception(_transitorio), stop=stop_after_attempt(5),
       wait=wait_exponential(min=2, max=60), reraise=True)
def get_bytes(c: httpx.Client, url: str, **kw) -> tuple[bytes, str | None]:
    r = c.get(url, **kw)
    r.raise_for_status()
    return r.content, r.headers.get("content-type")
