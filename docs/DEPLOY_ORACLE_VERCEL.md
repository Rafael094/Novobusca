# Deploy — API no Oracle Cloud Free + Frontend na Vercel

Arquitetura alvo:

```
┌──────────────────────────┐
│  VERCEL (grátis)         │
│  frontend/ (Next.js)     │
└───────────┬──────────────┘
            │ HTTPS + CORS
            ▼
┌──────────────────────────┐         ┌──────────────────────────┐
│  ORACLE CLOUD FREE VM    │         │  (mesma VM)              │
│  docker compose          │         │  PostgreSQL 15.x         │
│  api :8000 (Dockerfile)  │────────►│  intelliinpi_app :5432   │
└──────────────────────────┘         └──────────────────────────┘
```

**Por que a API não fica na Vercel.** O backend FastAPI é um processo de longa
duração: mantém um *connection pool* do PostgreSQL (`backend/app/db.py`), um
*rate limiter* em memória (`backend/app/rate_limit.py`) e grava documentos
enviados no disco (`backend/app/config.py` → `DOCUMENT_STORAGE_DIR`). Funções
serverless são efêmeras e têm disco somente-leitura, o que estouraria as
conexões do banco, desativaria o rate limit de login e quebraria o upload de
documentos do NIT. A Vercel hospeda apenas o **frontend Next.js**.

---

## 1. Pré-requisitos

- VM Oracle Cloud (Always Free) com Ubuntu, IP público (ex.: `152.67.45.106`).
- PostgreSQL rodando na VM com o banco `intelliinpi_app`.
- Portas liberadas na *Security List* da VCN: **22** (SSH), **80** e **443** (HTTP/HTTPS).
  A porta **8000 não precisa** ser exposta se você usar o proxy reverso do passo 6.
- Repositório já publicado no GitHub (`https://github.com/Rafael094/Novobusca.git`).

> A porta **5432 não precisa** ficar aberta para a internet: a API fala com o
> PostgreSQL pelo host local da VM. Se hoje ela está aberta, considere restringir
> ao IP da VM nas Security Lists.

---

## 2. Preparar a VM

Conecte por SSH (**a chave privada fica na sua máquina**):

```bash
ssh ubuntu@152.67.45.106
```

Instale Docker + Compose e o utilitário do repositório:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git

# Docker Engine + compose plugin (script oficial)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
newgrp docker          # ou saia e entre novamente na sessão SSH

docker --version
docker compose version
```

Aumente o espaço de swap (a VM Always Free tem pouca RAM; o build do
`psycopg`/`argon2` agradece):

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h
```

---

## 3. Clonar o projeto

```bash
sudo mkdir -p /opt/intelliinpi
sudo chown -R "$USER":"$USER" /opt/intelliinpi
git clone https://github.com/Rafael094/Novobusca.git /opt/intelliinpi
cd /opt/intelliinpi
```

---

## 4. Criar o `.env` do backend **na VM** (nunca no repositório)

```bash
cd /opt/intelliinpi
cp backend/.env.prod.example backend/.env
chmod 600 backend/.env
nano backend/.env
```

Gere os dois segredos JWT (rode duas vezes, use um valor em cada variável):

```bash
openssl rand -base64 48
```

Confirme que `backend/.env` está protegido pelo git (deve imprimir `backend/.env`):

```bash
git check-ignore -v backend/.env
```

Preencha, no mínimo:

| Variável | Valor |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://postgres:<SENHA>@host.docker.internal:5432/intelliinpi_app` |
| `DEEPSEEK_API_KEY` | chave **rotacionada** da DeepSeek (ou vazio para desativar a IA) |

---

## 6. HTTPS e proxy reverso (Caddy)

A Vercel serve o frontend por **HTTPS**; o navegador bloqueia chamadas para uma
API em **HTTP** (*mixed content*). Publique a API por HTTPS também.

O caminho mais simples é apontar um subdomínio (ex.: `api.seudominio.com`) para
o IP da VM e usar o Caddy, que emite o certificado automaticamente:

```bash
sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt-get update && sudo apt-get install -y caddy
```

Edite `/etc/caddy/Caddyfile`:

```
api.seudominio.com {
    reverse_proxy 127.0.0.1:8000
}
```

```bash
sudo systemctl reload caddy
curl -s https://api.seudominio.com/api/health
```

Se **não** tiver domínio, uma alternativa grátis é o `nip.io`
(ex.: `152-67-45-106.nip.io`) — funciona, mas o certificado é menos confiável.

Depois de ter HTTPS, feche a porta 8000 no firewall (o tráfego passa só pelo Caddy):

```bash
sudo ufw allow 22,80,443/tcp
sudo ufw deny 8000/tcp
sudo ufw enable
```

---

## 7. Frontend na Vercel

