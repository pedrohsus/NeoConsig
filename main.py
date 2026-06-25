import os
import time
import json
import logging
import re
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("neoconsig")
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler("consultas.log", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(file_handler)

SENSITIVE_KEYS = {"client_secret", "access_token", "Authorization", "authorization"}


def _sanitize_headers(headers: dict) -> dict:
    sanitized = {}
    for k, v in headers.items():
        if k in SENSITIVE_KEYS or k.lower() == "authorization":
            sanitized[k] = "***REDACTED***"
        else:
            sanitized[k] = v
    return sanitized


def _sanitize_body(body: dict | str | None) -> dict | str | None:
    if body is None:
        return None
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            return body
    if isinstance(body, dict):
        return {k: ("***REDACTED***" if k in SENSITIVE_KEYS else v) for k, v in body.items()}
    return body


def log_request(method: str, url: str, headers: dict, body=None, params: dict | None = None):
    ts = datetime.now(timezone.utc).isoformat()
    entry = {
        "timestamp": ts,
        "direction": "REQUEST",
        "method": method,
        "url": str(url),
        "params": params,
        "headers": _sanitize_headers(dict(headers)),
        "body": _sanitize_body(body),
    }
    logger.info(json.dumps(entry, ensure_ascii=False, indent=2))


def log_response(status_code: int, headers: dict, body: str):
    ts = datetime.now(timezone.utc).isoformat()
    try:
        parsed_body = json.loads(body)
        parsed_body = _sanitize_body(parsed_body)
    except (json.JSONDecodeError, TypeError):
        parsed_body = body
    entry = {
        "timestamp": ts,
        "direction": "RESPONSE",
        "status_code": status_code,
        "headers": _sanitize_headers(dict(headers)),
        "body": parsed_body,
    }
    logger.info(json.dumps(entry, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# API NeoConsig — Produção (Cred BR)
# ---------------------------------------------------------------------------
BASE_URL = os.getenv("NEOCONSIG_BASE_URL", "https://wsst.neoconsig.com.br")
TOKEN_URL = f"{BASE_URL}/api-integracao/v1/oauth/token"
MARGEM_URL = f"{BASE_URL}/api-integracao/v2/consultar-margem"

CLIENT_ID = os.getenv("NEOCONSIG_CLIENT_ID", "81")
CLIENT_SECRET = os.getenv("NEOCONSIG_CLIENT_SECRET", "DLegtjCy7BQVfjxWDUNvfzneOb4xAYQMmSUIunOZ")

CONVENIOS = {
    "8": "Goiás",
    "70": "São Gonçalo",
    "48": "Sorocaba",
    "13": "São Luís",
    "67": "Hortolândia",
}


async def _get_token(client: httpx.AsyncClient) -> str:
    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }

    t0 = time.monotonic()
    log_request("POST", TOKEN_URL, {"Content-Type": "application/json"}, body=payload)

    resp = await client.post(
        TOKEN_URL,
        json=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )

    auth_time = time.monotonic() - t0
    log_response(resp.status_code, dict(resp.headers), resp.text)
    logger.info(json.dumps({"auth_seconds": round(auth_time, 2)}))
    resp.raise_for_status()

    data = resp.json()
    return data["access_token"]


async def consultar_margem(cpf: str, matricula: str, cod_banco: str, cod_convenio: str, token_consig: str, senha: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        access_token = await _get_token(client)

        params = {
            "codBanco": cod_banco,
            "codConvenio": cod_convenio,
            "cpf": cpf,
            "matricula": matricula,
        }
        if token_consig.strip():
            params["token"] = token_consig.strip()
        if senha.strip():
            params["senha"] = senha.strip()

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json; charset=utf-8",
        }

        t0 = time.monotonic()
        log_request("GET", MARGEM_URL, headers, params=params)

        resp = await client.get(MARGEM_URL, params=params, headers=headers)

        query_time = time.monotonic() - t0
        log_response(resp.status_code, dict(resp.headers), resp.text)
        logger.info(json.dumps({"query_seconds": round(query_time, 2)}))

        result = {"status_code": resp.status_code, "url_usada": str(resp.url)}
        try:
            result["data"] = resp.json()
        except (json.JSONDecodeError, ValueError):
            result["data"] = {"raw": resp.text}

        return result


def _format_api_error(text: str) -> str:
    try:
        data = json.loads(text)
        return _extract_error_message(data) or text
    except (json.JSONDecodeError, TypeError):
        return text


def _extract_error_message(data) -> str:
    if not isinstance(data, dict):
        return str(data)
    if "erros" in data and isinstance(data["erros"], list):
        parts = [f"Código {e.get('codigo', '?')}: {e.get('mensagem', '')}" for e in data["erros"]]
        return " | ".join(parts)
    if "erro" in data and isinstance(data["erro"], dict):
        e = data["erro"]
        return f"Código {e.get('codigo', '?')}: {e.get('mensagem', '')}"
    if "sucesso" in data and isinstance(data["sucesso"], dict):
        s = data["sucesso"]
        return f"Código {s.get('codigo', '?')}: {s.get('mensagem', '')}"
    if "message" in data:
        return data["message"]
    return ""


# ---------------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(title="NeoConsig - Consulta de Margem")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "resultado": None,
        "erro": None,
        "convenios": CONVENIOS,
        "form": {"cpf": "", "matricula": "", "codBanco": "0958", "codConvenio": "8", "token": "", "senha": ""},
    })


@app.post("/consultar", response_class=HTMLResponse)
async def consultar(
    request: Request,
    cpf: str = Form(...),
    matricula: str = Form(...),
    codBanco: str = Form("958"),
    codConvenio: str = Form("8"),
    token: str = Form(""),
    senha: str = Form(""),
):
    cpf_limpo = re.sub(r"\D", "", cpf)

    form_data = {
        "cpf": cpf,
        "matricula": matricula,
        "codBanco": codBanco,
        "codConvenio": codConvenio,
        "token": token,
        "senha": senha,
    }

    try:
        result = await consultar_margem(cpf_limpo, matricula, codBanco, codConvenio, token, senha)
    except httpx.HTTPStatusError as exc:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "resultado": None,
            "convenios": CONVENIOS,
            "erro": f"Erro HTTP {exc.response.status_code} na autenticação: {_format_api_error(exc.response.text)}",
            "form": form_data,
        })
    except httpx.RequestError as exc:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "resultado": None,
            "convenios": CONVENIOS,
            "erro": f"Erro de conexão: {exc}",
            "form": form_data,
        })

    status = result["status_code"]
    data = result["data"]

    if status == 200 and "dadosConsulta" in data:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "resultado": data,
            "convenios": CONVENIOS,
            "erro": None,
            "form": form_data,
        })

    msg = _extract_error_message(data)
    if not msg:
        msg = str(data)

    url_info = f"URL: {result.get('url_usada', '?')}\n\n"
    detail = url_info + (json.dumps(data, ensure_ascii=False, indent=2) if isinstance(data, dict) else str(data))

    return templates.TemplateResponse("index.html", {
        "request": request,
        "resultado": None,
        "convenios": CONVENIOS,
        "erro": f"HTTP {status} — {msg}",
        "erro_detalhe": detail,
        "form": form_data,
    })


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
