# Cobrança — Painel de Produção

Automação que consulta a API do **3C Plus** a cada 30 minutos e atualiza um **Google Sheets** com a produção do time.

**Regra de produção:** somente finalizações **"Acordo formalizado"**.

## Estrutura

```
cobranca-producao/
├── run.py                 # Executa a atualização
├── src/
│   ├── api_3cplus.py      # Busca ligações + agrega produção
│   └── sheets.py          # Grava no Google Sheets
├── credentials/           # JSON da conta de serviço Google (você cria)
├── .env                   # Token 3C Plus + ID da planilha (você cria)
└── scripts/
    └── agendar.ps1        # Agenda no Windows a cada 30 min
```

## Passo 1 — Configurar o .env

Copie o exemplo e preencha:

```powershell
cd C:\Users\usuario\Projects\cobranca-producao
copy .env.example .env
```

Edite `.env`:

```
THREECPLUS_API_TOKEN=seu_token_do_gestor
GOOGLE_SHEETS_ID=id_da_sua_planilha
GOOGLE_SERVICE_ACCOUNT_FILE=credentials/service_account.json
```

## Passo 2 — Google Sheets (conta de serviço)

1. Acesse [Google Cloud Console](https://console.cloud.google.com/)
2. Crie um projeto (ex.: `cobranca-producao`)
3. Ative a **Google Sheets API** e a **Google Drive API**
4. Crie uma **Conta de serviço** → baixe o JSON
5. Salve o arquivo em `credentials/service_account.json`
6. Crie uma planilha no Google Sheets
7. **Compartilhe** a planilha com o e-mail da conta de serviço (ex.: `...@....iam.gserviceaccount.com`) como **Editor**
8. Copie o ID da planilha da URL:
   `https://docs.google.com/spreadsheets/d/ESTE_ID_AQUI/edit`

## Passo 3 — Instalar dependências

```powershell
cd C:\Users\usuario\Projects\cobranca-producao
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Passo 4 — Testar manualmente

```powershell
python run.py
```

Se funcionar, a planilha terá duas abas:
- **Resumo** — total do time e ranking por agente
- **Detalhes** — cada acordo formalizado do dia

## Passo 5 — Agendar a cada 30 minutos

Execute como administrador:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\agendar.ps1
```

Isso cria a tarefa **CobrancaProducao30Min** no Agendador do Windows (08:00–20:00, seg–sex).

## Dashboard web (Streamlit)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\iniciar_dashboard.ps1
```

Abre em http://localhost:8501

### Compartilhar com outras pessoas

Veja o guia completo: **[docs/COMPARTILHAR.md](docs/COMPARTILHAR.md)**

- **Rede local** — `scripts/compartilhar_rede_local.ps1` (mesma Wi-Fi)
- **Link na internet** — Streamlit Cloud + snapshot no Google Drive

## Segurança

- **Nunca** commite `.env` nem `credentials/service_account.json`
- Como o token foi compartilhado no chat, peça para TI **gerar um token novo** no 3C Plus após a implantação

## O que falta validar

A API `GET /calls` pode usar nomes de parâmetro ligeiramente diferentes na sua conta. Se `run.py` falhar na busca, abra um chamado com o erro — ajustamos os parâmetros (`start_date` / `end_date`) conforme a resposta da API.
