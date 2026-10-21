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
docker compose -f docker-compose.prod.yml up -d --build --wait

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
docker compose -f docker-compose.prod.yml up -d --build --wait
```

`--wait` só retorna quando o `api` estiver **`healthy`**. Use sempre: o boot é
sequencial (`alembic upgrade head` → `app.db_indexes` → `app.seed` → `uvicorn`) e
leva **~60–90 s** sem ninguém escutando na 8000. Nessa janela o Caddy responde
**502** em tudo — o que o browser reporta como erro de CORS, porque o preflight
`OPTIONS` não volta com os cabeçalhos. Não é bug: se você clicar em "Entrar"
durante o boot, vai parecer que a API caiu.

Se o comando parecer travado, o `api` é que não ficou saudável — abra outro
terminal e veja `logs api`. `Ctrl+C` é seguro: o `-d` já subiu tudo em segundo
plano. Sem o `--wait`, confirme antes de usar o site:

```bash
docker compose -f docker-compose.prod.yml ps
# intelliinpi_api ... Up (healthy)
```

O comando do container roda, antes de iniciar o servidor, as migrations, a
reconciliação dos índices de busca e o seed
(`alembic upgrade head && python -m app.db_indexes && python -m app.seed && uvicorn ...`).

Acompanhe e valide:

```bash
docker compose -f docker-compose.prod.yml logs -f api

# de dentro da VM
curl -s http://127.0.0.1:8000/api/health
# → {"status":"ok","service":"intelliinpi","version":"1.0.0"}
```

Se o health check falhar, quase sempre é o `DATABASE_URL` (host, senha sem
percent-encoding) ou `ENVIRONMENT=production` com segredos fracos.

---

## 5.1 Índices de busca — automáticos em todo deploy

As tabelas do INPI (`marcas` com ~6,6 milhões de linhas, `patentes` e as tabelas
de relacionamento) são carregadas em massa pelo pipeline de ingestão, **fora do
Alembic**. Sem os índices de busca, cada consulta virava um `Seq Scan` da tabela
inteira: uma busca exata por nome levava **~76 s**; com índice, ~1 ms.

O passo `python -m app.db_indexes` (`backend/app/db_indexes.py`) fecha esse
buraco: ele carrega o manifesto dos índices que devem existir e, **a cada
deploy**, cria apenas o que estiver faltando. Um banco recriado, um restore ou
um índice apagado à mão voltam ao normal no próximo deploy, sem intervenção.

Além dos índices de busca, o mesmo passo garante os **índices únicos** de que o
código da ingestão depende para `INSERT ... ON CONFLICT` (`inpi_dataset.name`,
`inpi_import_checkpoint(dataset_id, target_table)`, `inpi_rpi.number`,
`marcas_logos.codigo_interno`, `marcas_peticoes(codigo_interno, protocolo)`,
`marcas_pepi_sync.codigo_interno`). Um banco cujo schema divergiu do Alembic
(dump/restore antigo) quebrava na primeira gravação do worker com
`InvalidColumnReference: there is no unique or exclusion constraint matching the
ON CONFLICT specification` — foi o que aconteceu em produção com `inpi_rpi`.
Agora ele se conserta sozinho no deploy.

Propriedades (e por que é seguro deixar isso no caminho de subida):

- **idempotente** — quando já está tudo no lugar leva ~1 s (só consulta o catálogo);
- **comparação por definição** — um índice equivalente com nome herdado não gera
  duplicata; um índice com o nome esperado mas definição diferente é apenas
  *reportado* como conflito (ele nunca apaga nem substitui nada);
- **um índice que falha não derruba o deploy** — a API sobe de qualquer forma e
  o erro aparece no log (o índice é retomado no próximo deploy);
- **uma execução por vez** — *advisory lock* do PostgreSQL (evita dois containers
  reconciliando em paralelo, causa dos erros `duplicate key ... "pg_class_relname_nsp_index"`);
- **`lock_timeout` curto** — se o índice não conseguir o lock, ele é adiado em vez
  de segurar a subida da API.

O log do deploy mostra exatamente o que aconteceu:

```bash
docker compose -f docker-compose.prod.yml logs api | grep db_indexes
# "reconciliando índices (186 no manifesto, 6 índices únicos exigidos, timeout por índice: sem limite)"
# "índice criado em 42.7s"  {"index": "ix_marcas_data_vigencia", "table": "marcas"}
# "índice único criado (faltava no banco)"  {"index": "uq_inpi_rpi_number", "table": "inpi_rpi"}
# "reconciliação de índices concluída em 43.1s: 2 criado(s), 188 já existia(m), 0 conflito(s), 0 tabela(s) ausente(s), 0 erro(s)"
```

### Rodar/inspecionar à mão

```bash
cd /opt/intelliinpi

