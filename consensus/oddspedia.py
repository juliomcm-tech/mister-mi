"""Read the user-authorized feed without publishing credentials or raw responses.

This connection is separate from prediction votes. Until its event/market schema
is mapped and tested, a successful JSON response is not an analysed selection.
"""
from datetime import datetime, timezone
from html import unescape
from urllib.parse import parse_qs, urlsplit, urlencode
import json
import os
import re

from .sources import Client

PUBLIC_URL = "https://widgets.oddspedia.com/"
_VISIBLE_KEY = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,39}$")
_PRIVATE_KEY = re.compile(r"token|secret|key|auth|password|cookie|url|link|email|user|account|affiliate", re.I)


def validate_feed_url(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Guarda o link completo da primeira linha da Oddspedia no Secret ODDSPEDIA_FEED_URL.")
    value = unescape(value.strip())
    if len(value) > 8192 or re.search(r"[\s<>\\\"']", value):
        raise ValueError("ODDSPEDIA_FEED_URL deve conter só o URL completo, sem HTML, JSON ou formatação de mensagem.")
    try:
        url = urlsplit(value)
        allowed = (url.scheme == "https" and url.hostname == "widgets.oddspedia.com"
                   and url.port in (None, 443) and not url.username and not url.password
                   and not url.fragment and url.path in {"/api/matches", "/api/sports"})
        tokens = parse_qs(url.query, keep_blank_values=True).get("api_token", [])
    except (ValueError, TypeError):
        allowed, tokens = False, []
    if not allowed or len(tokens) != 1 or not 12 <= len(tokens[0]) <= 2048 or re.search(r"\s", tokens[0]):
        raise ValueError("Copia o link completo junto de OPEN, incluindo api_token e lang, para ODDSPEDIA_FEED_URL.")
    if tokens[0].lower() in {"oculta", "your_api_token", "your_api_key"} or re.fullmatch(r"[xX]+", tokens[0]):
        raise ValueError("O Secret contém uma chave de exemplo. Usa o link com a chave real da tua conta Oddspedia.")
    return value


def _shape(value, depth=0):
    """Only field names and types; never an API value or URL."""
    if depth >= 3 and isinstance(value, (list, dict)):
        return "array" if isinstance(value, list) else "object"
    if isinstance(value, dict):
        return {key: _shape(item, depth + 1) for key, item in list(value.items())[:40]
                if isinstance(key, str) and _VISIBLE_KEY.fullmatch(key) and not _PRIVATE_KEY.search(key)}
    if isinstance(value, list):
        return [_shape(value[0], depth + 1)] if value else []
    return "null" if value is None else "boolean" if isinstance(value, bool) else "number" if isinstance(value, (int, float)) else "string"


def _records(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("matches", "events", "data", "results", "items", "rows"):
            if isinstance(data.get(key), list):
                return data[key]
    return None


def _read_endpoint(client, endpoint, token, language, query=None):
    """Only documented calls. Response values remain inside this function."""
    params = {"api_token": token, "lang": language}
    if query is not None:
        params["q"] = query
    url = PUBLIC_URL.rstrip("/") + endpoint + "?" + urlencode(params)
    result = {"endpoint": endpoint}
    if query is not None:
        result["query"] = query
    try:
        raw = client.get(url, check_robots=False, headers={"Accept": "application/json"})
    except Exception as exc:
        status = getattr(exc, "code", None)
        if not isinstance(status, int):
            match = re.fullmatch(r"HTTP (\d{3})", str(exc))
            status = int(match[1]) if match else None
        message = f"A Oddspedia recusou {endpoint} (HTTP {status})." if status else f"Não foi possível contactar {endpoint} nesta recolha."
        return {**result, "status": "error", "reason": "request_failed", "http_status": status, "message": message}, None
    # This provider can return the exact plain text "Empty data" instead of JSON.
    if isinstance(raw, str) and re.sub(r"\s+", "", raw).casefold() == "emptydata":
        return {**result, "status": "empty", "reason": "empty_response", "records_received": 0,
                "message": "A Oddspedia devolveu «Empty data» para este pedido."}, None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return {**result, "status": "error", "reason": "invalid_response", "message": "O pedido não devolveu JSON válido."}, None
    if isinstance(data, str) and re.sub(r"\s+", "", data).casefold() == "emptydata":
        return {**result, "status": "empty", "reason": "empty_response", "records_received": 0,
                "message": "A Oddspedia devolveu «Empty data» para este pedido."}, None
    if not isinstance(data, (dict, list)) or isinstance(data, dict) and (data.get("error") or data.get("errors") or data.get("success") is False or data.get("status") in ("error", "failed", False)):
        return {**result, "status": "error", "reason": "api_error", "message": "A API devolveu um erro. Confirma o acesso da conta Oddspedia."}, None
    rows = _records(data)
    empty = rows == []
    return {**result, "status": "empty" if empty else "ok", "reason": "empty_response" if empty else None,
            "records_received": len(rows) if rows is not None else None, "response_shape": _shape(data),
            "message": "O pedido não devolveu registos." if empty else "Recebida uma resposta JSON."}, data


def _search_queries(queries, token):
    result = []
    for value in queries or []:
        if not isinstance(value, str):
            continue
        query = " ".join(value.split()).casefold()
        if not 2 <= len(query) <= 100 or token.casefold() in query or "http:" in query or "https:" in query:
            continue
        if query not in result:
            result.append(query)
        if len(result) == 6:
            break
    return result


def collect_oddspedia_feed(now=None, *, feed_url=None, client=None, queries=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must contain a timezone")
    value = os.environ.get("ODDSPEDIA_FEED_URL", "") if feed_url is None else feed_url
    result = {"id": "oddspedia", "name": "Oddspedia API", "configured": bool(value),
              "checked_at": now.astimezone(timezone.utc).isoformat(), "url": PUBLIC_URL,
              "counts_as_prediction": False, "used_in_analysis": False,
              "strategy": "documented_catalogue_and_search"}
    if not value:
        return {**result, "status": "not_configured", "message": "ODDSPEDIA_FEED_URL ainda não está disponível na recolha do GitHub."}
    try:
        url = validate_feed_url(value)
    except ValueError as exc:
        return {**result, "status": "error", "reason": "invalid_configuration", "message": str(exc)}
    params = parse_qs(urlsplit(url).query)
    token = params["api_token"][0]
    language = params.get("lang", ["en"])[0]
    if not re.fullmatch(r"[a-zA-Z-]{2,8}", language):
        language = "en"
    # GitHub masks the full Secret by default; register the extracted token too.
    if os.environ.get("GITHUB_ACTIONS") == "true":
        if not re.search(r"[\r\n]", token):
            print("::add-mask::" + token.replace("%", "%25"))
    client = client or Client()
    catalogue, data = _read_endpoint(client, "/api/sports", token, language)
    result.update({**catalogue, "catalogue": catalogue, "searches": []})
    if catalogue["status"] != "ok":
        return result  # A refusal stops this attempt; no route probing or retries.
    rows = _records(data)
    if not rows or not all(isinstance(row, dict) and {"id", "slug", "match_count"}.issubset(row)
                           and type(row["id"]) is int and row["id"] > 0
                           and type(row["match_count"]) is int and row["match_count"] >= 0 for row in rows):
        return {**result, "status": "error", "reason": "unexpected_catalogue",
                "message": "O pedido documentado de desportos devolveu um formato ainda não reconhecido."}
    result.update(kind="sports_catalogue", sports_count=len(rows),
                  message=f"Recebido o catálogo de {len(rows)} desportos. As contagens não são jogos analisados.")
    search_queries = _search_queries(queries, token)
    for query in search_queries:
        search, _ = _read_endpoint(client, "/api/search", token, language, query)
        result["searches"].append(search)
        if search["status"] == "error":
            break
    if not search_queries:
        result.update(status="partial", reason="catalogue_only")
    elif any(row["status"] == "error" for row in result["searches"]):
        result.update(status="partial", reason="search_failed", message="O catálogo respondeu, mas uma pesquisa foi recusada ou falhou. Os dados ainda não entram na análise.")
    else:
        received = sum(row.get("records_received") or 0 for row in result["searches"])
        result.update(search_records_received=received,
                      status="ok" if received else "empty", reason=None if received else "empty_searches",
                      message=(f"Catálogo recebido e {received} registos devolvidos nas pesquisas de equipas. Podem repetir jogos; formato em validação."
                               if received else "O catálogo respondeu, mas as pesquisas das equipas não devolveram jogos. «Empty data» é uma resposta vazia, distinta de HTTP 403."))
    return result
