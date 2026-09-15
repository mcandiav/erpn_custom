import frappe
import re
from pathlib import Path
from frappe_mcp import MCP, ToolAnnotations


mcp = MCP("erpn-custom-mcp")


@mcp.tool(
    annotations=ToolAnnotations(
        title="ERPNext Status",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
def erp_status() -> dict:
    """Return basic read-only information about the current ERPNext site."""
    return {
        "site": frappe.local.site,
        "user": frappe.session.user,
        "frappe_version": frappe.__version__,
    }


CUSTOM_CODE_ROOT = Path(__file__).resolve().parent
ALLOWED_PROGRAM_SUFFIXES = {".py", ".js", ".json", ".html", ".md"}
BLOCKED_PROGRAM_NAMES = {
    ".env",
    "site_config.json",
    "common_site_config.json",
}
BLOCKED_NAME_FRAGMENTS = {
    "secret",
    "credential",
    "private_key",
    "access_token",
    "refresh_token",
}


def _safe_program_path(relative_path: str) -> Path:
    if not relative_path or not relative_path.strip():
        raise ValueError("path is required")

    candidate = (CUSTOM_CODE_ROOT / relative_path).resolve()

    try:
        relative = candidate.relative_to(CUSTOM_CODE_ROOT)
    except ValueError:
        raise ValueError("path is outside the allowed custom-code directory")

    if any(part.startswith(".") for part in relative.parts):
        raise ValueError("hidden files are not allowed")

    name_lower = candidate.name.lower()

    if candidate.name in BLOCKED_PROGRAM_NAMES:
        raise ValueError("this file is blocked")

    if any(fragment in name_lower for fragment in BLOCKED_NAME_FRAGMENTS):
        raise ValueError("this file name is blocked")

    if candidate.suffix.lower() not in ALLOWED_PROGRAM_SUFFIXES:
        raise ValueError("file type is not allowed")

    if not candidate.is_file():
        raise ValueError("file does not exist")

    return candidate


@mcp.tool(
    annotations=ToolAnnotations(
        title="List Custom Programs",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
def list_custom_programs() -> dict:
    """List readable source files from the erpn_custom application."""
    programs = []

    for file_path in sorted(CUSTOM_CODE_ROOT.rglob("*")):
        if not file_path.is_file():
            continue

        relative = file_path.relative_to(CUSTOM_CODE_ROOT)

        if "__pycache__" in relative.parts:
            continue

        if any(part.startswith(".") for part in relative.parts):
            continue

        if file_path.suffix.lower() not in ALLOWED_PROGRAM_SUFFIXES:
            continue

        name_lower = file_path.name.lower()

        if file_path.name in BLOCKED_PROGRAM_NAMES:
            continue

        if any(fragment in name_lower for fragment in BLOCKED_NAME_FRAGMENTS):
            continue

        programs.append(str(relative))

    return {
        "root": "apps/erpn_custom/erpn_custom",
        "count": len(programs),
        "programs": programs,
    }


@mcp.tool(
    annotations=ToolAnnotations(
        title="Read Custom Program",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
def read_custom_program(path: str) -> dict:
    """Read one source file from the erpn_custom application."""
    file_path = _safe_program_path(path)

    size = file_path.stat().st_size
    if size > 200_000:
        raise ValueError("file is larger than the 200 KB read limit")

    return {
        "path": str(file_path.relative_to(CUSTOM_CODE_ROOT)),
        "size": size,
        "content": file_path.read_text(encoding="utf-8", errors="replace"),
    }


def _redact_sensitive_text(text: str) -> str:
    """Redact obvious credential assignments before returning source through MCP."""
    sensitive = re.compile(
        r'(?i)\b(password|passwd|api[_-]?key|secret|client[_-]?secret|'
        r'access[_-]?token|refresh[_-]?token)\b\s*[:=]\s*([\'"])(.*?)\2'
    )

    return sensitive.sub(
        lambda m: f'{m.group(1)} = {m.group(2)}***REDACTED***{m.group(2)}',
        text,
    )


@mcp.tool(
    annotations=ToolAnnotations(
        title="Search Custom Code",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
def search_custom_code(text: str, max_results: int = 50) -> dict:
    """Search text inside readable erpn_custom source files."""
    query = (text or "").strip()

    if len(query) < 2:
        raise ValueError("search text must contain at least 2 characters")

    max_results = max(1, min(int(max_results), 100))
    query_lower = query.lower()
    matches = []

    for file_path in sorted(CUSTOM_CODE_ROOT.rglob("*")):
        if not file_path.is_file():
            continue

        relative = file_path.relative_to(CUSTOM_CODE_ROOT)

        if "__pycache__" in relative.parts:
            continue

        if any(part.startswith(".") for part in relative.parts):
            continue

        if file_path.suffix.lower() not in ALLOWED_PROGRAM_SUFFIXES:
            continue

        if file_path.name in BLOCKED_PROGRAM_NAMES:
            continue

        name_lower = file_path.name.lower()
        if any(fragment in name_lower for fragment in BLOCKED_NAME_FRAGMENTS):
            continue

        try:
            lines = file_path.read_text(
                encoding="utf-8",
                errors="replace",
            ).splitlines()
        except OSError:
            continue

        for line_number, line in enumerate(lines, start=1):
            if query_lower not in line.lower():
                continue

            matches.append({
                "path": str(relative),
                "line": line_number,
                "text": _redact_sensitive_text(line.strip())[:500],
            })

            if len(matches) >= max_results:
                return {
                    "query": query,
                    "count": len(matches),
                    "truncated": True,
                    "matches": matches,
                }

    return {
        "query": query,
        "count": len(matches),
        "truncated": False,
        "matches": matches,
    }


@mcp.tool(
    annotations=ToolAnnotations(
        title="List Server Scripts",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
def list_server_scripts() -> dict:
    """List ERPNext/Frappe Server Scripts without returning their source code."""
    rows = frappe.get_all(
        "Server Script",
        fields=[
            "name",
            "script_type",
            "reference_doctype",
            "disabled",
            "modified",
        ],
        order_by="modified desc",
        limit_page_length=200,
    )

    return {
        "count": len(rows),
        "scripts": rows,
    }


@mcp.tool(
    annotations=ToolAnnotations(
        title="Read Server Script",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
def read_server_script(name: str) -> dict:
    """Read one Frappe Server Script by exact name."""
    script_name = (name or "").strip()

    if not script_name:
        raise ValueError("name is required")

    row = frappe.db.get_value(
        "Server Script",
        script_name,
        [
            "name",
            "script_type",
            "reference_doctype",
            "disabled",
            "modified",
            "script",
        ],
        as_dict=True,
    )

    if not row:
        raise ValueError("Server Script does not exist")

    source = row.pop("script") or ""

    if len(source) > 200_000:
        raise ValueError("Server Script is larger than the 200 KB read limit")

    row["script"] = _redact_sensitive_text(source)
    return row


def _limit(value: int, default: int = 50, maximum: int = 200) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, maximum))


def _existing_fields(doctype: str, candidates: list[str]) -> list[str]:
    """Return only fields that really exist in this ERPNext version."""
    meta = frappe.get_meta(doctype)
    valid = {"name"}

    for field in meta.fields:
        valid.add(field.fieldname)

    return [field for field in candidates if field in valid]


def _customer_custom_fields() -> dict:
    """Detect Chile/customer custom fields without hard-coding fieldnames."""
    result = {}
    meta = frappe.get_meta("Customer")

    for field in meta.fields:
        label = (field.label or "").strip().lower()
        fieldname = (field.fieldname or "").strip()

        if "rut" in label or "rut" in fieldname.lower():
            result.setdefault("rut", fieldname)

        if "ranking" in label or "ranking" in fieldname.lower():
            result.setdefault("ranking", fieldname)

    return result


@mcp.tool(
    annotations=ToolAnnotations(
        title="Search Customers",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
def search_customers(query: str = "", limit: int = 50) -> dict:
    """Search ERPNext customers by code, name, RUT or commercial ranking."""
    limit = _limit(limit)
    query = (query or "").strip()

    fields = _existing_fields(
        "Customer",
        [
            "name",
            "customer_name",
            "customer_type",
            "customer_group",
            "territory",
            "mobile_no",
            "email_id",
            "disabled",
        ],
    )

    custom = _customer_custom_fields()

    for fieldname in custom.values():
        if fieldname and fieldname not in fields:
            fields.append(fieldname)

    filters = {}
    if "disabled" in fields:
        filters["disabled"] = 0

    or_filters = []

    if query:
        pattern = f"%{query}%"

        for fieldname in ["name", "customer_name"]:
            if fieldname in fields:
                or_filters.append(
                    ["Customer", fieldname, "like", pattern]
                )

        for fieldname in custom.values():
            if fieldname:
                or_filters.append(
                    ["Customer", fieldname, "like", pattern]
                )

    rows = frappe.get_all(
        "Customer",
        filters=filters,
        or_filters=or_filters or None,
        fields=fields,
        order_by="customer_name asc",
        limit_page_length=limit,
    )

    return {
        "query": query,
        "count": len(rows),
        "custom_fields": custom,
        "customers": rows,
    }


@mcp.tool(
    annotations=ToolAnnotations(
        title="Get Customer",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
def get_customer(name: str) -> dict:
    """Return safe business details for one Customer by exact ERPNext name."""
    customer = (name or "").strip()

    if not customer:
        raise ValueError("name is required")

    if not frappe.db.exists("Customer", customer):
        raise ValueError("Customer does not exist")

    fields = _existing_fields(
        "Customer",
        [
            "name",
            "customer_name",
            "customer_type",
            "customer_group",
            "territory",
            "mobile_no",
            "email_id",
            "tax_id",
            "default_currency",
            "default_price_list",
            "payment_terms",
            "disabled",
            "modified",
        ],
    )

    custom = _customer_custom_fields()

    for fieldname in custom.values():
        if fieldname and fieldname not in fields:
            fields.append(fieldname)

    row = frappe.db.get_value(
        "Customer",
        customer,
        fields,
        as_dict=True,
    )

    return {
        "custom_fields": custom,
        "customer": row,
    }


@mcp.tool(
    annotations=ToolAnnotations(
        title="Search Items",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
def search_items(query: str = "", limit: int = 50) -> dict:
    """Search ERPNext Item master records."""
    limit = _limit(limit)
    query = (query or "").strip()

    fields = _existing_fields(
        "Item",
        [
            "name",
            "item_code",
            "item_name",
            "item_group",
            "stock_uom",
            "is_stock_item",
            "disabled",
            "brand",
            "description",
        ],
    )

    filters = {}
    if "disabled" in fields:
        filters["disabled"] = 0

    or_filters = []

    if query:
        pattern = f"%{query}%"

        for fieldname in ["name", "item_code", "item_name"]:
            if fieldname in fields:
                or_filters.append(
                    ["Item", fieldname, "like", pattern]
                )

    rows = frappe.get_all(
        "Item",
        filters=filters,
        or_filters=or_filters or None,
        fields=fields,
        order_by="item_name asc",
        limit_page_length=limit,
    )

    return {
        "query": query,
        "count": len(rows),
        "items": rows,
    }


@mcp.tool(
    annotations=ToolAnnotations(
        title="List Sales Orders",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
def list_sales_orders(
    customer: str = "",
    status: str = "",
    limit: int = 50,
) -> dict:
    """List ERPNext Sales Orders with optional customer and status filters."""
    limit = _limit(limit)

    fields = _existing_fields(
        "Sales Order",
        [
            "name",
            "customer",
            "customer_name",
            "transaction_date",
            "delivery_date",
            "status",
            "company",
            "currency",
            "grand_total",
            "rounded_total",
            "advance_paid",
            "per_delivered",
            "per_billed",
            "docstatus",
            "modified",
        ],
    )

    filters = {
        "docstatus": ["!=", 2],
    }

    if customer:
        filters["customer"] = customer.strip()

    if status:
        filters["status"] = status.strip()

    rows = frappe.get_all(
        "Sales Order",
        filters=filters,
        fields=fields,
        order_by="transaction_date desc, modified desc",
        limit_page_length=limit,
    )

    return {
        "count": len(rows),
        "sales_orders": rows,
    }


@mcp.tool(
    annotations=ToolAnnotations(
        title="Get Sales Order",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
def get_sales_order(name: str) -> dict:
    """Return one Sales Order and its item lines."""
    order = (name or "").strip()

    if not order:
        raise ValueError("name is required")

    if not frappe.db.exists("Sales Order", order):
        raise ValueError("Sales Order does not exist")

    header_fields = _existing_fields(
        "Sales Order",
        [
            "name",
            "customer",
            "customer_name",
            "transaction_date",
            "delivery_date",
            "status",
            "company",
            "currency",
            "conversion_rate",
            "total",
            "net_total",
            "grand_total",
            "rounded_total",
            "advance_paid",
            "per_delivered",
            "per_billed",
            "docstatus",
            "modified",
        ],
    )

    item_fields = _existing_fields(
        "Sales Order Item",
        [
            "name",
            "idx",
            "item_code",
            "item_name",
            "description",
            "qty",
            "stock_uom",
            "rate",
            "amount",
            "warehouse",
            "delivery_date",
            "delivered_qty",
            "billed_amt",
        ],
    )

    header = frappe.db.get_value(
        "Sales Order",
        order,
        header_fields,
        as_dict=True,
    )

    items = frappe.get_all(
        "Sales Order Item",
        filters={
            "parent": order,
            "parenttype": "Sales Order",
        },
        fields=item_fields,
        order_by="idx asc",
        limit_page_length=500,
    )

    return {
        "sales_order": header,
        "items": items,
    }


@mcp.tool(
    annotations=ToolAnnotations(
        title="List Payment Entries",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
def list_payment_entries(
    party: str = "",
    from_date: str = "",
    to_date: str = "",
    limit: int = 50,
) -> dict:
    """List submitted ERPNext Payment Entries."""
    limit = _limit(limit)

    fields = _existing_fields(
        "Payment Entry",
        [
            "name",
            "posting_date",
            "payment_type",
            "party_type",
            "party",
            "party_name",
            "mode_of_payment",
            "paid_from",
            "paid_to",
            "paid_amount",
            "received_amount",
            "total_allocated_amount",
            "unallocated_amount",
            "reference_no",
            "reference_date",
            "company",
            "status",
            "docstatus",
            "modified",
        ],
    )

    filters = {
        "docstatus": 1,
    }

    if party:
        filters["party"] = party.strip()

    if from_date:
        filters["posting_date"] = [">=", from_date.strip()]

    if to_date:
        if "posting_date" in filters:
            filters["posting_date"] = [
                "between",
                [from_date.strip(), to_date.strip()],
            ]
        else:
            filters["posting_date"] = ["<=", to_date.strip()]

    rows = frappe.get_all(
        "Payment Entry",
        filters=filters,
        fields=fields,
        order_by="posting_date desc, modified desc",
        limit_page_length=limit,
    )

    return {
        "count": len(rows),
        "payment_entries": rows,
    }


@mcp.tool(
    annotations=ToolAnnotations(
        title="List Bank Transactions",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
def list_bank_transactions(
    bank_account: str = "",
    from_date: str = "",
    to_date: str = "",
    limit: int = 50,
) -> dict:
    """List ERPNext Bank Transactions."""
    limit = _limit(limit)

    fields = _existing_fields(
        "Bank Transaction",
        [
            "name",
            "date",
            "bank_account",
            "deposit",
            "withdrawal",
            "currency",
            "description",
            "reference_number",
            "party_type",
            "party",
            "allocated_amount",
            "unallocated_amount",
            "status",
            "modified",
        ],
    )

    filters = {}

    if bank_account:
        filters["bank_account"] = bank_account.strip()

    if from_date:
        filters["date"] = [">=", from_date.strip()]

    if to_date:
        if "date" in filters:
            filters["date"] = [
                "between",
                [from_date.strip(), to_date.strip()],
            ]
        else:
            filters["date"] = ["<=", to_date.strip()]

    rows = frappe.get_all(
        "Bank Transaction",
        filters=filters,
        fields=fields,
        order_by="date desc, modified desc",
        limit_page_length=limit,
    )

    return {
        "count": len(rows),
        "bank_transactions": rows,
    }


@mcp.tool(
    annotations=ToolAnnotations(
        title="Get Stock Levels",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
def get_stock_levels(
    item_code: str = "",
    warehouse: str = "",
    limit: int = 100,
) -> dict:
    """Return ERPNext Bin quantities by item and warehouse."""
    limit = _limit(limit, default=100, maximum=500)

    fields = _existing_fields(
        "Bin",
        [
            "name",
            "item_code",
            "warehouse",
            "actual_qty",
            "reserved_qty",
            "reserved_qty_for_production",
            "reserved_qty_for_sub_contract",
            "ordered_qty",
            "requested_qty",
            "indented_qty",
            "planned_qty",
            "projected_qty",
            "valuation_rate",
            "modified",
        ],
    )

    filters = {}

    if item_code:
        filters["item_code"] = item_code.strip()

    if warehouse:
        filters["warehouse"] = warehouse.strip()

    rows = frappe.get_all(
        "Bin",
        filters=filters,
        fields=fields,
        order_by="item_code asc, warehouse asc",
        limit_page_length=limit,
    )

    return {
        "count": len(rows),
        "stock": rows,
    }


def _apply_date_range(filters: dict, field: str, from_date: str, to_date: str) -> None:
    from_date = (from_date or "").strip()
    to_date = (to_date or "").strip()

    if from_date and to_date:
        filters[field] = ["between", [from_date, to_date]]
    elif from_date:
        filters[field] = [">=", from_date]
    elif to_date:
        filters[field] = ["<=", to_date]


@mcp.tool(
    annotations=ToolAnnotations(
        title="Get Customer Balance",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
def get_customer_balance(
    customer: str,
    company: str = "",
    to_date: str = "",
) -> dict:
    """Return accounting balance for one Customer from submitted GL Entries."""
    customer = (customer or "").strip()

    if not customer:
        raise ValueError("customer is required")

    if not frappe.db.exists("Customer", customer):
        raise ValueError("Customer does not exist")

    filters = {
        "party_type": "Customer",
        "party": customer,
        "is_cancelled": 0,
    }

    if company:
        filters["company"] = company.strip()

    if to_date:
        filters["posting_date"] = ["<=", to_date.strip()]

    rows = frappe.get_all(
        "GL Entry",
        filters=filters,
        fields=[
            "debit",
            "credit",
            "debit_in_account_currency",
            "credit_in_account_currency",
            "account_currency",
        ],
        limit_page_length=100000,
    )

    debit = sum(float(r.debit or 0) for r in rows)
    credit = sum(float(r.credit or 0) for r in rows)

    debit_account = sum(
        float(r.debit_in_account_currency or 0) for r in rows
    )
    credit_account = sum(
        float(r.credit_in_account_currency or 0) for r in rows
    )

    currencies = sorted({
        r.account_currency
        for r in rows
        if r.account_currency
    })

    return {
        "customer": customer,
        "company": company or None,
        "to_date": to_date or None,
        "debit": debit,
        "credit": credit,
        "balance": debit - credit,
        "debit_in_account_currency": debit_account,
        "credit_in_account_currency": credit_account,
        "balance_in_account_currency": debit_account - credit_account,
        "currencies": currencies,
        "entries_considered": len(rows),
    }


@mcp.tool(
    annotations=ToolAnnotations(
        title="Customer Ledger",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
def list_customer_ledger(
    customer: str,
    from_date: str = "",
    to_date: str = "",
    limit: int = 200,
) -> dict:
    """List General Ledger movements for one Customer."""
    customer = (customer or "").strip()

    if not customer:
        raise ValueError("customer is required")

    limit = _limit(limit, default=200, maximum=500)

    filters = {
        "party_type": "Customer",
        "party": customer,
        "is_cancelled": 0,
    }

    _apply_date_range(filters, "posting_date", from_date, to_date)

    fields = _existing_fields(
        "GL Entry",
        [
            "name",
            "posting_date",
            "account",
            "party_type",
            "party",
            "voucher_type",
            "voucher_no",
            "against",
            "debit",
            "credit",
            "account_currency",
            "debit_in_account_currency",
            "credit_in_account_currency",
            "remarks",
            "company",
        ],
    )

    rows = frappe.get_all(
        "GL Entry",
        filters=filters,
        fields=fields,
        order_by="posting_date desc, creation desc",
        limit_page_length=limit,
    )

    return {
        "customer": customer,
        "count": len(rows),
        "entries": rows,
    }


@mcp.tool(
    annotations=ToolAnnotations(
        title="List Sales Invoices",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
def list_sales_invoices(
    customer: str = "",
    status: str = "",
    from_date: str = "",
    to_date: str = "",
    limit: int = 50,
) -> dict:
    """List ERPNext Sales Invoices."""
    limit = _limit(limit)

    fields = _existing_fields(
        "Sales Invoice",
        [
            "name",
            "customer",
            "customer_name",
            "posting_date",
            "due_date",
            "status",
            "company",
            "currency",
            "grand_total",
            "rounded_total",
            "outstanding_amount",
            "paid_amount",
            "docstatus",
            "modified",
        ],
    )

    filters = {"docstatus": ["!=", 2]}

    if customer:
        filters["customer"] = customer.strip()

    if status:
        filters["status"] = status.strip()

    _apply_date_range(filters, "posting_date", from_date, to_date)

    rows = frappe.get_all(
        "Sales Invoice",
        filters=filters,
        fields=fields,
        order_by="posting_date desc, modified desc",
        limit_page_length=limit,
    )

    return {
        "count": len(rows),
        "sales_invoices": rows,
    }


@mcp.tool(
    annotations=ToolAnnotations(
        title="Get Sales Invoice",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
def get_sales_invoice(name: str) -> dict:
    """Return one Sales Invoice and its item lines."""
    invoice = (name or "").strip()

    if not invoice:
        raise ValueError("name is required")

    if not frappe.db.exists("Sales Invoice", invoice):
        raise ValueError("Sales Invoice does not exist")

    header_fields = _existing_fields(
        "Sales Invoice",
        [
            "name",
            "customer",
            "customer_name",
            "posting_date",
            "due_date",
            "status",
            "company",
            "currency",
            "total",
            "net_total",
            "grand_total",
            "rounded_total",
            "paid_amount",
            "outstanding_amount",
            "docstatus",
            "modified",
        ],
    )

    item_fields = _existing_fields(
        "Sales Invoice Item",
        [
            "idx",
            "item_code",
            "item_name",
            "description",
            "qty",
            "stock_uom",
            "rate",
            "amount",
            "warehouse",
            "sales_order",
            "delivery_note",
        ],
    )

    header = frappe.db.get_value(
        "Sales Invoice",
        invoice,
        header_fields,
        as_dict=True,
    )

    items = frappe.get_all(
        "Sales Invoice Item",
        filters={
            "parent": invoice,
            "parenttype": "Sales Invoice",
        },
        fields=item_fields,
        order_by="idx asc",
        limit_page_length=500,
    )

    return {
        "sales_invoice": header,
        "items": items,
    }


@mcp.tool(
    annotations=ToolAnnotations(
        title="List Purchase Orders",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
def list_purchase_orders(
    supplier: str = "",
    status: str = "",
    limit: int = 50,
) -> dict:
    """List ERPNext Purchase Orders."""
    limit = _limit(limit)

    fields = _existing_fields(
        "Purchase Order",
        [
            "name",
            "supplier",
            "supplier_name",
            "transaction_date",
            "schedule_date",
            "status",
            "company",
            "currency",
            "grand_total",
            "per_received",
            "per_billed",
            "docstatus",
            "modified",
        ],
    )

    filters = {"docstatus": ["!=", 2]}

    if supplier:
        filters["supplier"] = supplier.strip()

    if status:
        filters["status"] = status.strip()

    rows = frappe.get_all(
        "Purchase Order",
        filters=filters,
        fields=fields,
        order_by="transaction_date desc, modified desc",
        limit_page_length=limit,
    )

    return {
        "count": len(rows),
        "purchase_orders": rows,
    }


@mcp.tool(
    annotations=ToolAnnotations(
        title="Get Purchase Order",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
def get_purchase_order(name: str) -> dict:
    """Return one Purchase Order and its item lines."""
    order = (name or "").strip()

    if not order:
        raise ValueError("name is required")

    if not frappe.db.exists("Purchase Order", order):
        raise ValueError("Purchase Order does not exist")

    header_fields = _existing_fields(
        "Purchase Order",
        [
            "name",
            "supplier",
            "supplier_name",
            "transaction_date",
            "schedule_date",
            "status",
            "company",
            "currency",
            "grand_total",
            "per_received",
            "per_billed",
            "docstatus",
            "modified",
        ],
    )

    item_fields = _existing_fields(
        "Purchase Order Item",
        [
            "idx",
            "item_code",
            "item_name",
            "description",
            "qty",
            "received_qty",
            "stock_uom",
            "rate",
            "amount",
            "warehouse",
            "schedule_date",
        ],
    )

    header = frappe.db.get_value(
        "Purchase Order",
        order,
        header_fields,
        as_dict=True,
    )

    items = frappe.get_all(
        "Purchase Order Item",
        filters={
            "parent": order,
            "parenttype": "Purchase Order",
        },
        fields=item_fields,
        order_by="idx asc",
        limit_page_length=500,
    )

    return {
        "purchase_order": header,
        "items": items,
    }


@mcp.tool(
    annotations=ToolAnnotations(
        title="List Purchase Receipts",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
def list_purchase_receipts(
    supplier: str = "",
    from_date: str = "",
    to_date: str = "",
    limit: int = 50,
) -> dict:
    """List submitted Purchase Receipts."""
    limit = _limit(limit)

    fields = _existing_fields(
        "Purchase Receipt",
        [
            "name",
            "supplier",
            "supplier_name",
            "posting_date",
            "status",
            "company",
            "currency",
            "grand_total",
            "docstatus",
            "modified",
        ],
    )

    filters = {"docstatus": 1}

    if supplier:
        filters["supplier"] = supplier.strip()

    _apply_date_range(filters, "posting_date", from_date, to_date)

    rows = frappe.get_all(
        "Purchase Receipt",
        filters=filters,
        fields=fields,
        order_by="posting_date desc, modified desc",
        limit_page_length=limit,
    )

    return {
        "count": len(rows),
        "purchase_receipts": rows,
    }


@mcp.tool(
    annotations=ToolAnnotations(
        title="List Delivery Notes",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
def list_delivery_notes(
    customer: str = "",
    from_date: str = "",
    to_date: str = "",
    limit: int = 50,
) -> dict:
    """List submitted Delivery Notes."""
    limit = _limit(limit)

    fields = _existing_fields(
        "Delivery Note",
        [
            "name",
            "customer",
            "customer_name",
            "posting_date",
            "status",
            "company",
            "grand_total",
            "docstatus",
            "modified",
        ],
    )

    filters = {"docstatus": 1}

    if customer:
        filters["customer"] = customer.strip()

    _apply_date_range(filters, "posting_date", from_date, to_date)

    rows = frappe.get_all(
        "Delivery Note",
        filters=filters,
        fields=fields,
        order_by="posting_date desc, modified desc",
        limit_page_length=limit,
    )

    return {
        "count": len(rows),
        "delivery_notes": rows,
    }


@mcp.tool(
    annotations=ToolAnnotations(
        title="List Warehouses",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
def list_warehouses(company: str = "", limit: int = 200) -> dict:
    """List enabled ERPNext warehouses."""
    limit = _limit(limit, default=200, maximum=500)

    fields = _existing_fields(
        "Warehouse",
        [
            "name",
            "warehouse_name",
            "company",
            "parent_warehouse",
            "is_group",
            "disabled",
            "account",
            "modified",
        ],
    )

    filters = {}

    if "disabled" in fields:
        filters["disabled"] = 0

    if company:
        filters["company"] = company.strip()

    rows = frappe.get_all(
        "Warehouse",
        filters=filters,
        fields=fields,
        order_by="name asc",
        limit_page_length=limit,
    )

    return {
        "count": len(rows),
        "warehouses": rows,
    }


@mcp.tool(
    annotations=ToolAnnotations(
        title="List Bank Accounts",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
def list_bank_accounts(company: str = "", limit: int = 100) -> dict:
    """List ERPNext Bank Account master records."""
    limit = _limit(limit, default=100, maximum=200)

    fields = _existing_fields(
        "Bank Account",
        [
            "name",
            "account_name",
            "bank",
            "company",
            "account",
            "is_company_account",
            "disabled",
            "modified",
        ],
    )

    filters = {}

    if "disabled" in fields:
        filters["disabled"] = 0

    if company:
        filters["company"] = company.strip()

    rows = frappe.get_all(
        "Bank Account",
        filters=filters,
        fields=fields,
        order_by="account_name asc",
        limit_page_length=limit,
    )

    return {
        "count": len(rows),
        "bank_accounts": rows,
    }


def _normalize_mcp_result(value):
    """Convert Frappe objects, dates and decimals to plain JSON-compatible values."""
    return frappe.parse_json(frappe.as_json(value))


def _install_json_safe_tool_wrappers():
    """Normalize every registered tool result before frappe-mcp serializes it."""
    for tool_info in mcp._tool_registry.values():
        original_fn = tool_info["fn"]

        if getattr(original_fn, "_mcp_json_safe", False):
            continue

        def wrapped(*args, __fn=original_fn, **kwargs):
            return _normalize_mcp_result(__fn(*args, **kwargs))

        wrapped._mcp_json_safe = True
        tool_info["fn"] = wrapped


_install_json_safe_tool_wrappers()


@mcp.register(allow_guest=True)
def handle_mcp():
    if frappe.session.user == "Guest":
        raise frappe.AuthenticationError("Bearer authentication required")

    frappe.only_for("MCP")