# o que falta (não altera nada)
docker compose -f docker-compose.prod.yml run --rm --no-deps api python -m app.db_indexes --dry-run

# reconciliar agora, acompanhando o log
docker compose -f docker-compose.prod.yml run --rm --no-deps api python -m app.db_indexes

# DDL equivalente, para rodar direto no psql (banco que o app não alcança)
docker compose -f docker-compose.prod.yml run --rm --no-deps api python -m app.db_indexes --emit-sql > /tmp/indices.sql
```

### Primeira carga de dados (importante)

Os índices são o que torna a **leitura** rápida, mas custam tempo de **escrita**.
Depois de uma carga em massa nova, deixe o índice ser (re)criado antes de medir
qualquer coisa — senão o `ANALYZE` não enxerga estatística nova e o planner
continua preferindo `Seq Scan`:

```bash
docker compose -f docker-compose.prod.yml run --rm --no-deps api python -m app.db_indexes
```

Se rodar num banco já cheio e o índice pesado (GIN trigram, que serve o filtro
"Contém") demorar mais que o normal, o deploy não trava: defina
`INDEX_BUILD_TIMEOUT_SECONDS` no `.env` (ver `backend/.env.prod.example`) e
construa o índice fora do horário do deploy com `--timeout 0`.

### Validar que o planner está usando os índices

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT id FROM marcas WHERE public.fold(elemento_nominativo) = public.fold('Magu');
-- Index Scan using ix_marcas_elemento_nominativo_fold (esperado ~1 ms)

EXPLAIN (ANALYZE, BUFFERS)
SELECT id FROM marcas WHERE elemento_nominativo ILIKE '%magu%';
-- Bitmap Index Scan on ix_marcas_elemento_nominativo_trgm (esperado < 1 s)
```

Os índices das tabelas de **aplicativo** (RBAC, NIT, CRM...) continuam sendo
criados pelo Alembic (`alembic upgrade head`); o manifesto inclui esses nomes
apenas como rede de segurança.

---

## 5.2 Worker de petições (pePI) — container próprio

As **petições** de um processo de marca (documentos GRU: protocolo, data,
serviço, cliente, delivery) **não** existem nos CSVs de dados abertos: só na
aplicação de consulta pePI (`busca.inpi.gov.br`), atrás de uma sessão anônima —
exatamente como os logotipos (`ingestion.logos`).

O worker `ingestion.peticoes` faz o login anônimo, lê a página de detalhe de cada
marca (`MarcasServletController?Action=detail&CodPedido=<codigo_interno>`),
extrai as petições e grava em `marcas_peticoes`, registrando o progresso em
`marcas_pepi_sync`. Ele roda em **container próprio** (serviço `peticoes` do
`docker-compose.prod.yml`, mesmo `.env` e mesmo PostgreSQL do host) para não
competir com a API.

### Como ele roda

Sobe junto com a stack e fica em loop:

```bash
cd /opt/intelliinpi
docker compose -f docker-compose.prod.yml up -d --build --wait  # api + peticoes + rpi
docker compose -f docker-compose.prod.yml logs -f peticoes
```

Cada ciclo drena a fila `PENDING` (marcas que alguém abriu na tela — o endpoint
de detalhe as enfileira), busca um lote de `Mista`/`Figurativa` e dorme 5 min. O
status terminal em `marcas_pepi_sync` garante o **resume**: cada marca é buscada
uma vez só, mesmo reiniciando o worker.

