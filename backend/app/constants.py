"""System constants: module codes, permission codes and default roles.

The RBAC model is extensible: new modules/permissions/roles can be added here
and re-seeded without schema changes.
"""

from __future__ import annotations

# --- Modules ----------------------------------------------------------------
# Each module declares whether it controls scope by company/unity
# (``ControlCompanyUnity``). When True, the resources belonging to the module may
# be granted/denied within a specific ``Company``/``Unity`` (see RBAC section 3).
MODULES: list[dict] = [
    {
        "code": "CORE",
        "name": "Core",
        "description": "Funcionalidades essenciais da plataforma",
        "control_company_unity": False,
    },
    {
        "code": "ADMIN",
        "name": "Administração",
        "description": "Gestão de tenants, usuários, papéis e permissões",
        "control_company_unity": True,
    },
    {
        "code": "MARCAS",
        "name": "Marcas",
        "description": "Pesquisa e consulta de marcas",
        "control_company_unity": True,
    },
    {
        "code": "PATENTES",
        "name": "Patentes",
        "description": "Pesquisa e consulta de patentes",
        "control_company_unity": True,
    },
    {
        "code": "BUSCA",
        "name": "Busca",
        "description": "Busca global e avançada",
        "control_company_unity": True,
    },
    {
        "code": "RELATORIOS",
        "name": "Relatórios",
        "description": "Relatórios e exportações",
        "control_company_unity": True,
    },
    {
        "code": "CONFIGURACOES",
        "name": "Configurações",
        "description": "Configurações da conta e preferências",
        "control_company_unity": False,
    },
    {
        "code": "INPI_SYNC",
        "name": "Sincronização INPI",
        "description": "Datasets, importações e sincronização do INPI",
        "control_company_unity": False,
    },
    {
        "code": "AUDITORIA",
        "name": "Auditoria",
        "description": "Trilha de auditoria e logs",
        "control_company_unity": False,
    },
    {
        "code": "CLIENTES",
        "name": "Clientes",
        "description": "Gestão de empresas e clientes do tenant",
        "control_company_unity": True,
    },
]

