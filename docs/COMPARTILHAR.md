# Compartilhar o dashboard com outras pessoas

Existem **duas formas** de liberar acesso. Escolha conforme a necessidade:

| Opção | Quem acessa | Melhor para |
|-------|-------------|-------------|
| **A — Rede local** | Mesma Wi-Fi / VPN da empresa | Time no escritório, teste rápido |
| **B — Streamlit Cloud** | Qualquer lugar, via link na internet | Supervisores, outras unidades, home office |

---

## Opção A — Rede local (5 minutos)

No **seu PC** (onde já roda o painel):

```powershell
cd C:\Users\usuario\Projects\cobranca-producao
powershell -ExecutionPolicy Bypass -File .\scripts\compartilhar_rede_local.ps1
```

O script mostra um endereço como `http://192.168.x.x:8501`. **Outras pessoas na mesma rede** abrem esse link no navegador.

**Importante:**
- Seu PC precisa ficar ligado com o script rodando
- Rode `python run.py` quando exportar CSV novo (como já faz hoje)
- Se não abrir em outro PC, libere a porta **8501** no Firewall do Windows

### Liberar firewall (se necessário)

PowerShell **como administrador**:

```powershell
New-NetFirewallRule -DisplayName "Streamlit Cobranca 8501" -Direction Inbound -LocalPort 8501 -Protocol TCP -Action Allow
```

---

## Opção B — Link na internet (Streamlit Cloud)

Fluxo resumido:

1. **Seu PC** continua atualizando os dados (`python run.py`)
2. O snapshot vai para o **Google Drive**
3. O **Streamlit Cloud** só **lê** e exibe (visualização — sem CSV, sem token 3C Plus na nuvem)

### Passo 1 — Pasta no Google Drive

1. No Google Drive, crie uma pasta (ex.: `Cobranca Snapshot`)
2. **Compartilhe** com o e-mail da conta de serviço como **Editor**  
   (o mesmo de `credentials/service_account.json`, ex.: `cobranca-automacao@....iam.gserviceaccount.com`)
3. Copie o **ID da pasta** da URL:  
   `https://drive.google.com/drive/folders/ESTE_ID_AQUI`

### Passo 2 — Configurar o `.env` no seu PC

Adicione no `.env`:

```
GOOGLE_DRIVE_SNAPSHOT_FOLDER_ID=ESTE_ID_AQUI
DASHBOARD_MODE=local
```

Teste:

```powershell
python run.py
```

Deve aparecer: `Snapshot na nuvem (Drive): ...`

Na pasta do Drive, confira o arquivo `cobranca-latest.json`.

### Passo 3 — Subir o código no GitHub

1. Crie um repositório no GitHub (pode ser **privado**)
2. No projeto:

```powershell
cd C:\Users\usuario\Projects\cobranca-producao
git init
git add .
git commit -m "Dashboard cobrança"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/cobranca-producao.git
git push -u origin main
```

**Nunca** commite `.env`, `credentials/` nem `data/latest.json` (já estão no `.gitignore`).

### Passo 4 — Publicar no Streamlit Cloud

1. Acesse [share.streamlit.io](https://share.streamlit.io) e entre com GitHub
2. **New app** → selecione o repositório
3. **Main file path:** `dashboard/app.py`
4. **Advanced settings → Secrets** — cole (ajuste os valores):

```toml
DASHBOARD_MODE = "cloud"

GOOGLE_SERVICE_ACCOUNT_JSON = '''
{
  "type": "service_account",
  "project_id": "seu-projeto",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n",
  "client_email": "cobranca-automacao@....iam.gserviceaccount.com",
  "client_id": "...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "...",
  "universe_domain": "googleapis.com"
}
'''

GOOGLE_DRIVE_SNAPSHOT_FOLDER_ID = "id_da_pasta_no_drive"

# Opcional — exige senha antes de ver o painel
VIEWER_PASSWORD = "escolha-uma-senha"
```

5. Clique **Deploy**

Em alguns minutos você recebe um link como:

`https://cobranca-producao.streamlit.app`

Compartilhe só com quem deve ver. Com `VIEWER_PASSWORD`, quem abrir o link precisa da senha.

### Passo 5 — Manter atualizado

No **seu PC** (rotina atual):

1. Exportar CSV do 3C Plus
2. `python run.py` → atualiza planilha + Drive
3. Quem está no link remoto clica **Recarregar** (ou espera ~2 min de cache)

Pode manter o agendamento `scripts/agendar.ps1` — cada execução também envia o snapshot pro Drive.

---

## O que cada pessoa consegue fazer

| Ação | Rede local | Streamlit Cloud |
|------|------------|-----------------|
| Ver KPIs, gráficos, squads | Sim | Sim |
| Pesquisar na aba Detalhes | Sim | Sim |
| Botão Atualizar (buscar CSV/API) | Só no PC servidor | Não (só Recarregar do Drive) |
| Exportar CSV / rodar run.py | Só no PC servidor | Não |

Ou seja: **visualização** para todos; **atualização de dados** só no seu PC.

---

## Problemas comuns

**“Snapshot não encontrado” no link remoto**  
→ Rode `python run.py` no PC principal e confira `cobranca-latest.json` na pasta do Drive.

**Erro de permissão no Drive**  
→ A pasta precisa estar compartilhada com a conta de serviço como Editor.

**Link abre mas dados antigos**  
→ Clique **Recarregar** no painel ou rode `python run.py` de novo.

**Quero só a planilha, sem dashboard**  
→ A planilha espelho no Google Sheets já pode ser compartilhada como “Somente visualização” com o time.

---

## Resumo recomendado

- **Escritório / mesma rede:** Opção A  
- **Qualquer lugar / link fixo:** Opção B  
- **Ambos:** Opção B para o time + você continua rodando `run.py` no PC