- **Pausar sem derrubar a stack:** `docker compose -f docker-compose.prod.yml stop peticoes`
- **Volume/ritmo:** flags do `command` ou os envs `INPI_PEPI_CONCURRENCY` /
  `INPI_PEPI_DELAY` (ver `backend/.env.prod.example`).
- **Atualizar periodicamente:** acrescente `--dias 30` ao comando para
  re-sincronizar o que já foi baixado (novas petições GRU surgem com o tempo).

### Rodar à mão (um processo específico)

```bash
cd /opt/intelliinpi

# diagnóstico de rede (DNS/TCP/TLS/HTTP), sem tocar no banco
docker compose -f docker-compose.prod.yml run --rm --no-deps peticoes \
  python -m ingestion.peticoes --diagnostico

# um código específico
docker compose -f docker-compose.prod.yml run --rm --no-deps peticoes \
  python -m ingestion.peticoes --codigos 4482935 --limite 1

# inspecionar a fila/estado (o Postgres roda nativo na VM, no container inpi-postgres)
docker exec inpi-postgres psql -U postgres -d intelliinpi_app \
  -c "SELECT status, count(*) FROM marcas_pepi_sync GROUP BY status;"
```

> **Fonte instável.** O `busca.inpi.gov.br` é um servlet legado com TLS frágil (o
> mesmo preflight que protege os logotipos vale aqui). Se o host cair no meio de
> um lote, o ciclo termina e recomeça: nada é perdido, o que faltou fica
> `PENDING`/`ERROR` e é retomado depois.

> **Logotipos são outro worker.** O serviço `peticoes` **não** baixa imagens —
> isso continua em `ingestion.logos` (a imagem aparece na tela via
> `marcas_logos`). Para rodá-lo no container de ingestão (monta o mesmo volume
> `api_data` da API — ver §5.2.1):
>
> ```bash
> docker compose -f docker-compose.prod.yml run --rm --no-deps peticoes \
>   python -m ingestion.logos --apresentacao Mista --apresentacao Figurativa
> ```

### 5.2.1 Logotipos — a **imagem** tem de estar no servidor, não só a linha no banco

`marcas_logos` guarda o *metadado* e a coluna `arquivo` aponta para o JPEG em
`data/raw/marcas/logos/<2 primeiros dígitos>/<codigo>.jpg` (mesmo volume
`api_data`). **Restaurar só o dump do banco não traz as imagens**: a linha fica
`status = OK` mas o arquivo não existe no host e a tela cai no placeholder.

`tem_logo` (na busca e no detalhe) reflete o **arquivo em disco**, não o status da
linha — então, quando a imagem não veio junto no restore, a API já responde
`tem_logo: false` em vez de mandar a UI pedir uma imagem que daria 404.

- **`GET /api/marcas/{codigo}`** devolve o logotipo **embutido** no campo `logo`
  como data URI (`data:image/jpeg;base64,...`), até 512 KB — a tela de detalhe
  não faz uma segunda requisição. `logo: null` quando não há imagem em disco.
- **`GET /api/marcas/{codigo}/logo`** continua existindo para as **listas**
  (monitoramento, resultados), onde embutir dezenas de imagens no JSON seria
  desperdício; faz streaming do arquivo (cacheável pelo navegador).

Conferir se as imagens chegaram na VM:

```bash
docker compose -f docker-compose.prod.yml exec api sh -c \
  'ls -l /app/data/raw/marcas/logos/44/ | head'
```

Há três formas de **popular** as imagens (a primeira não depende de transferir
nada):

**1. Busca sob demanda (recomendada para uma VM nova).** Ligue
`LOGO_FETCH_ENABLED=true` no `backend/.env` da VM — e **baixe o timeout**, que
por padrão é 120 s e bloquearia a requisição do detalhe:

```
LOGO_FETCH_ENABLED=true
LOGO_HTTP_TIMEOUT_SECONDS=15
LOGO_HTTP_RETRIES=1
```