# --- Permissions (module_code, code, name) ----------------------------------
PERMISSIONS: list[tuple[str, str, str]] = [
    # MARCAS
    ("MARCAS", "MARCAS_VIEW", "Visualizar marcas"),
    ("MARCAS", "MARCAS_SEARCH", "Pesquisar marcas"),
    ("MARCAS", "MARCAS_EXPORT", "Exportar marcas"),
    ("MARCAS", "MARCAS_ADMIN", "Administrar marcas"),
    # PATENTES
    ("PATENTES", "PATENTES_VIEW", "Visualizar patentes"),
    ("PATENTES", "PATENTES_SEARCH", "Pesquisar patentes"),
    ("PATENTES", "PATENTES_EXPORT", "Exportar patentes"),
    ("PATENTES", "PATENTES_ADMIN", "Administrar patentes"),
    # BUSCA
    ("BUSCA", "BUSCA_GLOBAL", "Executar busca global"),
    # RELATORIOS
    ("RELATORIOS", "RELATORIOS_VIEW", "Visualizar relatórios"),
    ("RELATORIOS", "RELATORIOS_EXPORT", "Exportar relatórios"),
    # CONFIGURACOES
    ("CONFIGURACOES", "CONFIG_VIEW", "Visualizar configurações"),
    ("CONFIGURACOES", "CONFIG_MANAGE", "Gerenciar configurações"),
    # ADMIN
    ("ADMIN", "TENANT_VIEW", "Visualizar tenants"),
    ("ADMIN", "TENANT_CREATE", "Criar tenants"),
    ("ADMIN", "TENANT_EDIT", "Editar tenants"),
    ("ADMIN", "TENANT_DELETE", "Excluir/desativar tenants"),
    ("ADMIN", "USER_VIEW", "Visualizar usuários"),
    ("ADMIN", "USER_CREATE", "Criar usuários"),
    ("ADMIN", "USER_EDIT", "Editar usuários"),
    ("ADMIN", "USER_DELETE", "Excluir/desativar usuários"),
    ("ADMIN", "MODULE_VIEW", "Visualizar módulos"),
    ("ADMIN", "MODULE_MANAGE", "Gerenciar módulos"),
    ("ADMIN", "ROLE_VIEW", "Visualizar papéis"),
    ("ADMIN", "ROLE_CREATE", "Criar papéis"),
    ("ADMIN", "ROLE_EDIT", "Editar papéis"),
    ("ADMIN", "ROLE_DELETE", "Excluir papéis"),
    ("ADMIN", "ROLE_MANAGE", "Gerenciar papéis e permissões"),
    ("ADMIN", "PERMISSION_VIEW", "Visualizar permissões"),
    ("ADMIN", "AUDIT_VIEW", "Visualizar auditoria"),
    # INPI_SYNC
    ("INPI_SYNC", "SYNC_VIEW", "Visualizar status de sincronização"),
    ("INPI_SYNC", "SYNC_EXECUTE", "Executar sincronização"),
    ("INPI_SYNC", "DATASET_VIEW", "Visualizar datasets"),
    ("INPI_SYNC", "IMPORT_VIEW", "Visualizar importações"),
    ("INPI_SYNC", "IMPORT_RETRY", "Reprocessar importações com falha"),
    # CLIENTES
    ("CLIENTES", "COMPANY_VIEW", "Visualizar empresas"),
    ("CLIENTES", "COMPANY_MANAGE", "Gerenciar empresas"),
    ("CLIENTES", "CUSTOMER_VIEW", "Visualizar clientes"),
    ("CLIENTES", "CUSTOMER_MANAGE", "Gerenciar clientes"),
    ("CLIENTES", "PERSON_VIEW", "Visualizar pessoas"),
    ("CLIENTES", "PERSON_MANAGE", "Gerenciar pessoas"),
    ("CLIENTES", "UNITY_VIEW", "Visualizar unidades"),
    ("CLIENTES", "UNITY_MANAGE", "Gerenciar unidades"),
    # ADMIN — RBAC avançado (Resources, Groups, UserPolicy, GroupPolicy)
    ("ADMIN", "RESOURCE_VIEW", "Visualizar recursos"),
    ("ADMIN", "RESOURCE_MANAGE", "Gerenciar recursos"),
    ("ADMIN", "GROUP_VIEW", "Visualizar grupos"),
    ("ADMIN", "GROUP_MANAGE", "Gerenciar grupos"),
    ("ADMIN", "USER_POLICY_MANAGE", "Gerenciar políticas diretas de usuário"),
    ("ADMIN", "GROUP_POLICY_MANAGE", "Gerenciar políticas de grupo"),
    ("ADMIN", "ROLE_POLICY_MANAGE", "Gerenciar políticas de papel"),
    # MARCAS — monitoramento seletivo
    ("MARCAS", "MARCAS_MONITOR", "Ativar/desativar monitoramento seletivo de marcas"),
    # PATENTES — monitoramento seletivo
    ("PATENTES", "PATENTES_MONITOR", "Ativar/desativar monitoramento seletivo de patentes"),
]

