# Invoice Generator

Generates a client invoice PDF plus a matching email template. Hours come from a per-month
Excel timesheet; everything else comes from the client's YAML config.

## Setup

```sh
uv sync
```

Copy `clients/example/` to `clients/<your-client>/` and edit its `config.yaml`. The folder name
is the value you pass to `--client`, so keep it lowercase (letters, digits, `-` and `_`).

Everything under `clients/` is gitignored apart from the example, so your configs, timesheets
and generated invoices stay local.

## Usage

Create a blank timesheet for the month, pre-filled with every day of that month:

```sh
uv run invoice-generator new-timesheet --client acme --month 2026-10
```

Open it, enter hours next to the days you worked, save. Then generate:

```sh
uv run invoice-generator --client acme
uv run invoice-generator --client acme --month 2026-10 --print-email
```

`generate` is the default command, so `--client acme` on its own works.

Options:

- `--client` (required) — folder name under `--clients-dir`
- `--clients-dir` — defaults to `clients`
- `--month` — `YYYY-MM`; defaults to the client's most recent timesheet
- `--invoice-date` — `YYYY-MM-DD`; defaults to `billing.invoice_date`, else today
- `--print-email` — also print the email template to stdout

## Layout

Each client owns a folder with its config, timesheets, and generated invoices:

```
clients/
  acme/
    config.yaml
    invoices/
      2026-10/                               # one folder per billing month
        invoice-ACME-2026-10.timesheet.xlsx
        invoice-ACME-2026-10.pdf
        invoice-ACME-2026-10.email.txt
```

The folder is named for the billing month, not the invoice date, so `--month 2026-10` always
writes to `invoices/2026-10/`. `new-timesheet` creates the timesheet there and `generate` adds
the PDF and email beside it — the whole folder is what you send the client.

## Timesheet

One `.xlsx` per client per month, living in that month's invoice folder. Columns are `Day`, `Date`, `Hours`,
`Notes`; row 1 is the header and the bottom `TOTAL` row carries a `SUM` formula for your own
reference. Rows without a date are ignored, so you can delete, reorder, or add days freely.

Every day of the month gets a row, weekends included — they are shaded so the working week still
reads at a glance, but hours logged against them count like any other day.

`Day` is a formula (`TEXT($B2,"ddd")`) that reads the weekday off the date, so it fills itself in
and stays right if you change a date. Only `Hours` is read off the sheet.

Reading a timesheet fails loudly on a date outside the month, a duplicate date, negative hours,
or a non-numeric hours cell. Notes are for you — they do not appear on the invoice.

The billing period is always the **full calendar month**, and total hours are the sum of the
sheet, so `period_start`, `period_end`, and `hours` are not config fields.

## Config

```yaml
contractor:
  name: ...
  address: ...
  email: ...
client:
  name: ...
  address: ...
  email: ...
billing:
  service_description: Consulting and software development
  invoice_number: ACME-2026-10  # optional; defaults to <CLIENT>-<YYYY-MM>
  invoice_date: 2026-11-02          # optional; defaults to today
  due_days: 30                      # optional; defaults to 30
  charge_info:
    tax_type: VAT
    tax_amount_percent: 0           # percentage of the subtotal; 0 if not charging tax
    tax_number: XX123456789         # optional; shown next to the tax label
    rate_hourly: 70
    currency: EUR
  bank_info:
    - key: IBAN
      value: ...
```

Unknown keys are rejected and every field is validated by pydantic, so a typo or an unfilled
placeholder fails before a PDF is written.

## Development

```sh
uv run ruff check .
uv run ruff format .
```