```bash
docker compose -f docker-compose.prod.yml up -d api
```

A partir daí, abrir o detalhe de uma marca **Mista/Figurativa** faz a API buscar
a imagem no pePI, gravar em `api_data` + `marcas_logos` e devolvê-la já embutida
em `logo`. Nominativa é ignorada (não carrega imagem), e uma vez gravada não há
mais acesso à rede. Ao terminar de povoar, volte para `false` — assim nenhuma
leitura fica esperando o INPI.

> É uma escrita em `GET` (o desenho original já previa a flag). Com a flag
> **desligada** (padrão) a API é DB-only e nunca toca o pePI.

**2. Worker offline**, pelo container de ingestão (monta o mesmo volume
`api_data` da API):

```bash
docker compose -f docker-compose.prod.yml run --rm --no-deps peticoes \
  python -m ingestion.logos --diagnostico        # o pePI está no ar?

docker compose -f docker-compose.prod.yml run --rm --no-deps peticoes \
  python -m ingestion.logos --apresentacao Mista --limite 500
```

Se o preflight falhar (INPI fora do ar) **nada** é gravado; `--force` pula a
checagem. `logo_codes` ordena por `codigo_interno`, então `--limite` é
determinístico e o progresso é retomável entre rodadas.

**3. Copiar os arquivos** já baixados em outro ambiente (restore) — o banco
precisa das linhas em `marcas_logos` **e** os JPEGs dentro de `api_data`:

```bash
docker cp /tmp/logos/. intelliinpi_api:/app/data/raw/marcas/logos/
```

