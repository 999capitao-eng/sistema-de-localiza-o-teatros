import time

import requests

from .config import USER_AGENT


def get_session():
    sessao = requests.Session()
    sessao.headers.update({"User-Agent": USER_AGENT})
    return sessao


def request_with_retry(sessao, metodo, url, retries=4, backoff=5, timeout=180, **kwargs):
    ultimo_erro = None
    for tentativa in range(1, retries + 1):
        try:
            resp = sessao.request(metodo, url, timeout=timeout, **kwargs)
            if resp.status_code in (429, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {resp.status_code}")
            resp.raise_for_status()
            return resp
        except requests.RequestException as erro:
            ultimo_erro = erro
            espera = backoff * tentativa
            print(f"[aviso] tentativa {tentativa}/{retries} falhou: {erro}. "
                  f"Aguardando {espera}s")
            time.sleep(espera)
    raise RuntimeError(f"Falha apos {retries} tentativas: {ultimo_erro}")
