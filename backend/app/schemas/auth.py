"""Authentication & admin schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- Auth -------------------------------------------------------------------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class MeResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    is_master_admin: bool
    tenant_id: uuid.UUID | None
    tenant_name: str | None = None
    person_id: uuid.UUID | None = None
    roles: list[str]
    modules: list[str]
    permissions: list[str]
    resources: list[str] = Field(default_factory=list)


# --- Tenant -----------------------------------------------------------------
class TenantBase(BaseModel):
    social_reason: str = Field(min_length=1, max_length=255)
    company_name: str | None = None
    cnpj: str | None = None
    email: EmailStr | None = None
    phone: str | None = None


class TenantCreate(TenantBase):
    active: bool = True
    module_codes: list[str] = Field(default_factory=list)


class TenantUpdate(BaseModel):
    social_reason: str | None = None
    company_name: str | None = None
    cnpj: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    active: bool | None = None


class TenantOut(TenantBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    mcp_api_key: str | None = None
    active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    modules: list[str] = Field(default_factory=list)
    user_count: int = 0


# --- Module -----------------------------------------------------------------
class ModuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    code: str
    description: str | None = None
    control_company_unity: bool = False
    sort_order: int = 0
    active: bool


class ModuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=64)
    description: str | None = None
    control_company_unity: bool = False
    sort_order: int = 0
    active: bool = True


class ModuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    control_company_unity: bool | None = None
    sort_order: int | None = None
    active: bool | None = None


class TenantModuleUpdate(BaseModel):
    module_codes: list[str]


# --- User -------------------------------------------------------------------
class UserBase(BaseModel):
    access_code: str = Field(min_length=1, max_length=255)
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(min_length=8)
    person_id: uuid.UUID | None = None
    # Optional person data used to create the profile when person_id is absent.
    name: str | None = None
    tenant_id: uuid.UUID | None = None
    type: str = "INTERNAL"
    mfa: bool = False
    active: bool = True
    role_ids: list[uuid.UUID] = Field(default_factory=list)
    tenant_ids: list[uuid.UUID] = Field(default_factory=list)


class UserUpdate(BaseModel):
    access_code: str | None = None
    email: EmailStr | None = None
    active: bool | None = None
    type: str | None = None
    mfa: bool | None = None
    person_id: uuid.UUID | None = None
    role_ids: list[uuid.UUID] | None = None


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=8)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    access_code: str
    email: EmailStr
    person_id: uuid.UUID | None = None
    tenant_id: uuid.UUID | None
    tenant_name: str | None = None
    type: str = "INTERNAL"
    mfa: bool = False
    active: bool
    is_master_admin: bool
    last_login_at: datetime | None = None
    created_at: datetime
    deleted_at: datetime | None = None
    roles: list["RoleOut"] = Field(default_factory=list)


class UserNameMixin(BaseModel):
    """Compatibility helper: ``UserOut`` keeps ``name`` derived from ``Person``."""

    name: str | None = None


# --- Role / Permission ------------------------------------------------------
class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    module_code: str | None = None
    description: str | None = None


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    code: str
    module_code: str | None = None
    description: str | None = None
    is_system: bool
    active: bool
    permissions: list[str] = Field(default_factory=list)


class RoleCreate(BaseModel):
    name: str
    code: str
    module_code: str | None = None
    description: str | None = None
    permission_codes: list[str] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    active: bool | None = None
    permission_codes: list[str] | None = None


# --- Audit ------------------------------------------------------------------
class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    user_id: uuid.UUID | None
    action: str
    resource: str | None = None
    resource_id: str | None = None
    meta: dict | None = None
    ip: str | None = None
    user_agent: str | None = None
    created_at: datetime


UserOut.model_rebuild()