# --- Resources (module_code, code, name, description, control_company_unity) ---
# A Resource is the atomic authorization target. Its code follows the
# "modulo:acao" convention (e.g. ``marcas:user``, ``accesscontrol:admin``).
# ``control_company_unity`` allows a resource to be scoped by Company/Unity
# independently of its parent module.
RESOURCES: list[dict] = [
    # CORE
    {"module": "CORE", "code": "core:user", "name": "Uso geral da plataforma",
     "description": "Acesso básico ao core da plataforma", "control_company_unity": False},
    # ADMIN
    {"module": "ADMIN", "code": "accesscontrol:admin", "name": "Administração de acesso",
     "description": "Gestão de tenants, usuários, papéis e permissões", "control_company_unity": True},
    {"module": "ADMIN", "code": "accesscontrol:user", "name": "Usuários",
     "description": "Gestão de usuários", "control_company_unity": True},
    {"module": "ADMIN", "code": "accesscontrol:tenant", "name": "Tenants",
     "description": "Gestão de tenants", "control_company_unity": False},
    {"module": "ADMIN", "code": "accesscontrol:module", "name": "Módulos",
     "description": "Gestão do catálogo de módulos", "control_company_unity": False},
    {"module": "ADMIN", "code": "accesscontrol:resource", "name": "Recursos",
     "description": "Gestão de recursos de autorização", "control_company_unity": False},
    {"module": "ADMIN", "code": "accesscontrol:group", "name": "Grupos",
     "description": "Gestão de grupos e políticas de grupo", "control_company_unity": True},
    {"module": "ADMIN", "code": "accesscontrol:audit", "name": "Auditoria",
     "description": "Consulta da trilha de auditoria", "control_company_unity": False},
    # MARCAS
    {"module": "MARCAS", "code": "marcas:user", "name": "Consulta de marcas",
     "description": "Pesquisa e visualização de marcas", "control_company_unity": True},
    {"module": "MARCAS", "code": "marcas:export", "name": "Exportação de marcas",
     "description": "Exportar resultados de marcas", "control_company_unity": True},
    {"module": "MARCAS", "code": "marcas:admin", "name": "Administração de marcas",
     "description": "Administrar dados de marcas", "control_company_unity": True},
    {"module": "MARCAS", "code": "marcas:monitor", "name": "Monitoramento de marcas",
     "description": "Ativar/desativar monitoramento seletivo de marcas", "control_company_unity": True},
    # PATENTES
    {"module": "PATENTES", "code": "patentes:user", "name": "Consulta de patentes",
     "description": "Pesquisa e visualização de patentes", "control_company_unity": True},
    {"module": "PATENTES", "code": "patentes:export", "name": "Exportação de patentes",
     "description": "Exportar resultados de patentes", "control_company_unity": True},
    {"module": "PATENTES", "code": "patentes:admin", "name": "Administração de patentes",
     "description": "Administrar dados de patentes", "control_company_unity": True},
    {"module": "PATENTES", "code": "patentes:monitor", "name": "Monitoramento de patentes",
     "description": "Ativar/desativar monitoramento seletivo de patentes", "control_company_unity": True},
    # BUSCA
    {"module": "BUSCA", "code": "busca:global", "name": "Busca global",
     "description": "Executar busca global e avançada", "control_company_unity": True},
    # RELATORIOS
    {"module": "RELATORIOS", "code": "actionplan:user", "name": "Relatórios",
     "description": "Visualizar e exportar relatórios", "control_company_unity": True},
    # CONFIGURACOES
    {"module": "CONFIGURACOES", "code": "config:manage", "name": "Configurações",
     "description": "Gerenciar configurações da conta", "control_company_unity": False},
    # INPI_SYNC
    {"module": "INPI_SYNC", "code": "inpisync:user", "name": "Sincronização INPI",
     "description": "Datasets, importações e sincronização", "control_company_unity": False},
    # AUDITORIA
    {"module": "AUDITORIA", "code": "auditoria:view", "name": "Auditoria",
     "description": "Consultar trilha de auditoria", "control_company_unity": False},
    # CLIENTES
    {"module": "CLIENTES", "code": "clientes:company", "name": "Empresas",
     "description": "Gestão de empresas do tenant", "control_company_unity": True},
    {"module": "CLIENTES", "code": "clientes:unity", "name": "Unidades",
     "description": "Gestão de unidades/filiais das empresas", "control_company_unity": True},
    {"module": "CLIENTES", "code": "clientes:customer", "name": "Clientes",
     "description": "Gestão de clientes do tenant", "control_company_unity": True},
    {"module": "CLIENTES", "code": "clientes:person", "name": "Pessoas",
     "description": "Gestão de pessoas físicas", "control_company_unity": True},
]

