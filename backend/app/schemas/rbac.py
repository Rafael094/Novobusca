"""Schemas for the advanced RBAC model (Module → Resource → Policies).

Covers the three grant paths (UserPolicy / GroupPolicy / RolePolicy), the
``Group`` aggregation, the UI ``Menu`` chain and the ``UserTenant`` /
``UserCompanyUnity`` lotação associations.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Decision = Literal["ALLOWED", "DENIED"]


# --- Resource ---------------------------------------------------------------
class ResourceBase(BaseModel):
    code: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    is_native: bool = True
    control_company_unity: bool = False
    active: bool = True


class ResourceCreate(ResourceBase):
    module_code: str | None = None


class ResourceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    control_company_unity: bool | None = None
    active: bool | None = None


class ResourceOut(ResourceBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    module_id: uuid.UUID
    module_code: str | None = None
    created_at: datetime
    updated_at: datetime


# --- Policies ---------------------------------------------------------------
class PolicyScope(BaseModel):
    company_id: uuid.UUID | None = None
    unity_id: uuid.UUID | None = None


class UserPolicyCreate(PolicyScope):
    user_id: uuid.UUID
    resource_id: uuid.UUID
    decision: Decision = "ALLOWED"


class UserPolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    resource_id: uuid.UUID
    resource_code: str | None = None
    tenant_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None
    unity_id: uuid.UUID | None = None
    decision: str
    created_at: datetime


class GroupPolicyCreate(PolicyScope):
    group_id: uuid.UUID
    resource_id: uuid.UUID
    decision: Decision = "ALLOWED"


class GroupPolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    group_id: uuid.UUID
    resource_id: uuid.UUID
    resource_code: str | None = None
    company_id: uuid.UUID | None = None
    unity_id: uuid.UUID | None = None
    decision: str
    created_at: datetime


class RolePolicyCreate(PolicyScope):
    role_id: uuid.UUID
    resource_id: uuid.UUID
    user_id: uuid.UUID | None = None


class RolePolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    role_id: uuid.UUID
    resource_id: uuid.UUID
    resource_code: str | None = None
    user_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None
    unity_id: uuid.UUID | None = None
    # Resources granted through a role are strictly ALLOWED.
    decision: str = "ALLOWED"
    created_at: datetime


# --- Group ------------------------------------------------------------------
class GroupBase(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None


class GroupCreate(GroupBase):
    active: bool = True


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    active: bool | None = None


class GroupOut(GroupBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    active: bool
    created_at: datetime
    updated_at: datetime


class UserGroupCreate(PolicyScope):
    user_id: uuid.UUID
    group_id: uuid.UUID


class UserGroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    group_id: uuid.UUID
    company_id: uuid.UUID | None = None
    unity_id: uuid.UUID | None = None
    created_at: datetime


# --- Menu (UI) --------------------------------------------------------------
class MenuItemResourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    menu_item_id: uuid.UUID
    resource_id: uuid.UUID
    resource_code: str | None = None


class MenuItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    menu_id: uuid.UUID
    parent_id: uuid.UUID | None = None
    label: str
    route: str | None = None
    icon: str | None = None
    sort_order: int = 0
    active: bool
    required_resources: list[str] = Field(default_factory=list)


class MenuOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    active: bool
    items: list[MenuItemOut] = Field(default_factory=list)


# --- Multi-tenant / lotação -------------------------------------------------
class UserTenantCreate(BaseModel):
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    is_default: bool = False


class UserTenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    is_default: bool
    created_at: datetime


class UserCompanyUnityCreate(BaseModel):
    user_id: uuid.UUID
    company_id: uuid.UUID
    unity_id: uuid.UUID | None = None
    active: bool = True


class UserCompanyUnityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    company_id: uuid.UUID
    unity_id: uuid.UUID | None = None
    active: bool
    created_at: datetime


# --- Effective access (diagnostics) -----------------------------------------
class EffectiveAccessOut(BaseModel):
    user_id: uuid.UUID
    roles: list[str]
    modules: list[str]
    permissions: list[str]
    resources: list[str]
    scoped_resources: dict
    companies: list[uuid.UUID]
    unities: list[uuid.UUID]