1. **Add New → Project** → importe `Rafael094/Novobusca`.
2. **Root Directory:** `frontend` (o repositório tem `frontend/` e `backend/` na
   raiz; sem isso a Vercel não encontra o Next.js).
3. **Settings → Environment Variables** → uma única variável, aplicada a
   Production, Preview e Development:

   | Key | Value |
   |---|---|
   | `NEXT_PUBLIC_API_BASE_URL` | `https://api.seudominio.com` |

   > 🔒 Nunca use o prefixo `NEXT_PUBLIC_` para `DATABASE_URL` ou
   > `DEEPSEEK_API_KEY`: tudo com esse prefixo é embutido no JavaScript enviado
   > ao navegador. Esses valores pertencem apenas à API.

4. **Deploy**. Copie a URL gerada (ex.: `https://intelliinpi.vercel.app`).

> `NEXT_PUBLIC_*` é resolvido em *build time*: se a URL da API mudar, faça um
> **Redeploy**.

---

## 8. Fechar o ciclo (CORS)

Volte ao `.env` da VM e coloque a URL exata da Vercel em `CORS_ORIGINS` (sem
barra final), depois reinicie:

```bash
nano /opt/intelliinpi/backend/.env      # CORS_ORIGINS=https://intelliinpi.vercel.app
cd /opt/intelliinpi
docker compose -f docker-compose.prod.yml up -d
```

Teste o fluxo completo: abra o site na Vercel, faça login com
`MASTER_ADMIN_EMAIL` / `MASTER_ADMIN_PASSWORD` e verifique se as listagens
carregam (isso valida CORS + API + banco).

---

## 9. Operação

```bash
# status / logs
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f --tail=200 api

# atualizar o código
cd /opt/intelliinpi
git pull
docker compose -f docker-compose.prod.yml up -d --build

# parar / derrubar
docker compose -f docker-compose.prod.yml down            # mantém os volumes
docker compose -f docker-compose.prod.yml down -v         # APAGA os volumes
```

**Backup do banco** — ver `docs/RUNBOOK_BACKUP_RESTORE.md`.

**Uploads de documentos** ficam no volume `api_documents`; os datasets ingeridos,
em `api_data`. Ambos sobrevivem a `up --build` e `down` (mas não a `down -v`).

---

## 10. Segurança — checklist final

- [ ] Chave DeepSeek **rotacionada** (a antiga circulou em arquivos locais).
- [ ] `JWT_SECRET` e `JWT_REFRESH_SECRET` distintos e com ≥ 32 caracteres.
- [ ] `MASTER_ADMIN_PASSWORD` forte, diferente do valor de exemplo.
- [ ] `CORS_ORIGINS` lista **apenas** os domínios reais do frontend.
- [ ] Porta 5432 restrita (Security List da VCN + `ufw`), não exposta ao mundo.
- [ ] Apenas 22/80/443 abertas; 8000 bloqueada após o proxy reverso.
- [ ] `git status` limpo de segredos: `git grep -iE 'sk-[a-z0-9]{20,}'` não retorna nada.
- [ ] `backend/.env` na VM com permissão `600` e jamais commitado.

| `ENVIRONMENT` | `production` |
| `JWT_SECRET` | ≥ 32 caracteres |
| `JWT_REFRESH_SECRET` | ≥ 32 caracteres, **diferente** do anterior |
| `MASTER_ADMIN_EMAIL` | domínio real (TLD `.local` é recusado) |
| `MASTER_ADMIN_PASSWORD` | senha forte (diferente do valor de exemplo) |
| `CORS_ORIGINS` | `https://<seu-projeto>.vercel.app` |

> ⚠️ Com `ENVIRONMENT=production`, o backend **recusa iniciar** se os segredos
> JWT tiverem menos de 32 caracteres, se forem iguais entre si, ou se
> `MASTER_ADMIN_PASSWORD` ainda for o valor de exemplo
> (`backend/app/config.py` → `_reject_insecure_defaults`).

> A senha do banco na URL precisa de *percent-encoding*: `@` → `%40`, `:` → `%3A`,
> `/` → `%2F`.

---

## 5. Subir a API

```bash
cd /opt/intelliinpi
docker compose -f docker-compose.prod.yml up -d --build
```

O comando do container roda as migrations e o seed antes de iniciar o servidor
(`alembic upgrade head && python -m app.seed && uvicorn ...`).

Acompanhe e valide:

```bash
docker compose -f docker-compose.prod.yml logs -f api

# de dentro da VM
curl -s http://127.0.0.1:8000/api/health
# → {"status":"ok","service":"intelliinpi","version":"1.0.0"}
```

Se o health check falhar, quase sempre é o `DATABASE_URL` (host, senha sem
percent-encoding) ou `ENVIRONMENT=production` com segredos fracos.
