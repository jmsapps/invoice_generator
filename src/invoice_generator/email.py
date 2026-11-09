from __future__ import annotations

from invoice_generator.config import Invoice


def render_email(invoice: Invoice) -> str:
    client = invoice.config.client
    contractor = invoice.config.contractor
    currency = invoice.charge.currency
    lines = [
        f"To: {client.email}",
        f"From: {contractor.email}",
        f"Subject: Invoice {invoice.number} - {invoice.period_label}",
        "",
        f"Dear {client.name},",
        "",
        f"Attached is invoice for month {invoice.period_label}.",
        "",
        f"Invoice number: {invoice.number}",
        f"Billing period: {invoice.period_start:%Y-%m-%d} to {invoice.period_end:%Y-%m-%d}",
        f"Amount due: {currency} {invoice.total:,.2f}",
        f"Due date: {invoice.due_date:%Y-%m-%d}",
        "",
        "Please let me know if anything needs adjusting.",
        "",
        "Best regards,",
        contractor.name,
        contractor.email,
        "",
    ]
    return "\n".join(lines)
