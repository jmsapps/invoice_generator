from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from invoice_generator.config import Invoice, InvoiceConfig, invoice_number, load_config
from invoice_generator.email import render_email
from invoice_generator.pdf import render_pdf
from invoice_generator.timesheet import (
    TimesheetError,
    bundle_dir,
    latest_month,
    parse_month,
    read_hours,
    timesheet_path,
    write_blank,
)

COMMANDS = ("generate", "new-timesheet")
CLIENT_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="invoice-generator",
        description="Generate a client invoice PDF and matching email template.",
    )
    subparsers = parser.add_subparsers(dest="command")

    generate = subparsers.add_parser(
        "generate", help="generate the invoice PDF and email template (default)"
    )
    _add_common_args(generate)
    generate.add_argument(
        "--month",
        type=month_arg,
        help="billing month, YYYY-MM (default: the client's most recent timesheet)",
    )
    generate.add_argument(
        "--invoice-date",
        type=date.fromisoformat,
        help="invoice date, YYYY-MM-DD (default: config value, else today)",
    )
    generate.add_argument(
        "--print-email", action="store_true", help="also print the email template to stdout"
    )
    generate.set_defaults(handler=run_generate)

    scaffold = subparsers.add_parser(
        "new-timesheet", help="create a blank timesheet pre-filled with every day of the month"
    )
    _add_common_args(scaffold)
    scaffold.add_argument("--month", type=month_arg, required=True, help="billing month, YYYY-MM")
    scaffold.set_defaults(handler=run_new_timesheet)

    return parser


def client_arg(value: str) -> str:
    if not CLIENT_PATTERN.match(value):
        raise argparse.ArgumentTypeError(
            f"'{value}' must start with a lowercase letter or digit and contain only "
            "lowercase letters, digits, '-' or '_'"
        )
    return value


def month_arg(value: str) -> date:
    try:
        return parse_month(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--client",
        type=client_arg,
        required=True,
        help="client folder name under --clients-dir (lowercase, digits, '-' or '_')",
    )
    parser.add_argument(
        "--clients-dir",
        type=Path,
        default=Path("clients"),
        help="directory holding <client>/config.yaml (default: clients)",
    )


def normalize(argv: list[str]) -> list[str]:
    if argv and argv[0] in COMMANDS:
        return argv
    if argv and argv[0] in ("-h", "--help"):
        return argv
    return ["generate", *argv]


def load_client_config(args: argparse.Namespace) -> InvoiceConfig | None:
    try:
        return load_config(args.clients_dir, args.client)
    except FileNotFoundError as exc:
        print(f"error: no config found at {exc}", file=sys.stderr)
    except ValidationError as exc:
        print(f"error: invalid config for client '{args.client}'", file=sys.stderr)
        for issue in exc.errors():
            location = ".".join(str(part) for part in issue["loc"])
            print(f"  {location}: {issue['msg']}", file=sys.stderr)
    return None


def resolve_month(args: argparse.Namespace) -> date | None:
    if args.month:
        return args.month
    month = latest_month(args.clients_dir, args.client)
    if month is None:
        print(
            f"error: no timesheets for '{args.client}'. Create one with:\n"
            f"  invoice-generator new-timesheet --client {args.client} --month YYYY-MM",
            file=sys.stderr,
        )
    return month


def run_generate(args: argparse.Namespace) -> int:
    config = load_client_config(args)
    if config is None:
        return 2

    month = resolve_month(args)
    if month is None:
        return 2

    number = invoice_number(config, args.client, month)
    try:
        hours = read_hours(timesheet_path(args.clients_dir, args.client, month, number), month)
    except TimesheetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    invoice_date = args.invoice_date or config.billing.invoice_date or date.today()
    invoice = Invoice(config, args.client, month, hours, invoice_date)

    out_dir = bundle_dir(args.clients_dir, args.client, month)
    pdf_path = out_dir / f"invoice-{invoice.number}.pdf"
    email_path = out_dir / f"invoice-{invoice.number}.email.txt"

    render_pdf(invoice, pdf_path)
    email_body = render_email(invoice)
    email_path.write_text(email_body)

    print(f"period: {invoice.period_label} ({hours:,.2f} h)")
    print(f"pdf:    {pdf_path}")
    print(f"email:  {email_path}")
    if args.print_email:
        print()
        print(email_body, end="")
    return 0


def run_new_timesheet(args: argparse.Namespace) -> int:
    config = load_client_config(args)
    if config is None:
        return 2

    month = args.month
    number = invoice_number(config, args.client, month)
    try:
        path = write_blank(
            timesheet_path(args.clients_dir, args.client, month, number),
            month,
            config.client.name,
        )
    except TimesheetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"timesheet: {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(normalize(list(sys.argv[1:] if argv is None else argv)))
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
