from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from invoice_generator.config import Invoice

INK = colors.HexColor("#1f2933")
MUTED = colors.HexColor("#6b7785")
RULE = colors.HexColor("#d5dbe2")
BAND = colors.HexColor("#f2f5f8")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()["BodyText"]
    body = ParagraphStyle("body", parent=base, fontSize=9.5, leading=13.5, textColor=INK)
    return {
        "title": ParagraphStyle(
            "title", parent=body, fontName="Helvetica-Bold", fontSize=26, leading=30
        ),
        "label": ParagraphStyle(
            "label", parent=body, fontName="Helvetica-Bold", fontSize=8, textColor=MUTED
        ),
        "body": body,
        "bodyBold": ParagraphStyle("bodyBold", parent=body, fontName="Helvetica-Bold"),
        "right": ParagraphStyle("right", parent=body, alignment=TA_RIGHT),
        "rightBold": ParagraphStyle(
            "rightBold", parent=body, alignment=TA_RIGHT, fontName="Helvetica-Bold"
        ),
        "meta": ParagraphStyle("meta", parent=body, fontSize=9, textColor=MUTED),
        "metaRight": ParagraphStyle(
            "metaRight", parent=body, fontSize=9, textColor=MUTED, alignment=TA_RIGHT
        ),
    }


def _party_block(title: str, name: str, address: str, email: str, s: dict) -> list:
    return [
        Paragraph(title.upper(), s["label"]),
        Spacer(1, 3),
        Paragraph(name, s["bodyBold"]),
        Paragraph(address, s["body"]),
        Paragraph(email, s["meta"]),
    ]


def _header(invoice: Invoice, s: dict) -> Table:
    meta_rows = [
        ("Invoice number", invoice.number),
        ("Invoice date", f"{invoice.invoice_date:%Y-%m-%d}"),
        ("Due date", f"{invoice.due_date:%Y-%m-%d}"),
    ]
    meta = Table(
        [[Paragraph(k, s["metaRight"]), Paragraph(v, s["right"])] for k, v in meta_rows],
        colWidths=[32 * mm, 38 * mm],
    )
    meta.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
            ]
        )
    )
    header = Table([[Paragraph("INVOICE", s["title"]), meta]], colWidths=[95 * mm, 75 * mm])
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return header


def _parties(invoice: Invoice, s: dict) -> Table:
    contractor = invoice.config.contractor
    client = invoice.config.client
    table = Table(
        [
            [
                _party_block("From", contractor.name, contractor.address, contractor.email, s),
                _party_block("Bill to", client.name, client.address, client.email, s),
            ]
        ],
        colWidths=[85 * mm, 85 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def _line_items(invoice: Invoice, s: dict) -> Table:
    charge = invoice.charge
    currency = charge.currency
    description = (
        f"{invoice.billing.service_description}<br/>"
        f"<font color='#6b7785' size='8.5'>Billing period "
        f"{invoice.period_start:%Y-%m-%d} to "
        f"{invoice.period_end:%Y-%m-%d}</font>"
    )
    rows = [
        [
            Paragraph("DESCRIPTION", s["label"]),
            Paragraph("HOURS", s["metaRight"]),
            Paragraph("RATE", s["metaRight"]),
            Paragraph("AMOUNT", s["metaRight"]),
        ],
        [
            Paragraph(description, s["body"]),
            Paragraph(f"{invoice.hours:,.2f}", s["right"]),
            Paragraph(f"{charge.rate_hourly:,.2f}", s["right"]),
            Paragraph(f"{invoice.subtotal:,.2f}", s["right"]),
        ],
        [
            "",
            "",
            Paragraph("Subtotal", s["right"]),
            Paragraph(f"{currency} {invoice.subtotal:,.2f}", s["right"]),
        ],
        [
            "",
            "",
            Paragraph(_tax_label(invoice), s["right"]),
            Paragraph(f"{currency} {invoice.tax:,.2f}", s["right"]),
        ],
        [
            "",
            "",
            Paragraph("Total due", s["rightBold"]),
            Paragraph(f"{currency} {invoice.total:,.2f}", s["rightBold"]),
        ],
    ]
    table = Table(rows, colWidths=[74 * mm, 22 * mm, 38 * mm, 36 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, -1), 6),
                ("RIGHTPADDING", (-1, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("BACKGROUND", (0, 0), (-1, 0), BAND),
                ("LINEBELOW", (0, 1), (-1, 1), 0.5, RULE),
                ("LINEABOVE", (2, 4), (-1, 4), 0.75, INK),
                ("TOPPADDING", (2, 4), (-1, 4), 7),
            ]
        )
    )
    return table


def _tax_label(invoice: Invoice) -> str:
    charge = invoice.charge
    percent = f"{charge.tax_amount_percent.normalize():f}"
    label = f"{charge.tax_type} {percent}%"
    if charge.tax_number:
        return f"{label} ({charge.tax_number})"
    return label


def _payment_details(invoice: Invoice, s: dict) -> KeepTogether:
    entries = invoice.billing.bank_info
    flow: list = [Paragraph("PAYMENT DETAILS", s["label"]), Spacer(1, 4)]
    if entries:
        rows = [
            [Paragraph(entry.key, s["meta"]), Paragraph(entry.value, s["body"])]
            for entry in entries
        ]
        table = Table(rows, colWidths=[32 * mm, 138 * mm], hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (0, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        flow.append(table)
    else:
        flow.append(Paragraph("Provided separately.", s["body"]))
    return KeepTogether(flow)


def render_pdf(invoice: Invoice, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    s = _styles()
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=f"Invoice {invoice.number}",
        author=invoice.config.contractor.name,
    )
    doc.build(
        [
            _header(invoice, s),
            Spacer(1, 12 * mm),
            _parties(invoice, s),
            Spacer(1, 12 * mm),
            _line_items(invoice, s),
            Spacer(1, 14 * mm),
            _payment_details(invoice, s),
        ]
    )
    return path
