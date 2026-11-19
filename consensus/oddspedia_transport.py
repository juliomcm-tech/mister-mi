"""One ordinary HTTPS request; classify failures without exposing response data."""
import re
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

from .sources import USER_AGENT


class ApiAccessError(RuntimeError):
    def __init__(self, status, reason, message, response_type="unknown"):
        self.code, self.reason, self.response_type = status, reason, response_type
        super().__init__(message)


def classify_denial(status, headers, body):
    text = body.casefold()
    kind = "json" if "json" in headers.get("Content-Type", "").casefold() else "html" if "<html" in text or "<!doctype html" in text else "text"
    challenge = (headers.get("cf-mitigated", "").casefold() == "challenge"
                 or any(marker in text for marker in ("verify you are human", "enable javascript and cookies to continue",
                                                       "checking your browser", "automated traffic", "automated requests")))
    if challenge:
        return ApiAccessError(status, "provider_challenge", "A resposta exige verificação de navegador ou recusa tráfego automatizado. O coletor não tenta contornar essa verificação.", kind)
    if any(marker in text for marker in ("invalid domain", "domain not licensed", "domain is not licensed", "domain not authorized", "domain not authorised")):
        return ApiAccessError(status, "domain_rejected", "A resposta indica um domínio não autorizado. Confirma o domínio e o acesso da conta Oddspedia.", kind)
    if any(marker in text for marker in ("invalid api token", "invalid api_token", "invalid token", "token is invalid", "invalid api key", "api key is invalid", "expired token", "api token has expired")):
        return ApiAccessError(status, "credential_rejected", "A resposta indica uma chave inválida ou expirada. Confirma a chave na Oddspedia e atualiza o Secret.", kind)
    if any(marker in text for marker in ("account not approved", "api access disabled", "api access is disabled", "account is not activated", "no bookmakers configured")):
        return ApiAccessError(status, "account_rejected", "A resposta indica que o acesso ou a configuração da conta ainda não permite este pedido.", kind)
    if status == 429:
        return ApiAccessError(status, "rate_limited", "A Oddspedia limitou os pedidos. A próxima tentativa fica adiada.", kind)
    if status in (301, 302, 303, 307, 308):
        return ApiAccessError(status, "unexpected_redirect", "O endpoint redirecionou o pedido. A credencial não foi enviada para outro endereço.", kind)
    return ApiAccessError(status, "access_denied" if status in (401, 403) else "request_failed",
                          f"O pedido recebeu HTTP {status}; a resposta não esclareceu se a causa é a chave, a conta ou uma restrição de acesso.", kind)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OddspediaClient:
    def get(self, url, *, headers=None, check_robots=False):
        target = urlsplit(url)
        if (target.scheme != "https" or target.hostname != "widgets.oddspedia.com"
                or target.port not in (None, 443) or target.username or target.password
                or target.path not in {"/api/sports", "/api/search"}):
            raise ApiAccessError(None, "invalid_target", "O pedido não aponta para um endpoint autorizado da Oddspedia.")
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})})
        try:
            with build_opener(_NoRedirect()).open(request, timeout=18) as response:
                raw = response.read(5_000_001)
                if len(raw) > 5_000_000:
                    raise ApiAccessError(response.status, "response_too_large", "A resposta ultrapassou o limite de tamanho.")
                text = raw.decode("utf-8", errors="replace")
                if re.search(r"<\s*(?:!doctype\s+html|html)\b", text, re.I):
                    error = classify_denial(response.status, response.headers, text[:100_000])
                    if error.reason == "request_failed":
                        error = ApiAccessError(response.status, "unexpected_html", "O endereço devolveu uma página HTML em vez dos dados JSON da API.", "html")
                    raise error
                return text
        except HTTPError as error:
            body = error.read(100_000).decode("utf-8", errors="replace")
            raise classify_denial(error.code, error.headers, body) from None