Caminhos gravados com `\` continuam válidos graças à normalização.

> **Barra invertida do Windows.** O worker rodado no Windows gravava
> `raw\marcas\logos\44\4482935.jpg`. No Linux esse valor é *um único* nome de
> arquivo, então a leitura já normaliza `\` → `/` (e ainda tenta o caminho
> canônico `logos/<2 dígitos>/<arquivo>`). Downloads novos são gravados em
> formato POSIX, portável entre Windows e Linux.

## 5.3 Worker da RPI — atualização **semanal** de marcas e patentes

A **RPI** (Revista da Propriedade Industrial) é publicada toda **terça-feira** e
traz, por seção, os *despachos* daquela semana (exigências, oposições,
deferimento, indeferimento, concessão, arquivamento, ...). Os CSVs de dados
abertos são *snapshots*: reprocessá-los toda semana custaria ~11 GB de download e
a recarga total das tabelas (inviável com o disco atual). Por isso o worker
`ingestion.rpi` faz só o **delta semanal**, direto na fonte oficial das revistas.

Ele roda em **container próprio** (serviço `rpi` do `docker-compose.prod.yml`,
mesmo `.env`, mesmo PostgreSQL do host e o mesmo volume `api_data` da API).

### O que ele faz (por seção)

Seções suportadas: `marcas` (XML), `patentes` (TXT INID), `desenho_industrial`
(XML) e `software` (XML). Aceita os aliases `di`, `desenhos`,
`programa_computador` e `pc` no `--secao`.

1. **descobre** as edições recentes via JSON —
   `GET {base}/rpi/busca/data?revista.tipoRevista.id=<id>` (marcas = 5,
   patentes = 6, desenhos = 3, programas = 7);
2. **baixa** o ZIP de texto — `GET {base}/txt/<nomeArquivoEscritorio>` — e o
   guarda em `data/raw/rpi` (resume/auditoria; `raw_path`/`sha256` vão para
   `inpi_rpi`). Marcas/Patentes trazem o nome do arquivo no JSON; Desenhos e
   Programas não, então o worker deriva `DI<numero>.zip`/`PC<numero>.zip` e
   valida a assinatura ZIP antes de parsear (o portal responde 200 com HTML de
   erro quando o arquivo não existe);
3. **parseia** o conteúdo: XML para **Marcas** e **Desenhos Industriais**, TXT
   INID para **Patentes** e XML para **Programas de Computador**;
4. **casa** o número do processo com o `codigo_interno` que já temos
   (`marcas` por `numero_inpi`; `patentes`/`desenhos`/`softwares` pelo conjunto
   de dígitos, removendo o dígito verificador que só a RPI publica). Processo
   que ainda não está no banco é **ignorado** — ele entra pelo dump de dados
   abertos;
5. **grava** os despachos novos em `marcas_despachos`/`patentes_despachos`/
   `desenhos_despachos`/`softwares_despachos`, atualiza os dados bibliográficos
   de DI/software (titulares, autores, procuradores, classificação Locarno,
   prioridades, vínculos, linguagens, campos de aplicação) e registra o estado
   da edição em `inpi_rpi`
   (`metadata.sections.<secao> = {status, processos, casados, despachos, ...}`).

> **Escopo.** Para Marcas/Patentes o worker só **acrescenta** o histórico de
> publicações (despachos). Para Desenhos/Programas ele também atualiza a
> situação e os campos bibliográficos, porque essas seções publicam os dados
> completos do processo no XML. Campos já preenchidos pelo dump nunca são
> apagados (`COALESCE`); a situação termina no despacho mais recente processado,
> por isso o backfill roda em ordem crescente.

### Imagens/logotipos de Marcas e figuras de Desenhos

Depois de gravar os despachos, o worker baixa as imagens referenciadas no XML em
paralelo (`httpx` + `asyncio`, concorrência limitada e retry/backoff):

- **Marcas**: busca pública → acervo `/rpi/images/<edição>` → fallback histórico.
  Metadado em `marcas_rpi_imagens`, espelhado em `marcas_logos`.
- **Desenhos**: usa o acervo público de DI e o fallback `/rpi/images/<edição>`.
  Metadado em `desenhos_rpi_figuras`, espelhado em `desenhos_figuras`. O XML de
  DI nem sempre traz o nome da imagem; a referência é derivada do número do
  processo.
- **Programas de Computador** não têm imagens — só metadados bibliográficos.

Os bytes são validados por *magic number* (JPEG/PNG/WebP); HTML, GIF de
placeholder e respostas corrompidas são rejeitados. `OK`/`SEM_IMAGEM` são
terminais e `ERROR` volta na próxima rodada, então o processo é retomável.

### Como ele roda

Sobe junto com a stack e fica em loop (um ciclo a cada 6 h):

```bash
cd /opt/intelliinpi
docker compose -f docker-compose.prod.yml up -d --build --wait  # api + peticoes + rpi
docker compose -f docker-compose.prod.yml logs -f rpi
```

- **Pausar sem derrubar a stack:** `docker compose -f docker-compose.prod.yml stop rpi`
- **Fonte alternativa:** env `INPI_RPI_BASE_URL` (padrão `https://revistas.inpi.gov.br`).
- **Portal em manutenção:** o INPI derruba o `revistas.inpi.gov.br` por completo de
  vez em quando e **todo** caminho dele responde `503` (não é a VM, não é IP
  bloqueado — confira de outra rede se duvidar). O worker registra
  `Portal das Revistas inacessível (HTTP 503). Nada a fazer agora.` e segue
  vivo: nada é gravado, nada quebra, e o ciclo seguinte (6 h) tenta de novo.
  Zero intervenção necessária; quando o portal volta, o worker pega sozinho.

### Idempotência e resume

Duas camadas, então pode rodar quantas vezes quiser que nada duplica:

- a edição já marcada como `PROCESSED` em `inpi_rpi` é **pulada** (nada é
  baixado de novo);
- o `INSERT` usa anti-join por `(codigo_interno, numero_rpi, codigo_despacho,
  complemento_despacho)` — um despacho que o CSV aberto já trouxe não é
  reproduzido.

O ZIP é salvo em `data/raw/rpi`; se o download cair no meio, o `.part` não é
promovido e o próximo ciclo tenta de novo.

### Migration / tabelas novas (Desenhos e Programas)

