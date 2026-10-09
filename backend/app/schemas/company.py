"""Schemas for tenant-scoped company / unity / customer / person (CRM) entities."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- Person -----------------------------------------------------------------
class PersonBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    cpf: str | None = None
    email: EmailStr | None = None
    cell_phone: str | None = None
    address_line: str | None = None
    address_number: str | None = None
    address_complement: str | None = None
    district: str | None = None
    city: str | None = None
    state: str | None = Field(default=None, max_length=2)
    zip_code: str | None = None
    responsibility: str | None = None
    job_title: str | None = None
    notes: str | None = None


class PersonCreate(PersonBase):
    user_id: uuid.UUID | None = None
    active: bool = True


class PersonUpdate(BaseModel):
    name: str | None = None
    cpf: str | None = None
    email: EmailStr | None = None
    cell_phone: str | None = None
    address_line: str | None = None
    address_number: str | None = None
    address_complement: str | None = None
    district: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    responsibility: str | None = None
    job_title: str | None = None
    notes: str | None = None
    user_id: uuid.UUID | None = None
    active: bool | None = None


class PersonOut(PersonBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


# --- Company ----------------------------------------------------------------
class CompanyBase(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    external_id: str | None = None
    file_document: str | None = None
    social_reason: str | None = None
    cnpj: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    notes: str | None = None


class CompanyCreate(CompanyBase):
    active: bool = True


class CompanyUpdate(BaseModel):
    company_name: str | None = None
    external_id: str | None = None
    file_document: str | None = None
    social_reason: str | None = None
    cnpj: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    notes: str | None = None
    active: bool | None = None


class CompanyOut(CompanyBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    active: bool
    customer_count: int = 0
    unity_count: int = 0
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


# --- Unity ------------------------------------------------------------------
MatrizType = Literal["MATRIZ", "FILIAL"]


class UnityBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    social_reason: str | None = None
    cnpj: str | None = None
    matriz_type: MatrizType = "FILIAL"
    cnes: str | None = None
    sanitary_license: str | None = None
    opening_hours: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address_line: str | None = None
    address_number: str | None = None
    address_complement: str | None = None
    district: str | None = None
    city: str | None = None
    state: str | None = Field(default=None, max_length=2)
    zip_code: str | None = None
    notes: str | None = None


class UnityCreate(UnityBase):
    company_id: uuid.UUID
    active: bool = True


class UnityUpdate(BaseModel):
    name: str | None = None
    social_reason: str | None = None
    cnpj: str | None = None
    matriz_type: MatrizType | None = None
    cnes: str | None = None
    sanitary_license: str | None = None
    opening_hours: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address_line: str | None = None
    address_number: str | None = None
    address_complement: str | None = None
    district: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    notes: str | None = None
    active: bool | None = None


class UnityOut(UnityBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    company_id: uuid.UUID
    company_name: str | None = None
    active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None



# --- Customer ---------------------------------------------------------------
class CustomerBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str | None = None
    document: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    notes: str | None = None


class CustomerCreate(CustomerBase):
    company_id: uuid.UUID | None = None
    unity_id: uuid.UUID | None = None
    person_id: uuid.UUID | None = None
    active: bool = True


class CustomerUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    document: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    notes: str | None = None
    company_id: uuid.UUID | None = None
    unity_id: uuid.UUID | None = None
    person_id: uuid.UUID | None = None
    active: bool | None = None


class CustomerOut(CustomerBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    company_id: uuid.UUID | None = None
    unity_id: uuid.UUID | None = None
    person_id: uuid.UUID | None = None
    company_name: str | None = None
    unity_name: str | None = None
    person_name: str | None = None
    active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class PaginatedCompanies(BaseModel):
    pagination: dict
    items: list[CompanyOut]


class PaginatedUnities(BaseModel):
    pagination: dict
    items: list[UnityOut]


class PaginatedCustomers(BaseModel):
    pagination: dict
    items: list[CustomerOut]


class PaginatedPeople(BaseModel):
    pagination: dict
    items: list[PersonOut]
