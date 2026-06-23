# NeoConsig — Consulta de Margem Consignável

Aplicação web para consulta de margem consignável via API NeoConsig (Cred BR).

## Pré-requisito

- Python 3.10+ instalado na máquina
- A máquina deve sair com o IP **liberado na NeoConsig** (ex: 189.22.231.82)

## Instalação e execução (2 comandos)

```bash
pip install -r requirements.txt
python main.py
```

Acesse **http://localhost:8000** no navegador.

Para disponibilizar na rede local da empresa:

```bash
python main.py
```

Outros computadores na mesma rede acessam pelo IP da máquina:
**http://IP-DA-MAQUINA:8000**  (ex: http://192.168.1.100:8000)

## Deploy com Docker (opcional)

```bash
docker build -t neoconsig .
docker run -d -p 8000:8000 --name neoconsig neoconsig
```

## Variáveis de ambiente (opcional)

As credenciais já estão configuradas. Para sobrescrever:

| Variável | Padrão |
|---|---|
| `NEOCONSIG_BASE_URL` | https://wsst.neoconsig.com.br |
| `NEOCONSIG_CLIENT_ID` | 81 |
| `NEOCONSIG_CLIENT_SECRET` | (configurado) |
| `PORT` | 8000 |

## Estrutura

```
NeoConsig/
├── main.py              # Aplicação FastAPI
├── templates/
│   └── index.html       # Interface web
├── Dockerfile           # Deploy via container
├── Procfile             # Deploy em PaaS (Railway/Render)
├── requirements.txt     # Dependências Python
└── consultas.log        # Log gerado automaticamente
```

## Logs

Todas as operações são registradas em `consultas.log`. Credenciais sensíveis são automaticamente ocultadas nos logs.
