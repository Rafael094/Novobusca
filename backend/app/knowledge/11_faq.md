# Perguntas Frequentes (FAQ)

### Como faço login?
Acesse `/login`, informe e-mail e senha. Após entrar, o sistema carrega suas
permissões (`/api/auth/me`) e mostra apenas os blocos do menu permitidos.

### Onde vejo meus clientes?
Menu **CRM / Clientes → Clientes e empresas**, rota `/clientes`. A API é
`GET /api/clientes/customers`. O detalhe de um cliente fica em `/clientes/[id]`.

### Qual é o fluxo completo de registro no NIT?
1. **Comunicação** de invenção criada em `/nit/comunicacoes` (estado `PROPOSAL`).
2. **Triagem** (`NIT_WORKFLOW_TRIAGE`) → `TRIAGE`.
3. **Avaliação** — pareceres (`NIT_EVALUATION_CREATE`) → `EVALUATION`.
4. **Decisão** (`NIT_DECISION`) → `CLOSED` (aprovado) ou `REJECTED`.
5. Se aprovado, gera **ativo de PI** (`/nit/ativos`), que pode virar **oferta**
   (catálogo), **negociação**, **contrato** e **royalty**.

### Como insiro documentos?
Pela tela de detalhe da comunicação: `/nit/comunicacoes/[id]` → painel
**Documentos** (escolha o nível de sigilo e o arquivo; o envio é automático).
A tela `/nit/documentos` serve apenas para listar/baixar. Via API:
`POST /api/nit/documents` (multipart) com `file` e `disclosure_id` ou `asset_id`.

### Como pesquiso marcas?
Menu **INPI → Marcas** (`/marcas`). Filtre por nome, classe NICE, situação e
titular. A API é `GET /api/marcas/search`.

### Como pesquiso patentes?
Menu **INPI → Patentes** (`/patentes`). API: `GET /api/patentes/search`.

### Como funciona a análise de IA de marca?
A tela `/analises` envia os dados para `POST /api/analises`, que busca marcas
similares na base local e pede uma avaliação de risco ao modelo (DeepSeek). O laudo
traz risco geral, score, conflitos e recomendações.

### Por que recebi "503 — IA não configurada"?
O recurso de IA exige a chave `DEEPSEEK_API_KEY` no servidor. Sem ela, o sistema
**não inventa** resultado: retorna 503 com mensagem clara. Informe a um
administrador para configurar a chave.

### Onde ficam os comitês e as decisões?
**NIT → Comitês** (`/nit/comites`). Os pareceres exigem `NIT_EVALUATION_CREATE` e a
decisão exige `NIT_DECISION`.

### Onde publico uma tecnologia para transferência?
**NIT → Catálogo de Tecnologias** (`/nit/catalogo`), como **oferta**. Depois,
**Negociações** e **Contratos**.

### Onde vejo contratos e royalties?
**NIT → Contratos** (`/nit/contratos`). Obrigações geram **alertas de vencimento**;
os **royalties** aparecem no resumo de royalties.

### Onde vejo os indicadores e o FORMICT?
**NIT → Indicadores & FORMICT** (`/nit/indicadores`). API: `GET /api/nit/indicators`.

### Como administro usuários e permissões?
Menu do usuário (canto superior direito) → **Administração → Usuários**
(`/admin/usuarios`), atribuindo papéis. Tenants e módulos em `/admin/tenants` e
`/admin/modulos`.

### Quem pode enviar documentos do NIT?
Papéis com `NIT_DOCUMENT_UPLOAD`: **SUPER_ADMIN, TENANT_ADMIN, NIT_RESEARCHER,
NIT_ANALYST, NIT_MANAGER, NIT_TT_OPERATOR**. A leitura exige `NIT_DOCUMENT_VIEW` e
respeita o sigilo/ACL do documento.

### Como o sistema isola dados entre instituições?
O tenant é derivado do usuário autenticado e nunca do pedido. Registros de outro
tenant são bloqueados (403). Apenas o **Master Admin** tem alcance cross-tenant.

### Como uso este assistente?
Clique no botão flutuante no canto inferior direito de qualquer tela e escreva sua
pergunta (ex.: "onde vejo meus clientes?", "qual o fluxo do NIT?"). As respostas são
baseadas na documentação do próprio sistema.