O deploy da API roda `alembic upgrade head` antes do `uvicorn`: a revisão
`b7c9d1e2f3a4` cria `desenhos_rpi_figuras` (procedência das figuras de DI) e a
`f1a2b3c4d5e7` cria as tabelas base de Desenhos/Programas. Nada manual é
necessário no caminho normal.

Se o banco foi montado à mão com `database/06_desenhos_softwares.sql` (fora do
Alembic), aplique o DDL idempotente e marque a revisão para o `upgrade head` não
tentar recriar as tabelas:

```bash
cd /opt/intelliinpi

# DDL manual (idempotente) — cria também `desenhos_rpi_figuras`
docker exec -i inpi-postgres psql -U postgres -d intelliinpi_app \
  -f - < database/06_desenhos_softwares.sql

# marca a cabeça atual do Alembic
docker compose -f docker-compose.prod.yml run --rm --no-deps api \
  alembic stamp b7c9d1e2f3a4
```

Conferir as tabelas e a cabeça das migrations:

```bash
docker exec inpi-postgres psql -U postgres -d intelliinpi_app \
  -c "\dt desenhos_rpi_figuras" -c "\dt softwares"
docker compose -f docker-compose.prod.yml run --rm --no-deps api \
  alembic current
```

### Rodar à mão / inspecionar

```bash
cd /opt/intelliinpi

# conectividade com o portal das Revistas (sem tocar no banco)
docker compose -f docker-compose.prod.yml run --rm --no-deps rpi \
  python -m ingestion.rpi --diagnostico

# backfill das 4 últimas edições das quatro seções
docker compose -f docker-compose.prod.yml run --rm --no-deps rpi \
  python -m ingestion.rpi --secao marcas --secao patentes \
  --secao desenho_industrial --secao software --ultimas 4

# uma seção só / reprocessar
docker compose -f docker-compose.prod.yml run --rm --no-deps rpi \
  python -m ingestion.rpi --secao marcas --force

# backfill de um intervalo de edições (inclusivo, ordem crescente) — desenhos
docker compose -f docker-compose.prod.yml run --rm --no-deps rpi \
  python -m ingestion.rpi --secao desenho_industrial \
  --rpi-inicio 2500 --rpi-fim 2911

# só os metadados, sem baixar imagens de marcas/desenhos
docker compose -f docker-compose.prod.yml run --rm --no-deps rpi \
  python -m ingestion.rpi --secao desenho_industrial --sem-imagens

# retomar imagens pendentes/falhas de Desenhos (ou de Marcas)
docker compose -f docker-compose.prod.yml run --rm --no-deps rpi \
  python -m ingestion.rpi_images --secao desenho_industrial --pendentes --limite 500

# o que já foi processado (o Postgres roda nativo na VM, no container inpi-postgres)
docker exec inpi-postgres psql -U postgres -d intelliinpi_app \
  -c "SELECT number, status, metadata->'sections' FROM inpi_rpi ORDER BY number DESC LIMIT 5;"

# quanto entrou de cada seção
docker exec inpi-postgres psql -U postgres -d intelliinpi_app \
  -c "SELECT numero_rpi, count(*) FROM marcas_despachos GROUP BY 1 ORDER BY 1 DESC LIMIT 5;"
docker exec inpi-postgres psql -U postgres -d intelliinpi_app \
  -c "SELECT numero_rpi, count(*) FROM desenhos_despachos GROUP BY 1 ORDER BY 1 DESC LIMIT 5;"
docker exec inpi-postgres psql -U postgres -d intelliinpi_app \
  -c "SELECT numero_rpi, count(*) FROM softwares_despachos GROUP BY 1 ORDER BY 1 DESC LIMIT 5;"
```

> **Fonte instável.** O `revistas.inpi.gov.br` entra em manutenção de tempos em
> tempos (responde **503** com uma página de manutenção). O worker pré-checa a
> conectividade e, se o portal estiver fora, sai limpo sem marcar nada como
> `SEM_DADOS` — o próximo ciclo (6 h depois) tenta de novo. O mesmo vale para uma
> falha no meio do processamento: a edição fica `FAILED` em `inpi_rpi` e é
> retomada no ciclo seguinte (idempotente).