# --- System roles per module (module_code, role_code, role_name, permissions) -
ROLES: list[dict] = [
    {
        "module": "MARCAS",
        "code": "MARCAS_VIEW",
        "name": "Marcas - Visualizador",
        "permissions": ["MARCAS_VIEW", "MARCAS_SEARCH"],
        "resources": ["marcas:user"],
    },
    {
        "module": "MARCAS",
        "code": "MARCAS_ADMIN",
        "name": "Marcas - Administrador",
        "permissions": ["MARCAS_VIEW", "MARCAS_SEARCH", "MARCAS_EXPORT", "MARCAS_ADMIN"],
        "resources": ["marcas:user", "marcas:export", "marcas:admin", "marcas:monitor"],
    },
    {
        "module": "PATENTES",
        "code": "PATENTES_VIEW",
        "name": "Patentes - Visualizador",
        "permissions": ["PATENTES_VIEW", "PATENTES_SEARCH"],
        "resources": ["patentes:user"],
    },
    {
        "module": "PATENTES",
        "code": "PATENTES_ADMIN",
        "name": "Patentes - Administrador",
        "permissions": [
            "PATENTES_VIEW",
            "PATENTES_SEARCH",
            "PATENTES_EXPORT",
            "PATENTES_ADMIN",
        ],
        "resources": [
            "patentes:user",
            "patentes:export",
            "patentes:admin",
            "patentes:monitor",
        ],
    },
    {
        "module": "ADMIN",
        "code": "TENANT_ADMIN",
        "name": "Administrador do Tenant",
        "permissions": [
            "TENANT_VIEW",
            "USER_VIEW",
            "USER_CREATE",
            "USER_EDIT",
            "USER_DELETE",
            "MODULE_VIEW",
            "ROLE_VIEW",
            "ROLE_CREATE",
            "ROLE_EDIT",
            "ROLE_DELETE",
            "ROLE_MANAGE",
            "PERMISSION_VIEW",
            "AUDIT_VIEW",
            "CONFIG_VIEW",
            "CONFIG_MANAGE",
            "BUSCA_GLOBAL",
            "MARCAS_VIEW",
            "MARCAS_SEARCH",
            "PATENTES_VIEW",
            "PATENTES_SEARCH",
            "RELATORIOS_VIEW",
            "SYNC_VIEW",
            "DATASET_VIEW",
            "IMPORT_VIEW",
            "MARCAS_MONITOR",
            "PATENTES_MONITOR",
        ],
        "resources": [
            "accesscontrol:admin",
            "accesscontrol:user",
            "accesscontrol:tenant",
            "accesscontrol:module",
            "accesscontrol:resource",
            "accesscontrol:group",
            "accesscontrol:audit",
            "marcas:user",
            "marcas:monitor",
            "patentes:user",
            "patentes:monitor",
            "busca:global",
            "actionplan:user",
            "config:manage",
            "inpisync:user",
            "auditoria:view",
            "clientes:company",
            "clientes:unity",
            "clientes:customer",
            "clientes:person",
        ],
    },
    {
        "module": "INPI_SYNC",
        "code": "INPI_OPERATOR",
        "name": "Operador de Ingestão INPI",
        "permissions": [
            "SYNC_VIEW",
            "SYNC_EXECUTE",
            "DATASET_VIEW",
            "IMPORT_VIEW",
            "IMPORT_RETRY",
        ],
        "resources": ["inpisync:user"],
    },
    {
        "module": "BUSCA",
        "code": "ANALISTA",
        "name": "Analista de PI",
        "permissions": [
            "BUSCA_GLOBAL",
            "MARCAS_VIEW",
            "MARCAS_SEARCH",
            "PATENTES_VIEW",
            "PATENTES_SEARCH",
            "RELATORIOS_VIEW",
            "RELATORIOS_EXPORT",
            "MARCAS_MONITOR",
            "PATENTES_MONITOR",
        ],
        "resources": [
            "busca:global",
            "marcas:user",
            "marcas:monitor",
            "patentes:user",
            "patentes:monitor",
            "actionplan:user",
        ],
    },
    {
        # Full-access role: every permission. Seeded so the default tenant admin
        # (and any operator that needs full access) never loses privileges after
        # the multi-tenant migration. Kept in sync with ALL_PERMISSION_CODES.
        "module": "ADMIN",
        "code": "SUPER_ADMIN",
        "name": "Super Administrador",
        "permissions": [code for _, code, _ in PERMISSIONS],
        # Every resource is granted to the super admin (see ``ALL_RESOURCE_CODES``).
        "resources": [r["code"] for r in RESOURCES],
    },
]

# Master admin permission = all permissions.
ALL_PERMISSION_CODES: list[str] = [code for _, code, _ in PERMISSIONS]

# Every resource code (used by the master admin / SUPER_ADMIN full-access grants).
ALL_RESOURCE_CODES: list[str] = [r["code"] for r in RESOURCES]
