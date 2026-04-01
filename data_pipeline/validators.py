"""
validators.py — Data validation on ingestion.

Rules are driven by pipeline_config.yaml; no hard-coded thresholds here.
Each validator returns a list of ValidationResult objects — never raises on bad data.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)

VALID_CURRENCIES: set[str] = {"USD", "EUR", "GBP", "JPY", "CAD"}


@dataclass
class ValidationResult:
    rule_name: str
    passed: bool
    message: str
    severity: str = "error"          # info | warning | error | critical


@dataclass
class ValidationReport:
    document_type: str
    external_id: str
    results: list[ValidationResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results if r.severity in ("error", "critical"))

    @property
    def critical_failures(self) -> list[ValidationResult]:
        return [r for r in self.results if not r.passed and r.severity == "critical"]

    @property
    def error_failures(self) -> list[ValidationResult]:
        return [r for r in self.results if not r.passed and r.severity == "error"]

    def summary(self) -> dict[str, Any]:
        return {
            "document_type": self.document_type,
            "external_id": self.external_id,
            "passed": self.passed,
            "total_checks": len(self.results),
            "failures": len([r for r in self.results if not r.passed]),
        }


# ---------------------------------------------------------------------------
# Rule library — each function returns a single ValidationResult
# ---------------------------------------------------------------------------

def check_required_fields(record: dict, fields: list[str]) -> list[ValidationResult]:
    results = []
    for f in fields:
        val = record.get(f)
        missing = val is None or (isinstance(val, str) and val.strip() == "")
        results.append(ValidationResult(
            rule_name=f"required:{f}",
            passed=not missing,
            message="" if not missing else f"Required field '{f}' is missing or empty",
            severity="critical",
        ))
    return results


def check_numeric_non_negative(record: dict, fields: list[str]) -> list[ValidationResult]:
    results = []
    for f in fields:
        val = record.get(f)
        if val is None:
            continue
        try:
            numeric = float(val)
            ok = numeric >= 0
        except (TypeError, ValueError):
            ok = False
        results.append(ValidationResult(
            rule_name=f"non_negative:{f}",
            passed=ok,
            message="" if ok else f"Field '{f}' must be >= 0, got {val!r}",
        ))
    return results


def check_amount_range(record: dict, field_name: str, min_val: float, max_val: float) -> ValidationResult:
    val = record.get(field_name)
    if val is None:
        return ValidationResult(rule_name=f"amount_range:{field_name}", passed=True, message="skipped (null)")
    try:
        numeric = float(val)
        ok = min_val <= numeric <= max_val
    except (TypeError, ValueError):
        ok = False
    return ValidationResult(
        rule_name=f"amount_range:{field_name}",
        passed=ok,
        message="" if ok else f"'{field_name}'={val} outside [{min_val}, {max_val}]",
    )


def check_currency_code(record: dict, valid_codes: set[str] | None = None) -> ValidationResult:
    valid = valid_codes or VALID_CURRENCIES
    code = record.get("currency")
    ok = code in valid if code else True      # null handled by required-field check
    return ValidationResult(
        rule_name="currency_code",
        passed=ok,
        message="" if ok else f"Unsupported currency code '{code}'",
    )


def check_date_field(record: dict, field_name: str) -> ValidationResult:
    val = record.get(field_name)
    if val is None:
        return ValidationResult(rule_name=f"date_parse:{field_name}", passed=True, message="null skipped")
    ok = _parse_date(val) is not None
    return ValidationResult(
        rule_name=f"date_parse:{field_name}",
        passed=ok,
        message="" if ok else f"Cannot parse '{field_name}'={val!r} as a date",
    )


def check_date_order(record: dict, field_a: str, field_b: str) -> ValidationResult:
    a = _parse_date(record.get(field_a))
    b = _parse_date(record.get(field_b))
    if a is None or b is None:
        return ValidationResult(rule_name=f"date_order:{field_a}<={field_b}", passed=True, message="null skipped")
    ok = a <= b
    return ValidationResult(
        rule_name=f"date_order:{field_a}<={field_b}",
        passed=ok,
        message="" if ok else f"{field_a}={a} must be <= {field_b}={b}",
        severity="warning",
    )


def check_invoice_balance(record: dict, tolerance: float = 0.01) -> ValidationResult:
    """subtotal + tax - discount ≈ total_amount (leakage-free arithmetic check)."""
    try:
        sub = Decimal(str(record.get("subtotal") or 0))
        tax = Decimal(str(record.get("tax_amount") or 0))
        disc = Decimal(str(record.get("discount_amount") or 0))
        total = Decimal(str(record.get("total_amount") or 0))
        diff = abs(sub + tax - disc - total)
        ok = diff <= Decimal(str(tolerance))
    except Exception:
        ok = False
        diff = None
    return ValidationResult(
        rule_name="invoice_balance",
        passed=ok,
        message="" if ok else f"Balance mismatch: |subtotal+tax-discount-total|={diff} > {tolerance}",
        severity="warning",
    )


def check_enum(record: dict, field_name: str, allowed: list[str]) -> ValidationResult:
    val = record.get(field_name)
    if val is None:
        return ValidationResult(rule_name=f"enum:{field_name}", passed=True, message="null skipped")
    ok = val in allowed
    return ValidationResult(
        rule_name=f"enum:{field_name}",
        passed=ok,
        message="" if ok else f"'{field_name}'={val!r} not in {allowed}",
    )


def check_no_future_transaction_date(record: dict, field_name: str = "transaction_date") -> ValidationResult:
    val = _parse_date(record.get(field_name))
    if val is None:
        return ValidationResult(rule_name="no_future_date", passed=True, message="null skipped")
    ok = val <= date.today()
    return ValidationResult(
        rule_name="no_future_date",
        passed=ok,
        message="" if ok else f"transaction_date {val} is in the future",
        severity="warning",
    )


# ---------------------------------------------------------------------------
# Composite validators per document type
# ---------------------------------------------------------------------------

def validate_invoice(record: dict, config: dict | None = None) -> ValidationReport:
    cfg = config or {}
    ext_id = record.get("external_id", "<unknown>")
    report = ValidationReport(document_type="invoice", external_id=ext_id)

    required = cfg.get("required_fields", ["external_id", "invoice_number", "invoice_date", "total_amount", "currency"])
    report.results.extend(check_required_fields(record, required))

    non_neg = cfg.get("numeric_non_negative", ["subtotal", "tax_amount", "discount_amount", "total_amount"])
    report.results.extend(check_numeric_non_negative(record, non_neg))

    for f in cfg.get("date_fields", ["invoice_date", "due_date"]):
        report.results.append(check_date_field(record, f))

    ar = cfg.get("amount_range", {"min": 0.01, "max": 10_000_000})
    report.results.append(check_amount_range(record, "total_amount", ar["min"], ar["max"]))

    report.results.append(check_currency_code(record, set(cfg.get("currency_codes", list(VALID_CURRENCIES)))))

    if cfg.get("balance_check", {}).get("enabled", True):
        tol = cfg.get("balance_check", {}).get("tolerance", 0.01)
        report.results.append(check_invoice_balance(record, tol))

    return report


def validate_receipt(record: dict, config: dict | None = None) -> ValidationReport:
    cfg = config or {}
    ext_id = record.get("external_id", "<unknown>")
    report = ValidationReport(document_type="receipt", external_id=ext_id)

    required = cfg.get("required_fields", ["external_id", "transaction_date", "total_amount", "currency"])
    report.results.extend(check_required_fields(record, required))

    non_neg = cfg.get("numeric_non_negative", ["subtotal", "tax_amount", "tip_amount", "total_amount"])
    report.results.extend(check_numeric_non_negative(record, non_neg))

    for f in cfg.get("date_fields", ["transaction_date"]):
        report.results.append(check_date_field(record, f))

    report.results.append(check_no_future_transaction_date(record))

    ar = cfg.get("amount_range", {"min": 0.01, "max": 50_000})
    report.results.append(check_amount_range(record, "total_amount", ar["min"], ar["max"]))

    report.results.append(check_currency_code(record, set(cfg.get("currency_codes", list(VALID_CURRENCIES)))))

    allowed_pm = cfg.get("allowed_payment_methods", [
        "cash", "credit_card", "debit_card", "digital_wallet", "check", "bank_transfer", "other", "unknown"
    ])
    report.results.append(check_enum(record, "payment_method", allowed_pm))

    return report


def validate_contract(record: dict, config: dict | None = None) -> ValidationReport:
    cfg = config or {}
    ext_id = record.get("external_id", "<unknown>")
    report = ValidationReport(document_type="contract", external_id=ext_id)

    required = cfg.get("required_fields", ["external_id", "contract_number", "title", "contract_type"])
    report.results.extend(check_required_fields(record, required))

    for f in cfg.get("date_fields", ["effective_date", "expiration_date"]):
        report.results.append(check_date_field(record, f))

    date_order = cfg.get("date_order_check", {"field_a": "effective_date", "field_b": "expiration_date"})
    report.results.append(check_date_order(record, date_order["field_a"], date_order["field_b"]))

    allowed_types = cfg.get("allowed_types", [
        "msa", "nda", "sow", "purchase_order", "lease", "employment",
        "license", "service_agreement", "partnership", "other"
    ])
    report.results.append(check_enum(record, "contract_type", allowed_types))

    return report


VALIDATORS = {
    "invoice": validate_invoice,
    "receipt": validate_receipt,
    "contract": validate_contract,
}


def validate(document_type: str, record: dict, config: dict | None = None) -> ValidationReport:
    fn = VALIDATORS.get(document_type)
    if fn is None:
        raise ValueError(f"No validator registered for document_type={document_type!r}")
    return fn(record, config)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(val: Any) -> date | None:
    if val is None:
        return None
    if isinstance(val, date):
        return val
    if isinstance(val, datetime):
        return val.date()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(str(val).strip(), fmt).date()
        except ValueError:
            continue
    return None
