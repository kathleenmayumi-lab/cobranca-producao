# Publicar no GitHub + Streamlit Cloud

Guia rápido para liberar o painel via link na internet.

---

## Parte 1 — GitHub (subir o código)

### 1.1 Criar repositório no GitHub

1. Acesse [github.com/new](https://github.com/new)
2. Nome sugerido: `cobranca-producao`
3. **Private** (recomendado — código fica fechado)
4. **Não** marque README, .gitignore nem license (já existem no projeto)
5. Clique **Create repository**

### 1.2 Enviar o projeto (no PowerShell)

```powershell
cd C:\Users\usuario\Projects\cobranca-producao
git init
git add .
git status
```

Confira que **não** aparecem: `.env`, `credentials/`, `data/`, `.venv`

```powershell
git commit -m "Dashboard cobrança — painel Streamlit"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/cobranca-producao.git
git push -u origin main
```

Substitua `SEU_USUARIO` pelo seu login GitHub. Na primeira vez pode pedir login do GitHub.

---

## Parte 2 — Streamlit Cloud (link público/privado)

### 2.1 Criar conta e conectar GitHub

1. Acesse [share.streamlit.io](https://share.streamlit.io)
2. Entre com **GitHub**
3. Autorize o Streamlit a ver seus repositórios

### 2.2 Criar o app

1. **Create app**
2. **Repository:** `SEU_USUARIO/cobranca-producao`
3. **Branch:** `main`
4. **Main file path:** `dashboard/app.py`
5. **App URL (optional):** ex. `cobranca-velotax` → link fica `https://cobranca-velotax.streamlit.app`

Clique **Advanced settings** antes de Deploy.

### 2.3 Secrets (obrigatório)

No campo **Secrets**, gere o conteúdo no seu PC:

```powershell
cd C:\Users\usuario\Projects\cobranca-producao
powershell -ExecutionPolicy Bypass -File .\scripts\gerar_secrets_streamlit.ps1
```

Isso cria `streamlit_secrets_paste.toml` e copia para a área de transferência.

1. Abra [share.streamlit.io](https://share.streamlit.io) → seu app → **Settings** → **Secrets**
2. Cole **todo** o conteúdo
3. **Save**

### 2.4 Deploy

Clique **Deploy** (ou **Reboot app** se já existir).

Em 1–3 minutos o link fica no ar, ex.:

`https://cobranca-velotax.streamlit.app`

---

## Parte 3 — Rotina do dia a dia

| Quem | O que faz |
|------|-----------|
| **Você (PC principal)** | Export CSV → `python run.py` |
| **Time (link Streamlit)** | Abre o link → **Recarregar** se quiser dados frescos |

O `run.py` atualiza a aba `_Snapshot` na planilha. O Streamlit Cloud **só lê** — não precisa de CSV nem token 3C Plus na nuvem.

---

## Parte 4 — Senha no link (opcional)

No Secrets, adicione:

```toml
VIEWER_PASSWORD = "sua-senha-aqui"
```

Quem abrir o link precisa digitar a senha antes de ver o painel.

---

## Problemas comuns

**App abre vazio**  
→ Rode `python run.py` no PC e confira se aparece `Snapshot remoto (planilha aba _Snapshot): ok`

**Erro de credenciais no Streamlit**  
→ Secrets mal colados; rode de novo `gerar_secrets_streamlit.ps1` e cole o arquivo inteiro

**Dados desatualizados**  
→ Clique **Recarregar** no painel (cache ~2 min)

**Não quero código no GitHub público**  
→ Use repositório **Private** — Streamlit Cloud acessa repos privados na conta conectada

---

## Checklist final

- [ ] GitHub: repo criado e código enviado
- [ ] Streamlit: app apontando para `dashboard/app.py`
- [ ] Secrets colados (modo `cloud` + planilha + JSON conta de serviço)
- [ ] `python run.py` rodou ao menos uma vez hoje
- [ ] Link testado no celular ou outro PC
