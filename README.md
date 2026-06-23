# NeoConsig — Consulta de Margem Consignável

Aplicação web local para consulta de margem consignável via API NeoConsig (ambiente de homologação).

## Instalação

```bash
pip install -r requirements.txt
```

## Execução

```bash
python main.py
```

Acesse **http://localhost:8000** no navegador.

## Estrutura

```
NeoConsig/
├── main.py              # Aplicação FastAPI (backend + rotas)
├── templates/
│   └── index.html       # Interface web (Jinja2)
├── requirements.txt     # Dependências Python
└── consultas.log        # Log gerado automaticamente
```

## Logs

Todas as operações são registradas em `consultas.log` com timestamp, parâmetros, headers e body de request/response. Credenciais sensíveis (`client_secret`, `access_token`) são automaticamente ocultadas.
