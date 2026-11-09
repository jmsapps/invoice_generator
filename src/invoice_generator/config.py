from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from invoice_generator.timesheet import month_period


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Party(StrictModel):
    name: str
    address: str
    email: EmailStr


class BankEntry(StrictModel):
    key: str
    value: str


class ChargeInfo(StrictModel):
    tax_type: str
    tax_amount_percent: Decimal = Field(default=Decimal(0), ge=0)
    tax_number: str | None = None
    rate_hourly: Decimal = Field(gt=0)
    currency: str


class Billing(StrictModel):
    service_description: str
    invoice_number: str | None = None
    invoice_date: date | None = None
    due_days: int = Field(default=30, ge=0)
    charge_info: ChargeInfo
    bank_info: list[BankEntry] = Field(default_factory=list)


class InvoiceConfig(StrictModel):
    contractor: Party
    client: Party
    billing: Billing


class Invoice:
    def __init__(
        self,
        config: InvoiceConfig,
        client_slug: str,
        month: date,
        hours: Decimal,
        invoice_date: date,
    ) -> None:
        self.config = config
        self.client_slug = client_slug
        self.month = month
        self.hours = hours
        self.invoice_date = invoice_date
        self.period_start, self.period_end = month_period(month)

    @property
    def billing(self) -> Billing:
        return self.config.billing

    @property
    def charge(self) -> ChargeInfo:
        return self.config.billing.charge_info

    @property
    def number(self) -> str:
        return invoice_number(self.config, self.client_slug, self.month)

    @property
    def due_date(self) -> date:
        return self.invoice_date + timedelta(days=self.billing.due_days)

    @property
    def subtotal(self) -> Decimal:
        return quantize(self.hours * self.charge.rate_hourly)

    @property
    def tax(self) -> Decimal:
        return quantize(self.subtotal * self.charge.tax_amount_percent / 100)

    @property
    def total(self) -> Decimal:
        return quantize(self.subtotal + self.tax)

    @property
    def period_label(self) -> str:
        return f"{self.month:%B %Y}"


def invoice_number(config: InvoiceConfig, client_slug: str, month: date) -> str:
    return config.billing.invoice_number or f"{client_slug.upper()}-{month:%Y-%m}"


def quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def client_dir(clients_root: Path, client: str) -> Path:
    return clients_root / client


def load_config(clients_root: Path, client: str) -> InvoiceConfig:
    path = client_dir(clients_root, client) / "config.yaml"
    if not path.is_file():
        raise FileNotFoundError(path)
    data = yaml.safe_load(path.read_text()) or {}
    return InvoiceConfig.model_validate(data)
