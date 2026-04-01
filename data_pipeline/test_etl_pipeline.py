"""
test_etl_pipeline.py — Unit tests for ETL validators and transform layer.

No live DB required — loaders are mocked.
Run: pytest data_pipeline/test_etl_pipeline.py -v
"""
import pytest
from validators import (
    validate_invoice,
    validate_receipt,
    validate_contract,
    check_invoice_balance,
    check_date_order,
    ValidationReport,
)
from etl_pipeline import transform_record, stratified_split


# ---------------------------------------------------------------------------
# Validator tests
# ---------------------------------------------------------------------------

class TestInvoiceValidator:
    def _base(self, **kwargs) -> dict:
        return {
            "external_id": "INV-001",
            "invoice_number": "2024-001",
            "invoice_date": "2024-01-15",
            "total_amount": 1000.00,
            "currency": "USD",
            "subtotal": 900.00,
            "tax_amount": 100.00,
            "discount_amount": 0.00,
            **kwargs,
        }

    def test_valid_invoice_passes(self):
        report = validate_invoice(self._base())
        assert report.passed

    def test_missing_required_field_fails(self):
        rec = self._base()
        del rec["invoice_number"]
        report = validate_invoice(rec)
        assert not report.passed
        assert any("invoice_number" in r.rule_name for r in report.critical_failures)

    def test_negative_total_fails(self):
        report = validate_invoice(self._base(total_amount=-10))
        assert not report.passed

    def test_unsupported_currency_fails(self):
        report = validate_invoice(self._base(currency="XYZ"))
        assert not report.passed

    def test_balance_mismatch_is_warning(self):
        # subtotal(900) + tax(100) - discount(0) = 1000 != total(999)
        report = validate_invoice(self._base(total_amount=999.00))
        failures = [r for r in report.results if not r.passed]
        assert any(r.rule_name == "invoice_balance" and r.severity == "warning" for r in failures)

    def test_balance_within_tolerance_passes(self):
        result = check_invoice_balance(
            {"subtotal": 900, "tax_amount": 100, "discount_amount": 0, "total_amount": 1000.005},
            tolerance=0.01,
        )
        assert result.passed

    def test_invalid_date_fails(self):
        report = validate_invoice(self._base(invoice_date="not-a-date"))
        assert not report.passed


class TestReceiptValidator:
    def _base(self, **kwargs) -> dict:
        return {
            "external_id": "RCP-001",
            "transaction_date": "2024-01-10",
            "total_amount": 45.50,
            "currency": "USD",
            "payment_method": "credit_card",
            **kwargs,
        }

    def test_valid_receipt_passes(self):
        assert validate_receipt(self._base()).passed

    def test_invalid_payment_method_fails(self):
        report = validate_receipt(self._base(payment_method="bitcoin"))
        assert not report.passed

    def test_future_date_is_warning(self):
        report = validate_receipt(self._base(transaction_date="2099-12-31"))
        warnings = [r for r in report.results if not r.passed and r.severity == "warning"]
        assert any(r.rule_name == "no_future_date" for r in warnings)


class TestContractValidator:
    def _base(self, **kwargs) -> dict:
        return {
            "external_id": "CTR-001",
            "contract_number": "MSA-2024-001",
            "title": "Master Service Agreement",
            "contract_type": "msa",
            "effective_date": "2024-01-01",
            "expiration_date": "2025-01-01",
            **kwargs,
        }

    def test_valid_contract_passes(self):
        assert validate_contract(self._base()).passed

    def test_invalid_contract_type_fails(self):
        report = validate_contract(self._base(contract_type="magic_contract"))
        assert not report.passed

    def test_date_order_violation_is_warning(self):
        report = validate_contract(self._base(
            effective_date="2025-01-01",
            expiration_date="2024-01-01",
        ))
        failures = [r for r in report.results if not r.passed]
        assert any("date_order" in r.rule_name for r in failures)


# ---------------------------------------------------------------------------
# Transform tests
# ---------------------------------------------------------------------------

class TestTransformRecord:
    def test_keys_lowercased(self):
        raw = {"EXTERNAL_ID": "X1", "Invoice_Number": "INV"}
        rec = transform_record(raw, "invoice", "test.json")
        assert "external_id" in rec
        assert "invoice_number" in rec

    def test_external_id_generated_when_missing(self):
        rec = transform_record({"invoice_number": "INV-999"}, "invoice", "file.json")
        assert rec["external_id"].startswith("INV-")

    def test_external_id_deterministic(self):
        raw = {"invoice_number": "INV-999"}
        r1 = transform_record(raw, "invoice", "file.json")
        r2 = transform_record(raw, "invoice", "file.json")
        assert r1["external_id"] == r2["external_id"]

    def test_numeric_coercion(self):
        raw = {"external_id": "X1", "total_amount": "1,234.56"}
        rec = transform_record(raw, "invoice", "file.json")
        assert rec["total_amount"] == 1234.56

    def test_source_file_attached(self):
        rec = transform_record({"external_id": "X1"}, "invoice", "my_file.csv")
        assert rec["_source_file"] == "my_file.csv"


# ---------------------------------------------------------------------------
# Stratified split — no data leakage
# ---------------------------------------------------------------------------

class TestStratifiedSplit:
    def _make_records(self, n_per_class: int, classes=("A", "B", "C")) -> list[dict]:
        records = []
        for cls in classes:
            for i in range(n_per_class):
                records.append({"id": f"{cls}-{i}", "label": cls, "value": i})
        return records

    def test_split_sizes(self):
        records = self._make_records(100)
        train, test = stratified_split(records, "label", test_size=0.2)
        assert abs(len(train) / len(records) - 0.8) < 0.05
        assert abs(len(test) / len(records) - 0.2) < 0.05

    def test_class_distribution_preserved(self):
        records = self._make_records(100)
        train, test = stratified_split(records, "label", test_size=0.2)
        from collections import Counter
        train_dist = Counter(r["label"] for r in train)
        test_dist = Counter(r["label"] for r in test)
        # Each class should appear in both splits
        assert set(train_dist.keys()) == set(test_dist.keys())

    def test_no_overlap(self):
        records = self._make_records(50)
        train, test = stratified_split(records, "label", test_size=0.2)
        train_ids = {r["id"] for r in train}
        test_ids = {r["id"] for r in test}
        assert train_ids.isdisjoint(test_ids), "Data leakage: same record in train and test"

    def test_deterministic_with_seed(self):
        records = self._make_records(50)
        t1, v1 = stratified_split(records, "label", random_seed=42)
        t2, v2 = stratified_split(records, "label", random_seed=42)
        assert [r["id"] for r in t1] == [r["id"] for r in t2]
