"""
tests/test_transformers.py
20 Pytest unit tests — Week 2, Day 7
"""

import pytest
from datetime import datetime
from decimal import Decimal

from config.models import (
    UnifiedCustomer, UnifiedPayment, UnifiedTicket,
    CustomerStatus, PaymentStatus, TicketStatus,
)
from transformers.transformer import (
    CustomerTransformer, PaymentTransformer,
    TicketTransformer, UnifiedSchemaMapper,
)


# ─────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────

@pytest.fixture
def customers():
    return [
        UnifiedCustomer(
            id="stripe_cus_001", source="stripe", source_id="cus_001",
            email="  TEST@EXAMPLE.COM  ", name="Alice", currency="usd",
            country="US", created_at=datetime(2024, 1, 10),
        ),
        UnifiedCustomer(
            id="sf_001", source="salesforce", source_id="001",
            email="bob@sf.com", name="Bob",
        ),
    ]


@pytest.fixture
def payments():
    return [
        UnifiedPayment(
            id="stripe_ch_001", source="stripe", source_id="ch_001",
            customer_id="cus_001", amount=4999,
            currency="USD", status=PaymentStatus.SUCCEEDED,
        ),
        UnifiedPayment(
            id="stripe_ch_002", source="stripe", source_id="ch_002",
            amount=0, currency="eur", status=PaymentStatus.FAILED,
        ),
    ]


@pytest.fixture
def tickets():
    return [
        UnifiedTicket(
            id="zd_1001", source="zendesk", source_id="1001",
            subject="Cannot login", status=TicketStatus.SOLVED,
            tags=["billing", "urgent"],
            created_at=datetime(2024, 1, 1, 9, 0),
            solved_at=datetime(2024, 1, 1, 11, 30),
        ),
        UnifiedTicket(
            id="zd_1002", source="zendesk", source_id="1002",
            subject="Refund request", status=TicketStatus.OPEN,
        ),
    ]


# ─────────────────────────────────────────────
# MODEL TESTS
# ─────────────────────────────────────────────

class TestUnifiedCustomer:

    def test_email_lowercase(self):
        c = UnifiedCustomer(id="1", source="s", source_id="1",
                            email="  TEST@EXAMPLE.COM  ", name="T")
        assert c.email == "test@example.com"

    def test_currency_uppercase(self):
        c = UnifiedCustomer(id="1", source="s", source_id="1",
                            email="a@b.com", name="T", currency="usd")
        assert c.currency == "USD"

    def test_default_status_is_active(self):
        c = UnifiedCustomer(id="1", source="s", source_id="1",
                            email="a@b.com", name="T")
        assert c.status == CustomerStatus.ACTIVE

    def test_default_total_spent_zero(self):
        c = UnifiedCustomer(id="1", source="s", source_id="1",
                            email="a@b.com", name="T")
        assert c.total_spent == Decimal("0.00")


class TestUnifiedPayment:

    def test_cents_to_dollars(self):
        p = UnifiedPayment(id="1", source="stripe", source_id="1",
                           amount=4999, currency="USD",
                           status=PaymentStatus.SUCCEEDED)
        assert p.amount == Decimal("49.99")

    def test_zero_amount(self):
        p = UnifiedPayment(id="1", source="stripe", source_id="1",
                           amount=0, currency="USD",
                           status=PaymentStatus.FAILED)
        assert p.amount == Decimal("0.00")

    def test_currency_uppercase(self):
        p = UnifiedPayment(id="1", source="stripe", source_id="1",
                           amount=100, currency="eur",
                           status=PaymentStatus.SUCCEEDED)
        assert p.currency == "EUR"


# ─────────────────────────────────────────────
# CUSTOMER TRANSFORMER TESTS
# ─────────────────────────────────────────────

class TestCustomerTransformer:

    def test_returns_dataframe(self, customers):
        df = CustomerTransformer().transform(customers)
        assert len(df) > 0

    def test_null_company_filled(self, customers):
        df = CustomerTransformer().transform(customers)
        assert df["company"].null_count() == 0

    def test_null_phone_filled(self, customers):
        df = CustomerTransformer().transform(customers)
        assert df["phone"].null_count() == 0

    def test_currency_uppercase(self, customers):
        df = CustomerTransformer().transform(customers)
        for v in df["currency"].to_list():
            if v:
                assert v == v.upper()

    def test_deduplication(self):
        dupes = [
            UnifiedCustomer(id="a", source="stripe", source_id="dup",
                            email="a@b.com", name="V1"),
            UnifiedCustomer(id="a", source="stripe", source_id="dup",
                            email="a@b.com", name="V2"),
        ]
        df = CustomerTransformer().transform(dupes)
        assert len(df) == 1

    def test_dw_inserted_at_added(self, customers):
        df = CustomerTransformer().transform(customers)
        assert "dw_inserted_at" in df.columns

    def test_dw_source_system_added(self, customers):
        df = CustomerTransformer().transform(customers)
        assert "dw_source_system" in df.columns

    def test_empty_input(self):
        df = CustomerTransformer().transform([])
        assert df.is_empty()


# ─────────────────────────────────────────────
# PAYMENT TRANSFORMER TESTS
# ─────────────────────────────────────────────

class TestPaymentTransformer:

    def test_returns_dataframe(self, payments):
        df = PaymentTransformer().transform(payments)
        assert len(df) > 0

    def test_amount_usd_column(self, payments):
        df = PaymentTransformer().transform(payments)
        assert "amount_usd" in df.columns

    def test_no_null_payment_method(self, payments):
        df = PaymentTransformer().transform(payments)
        assert df["payment_method"].null_count() == 0

    def test_empty_input(self):
        df = PaymentTransformer().transform([])
        assert df.is_empty()


# ─────────────────────────────────────────────
# TICKET TRANSFORMER TESTS
# ─────────────────────────────────────────────

class TestTicketTransformer:

    def test_returns_dataframe(self, tickets):
        df = TicketTransformer().transform(tickets)
        assert len(df) > 0

    def test_tags_joined_as_string(self, tickets):
        df = TicketTransformer().transform(tickets)
        row = df.filter(df["source_id"] == "1001").to_dicts()
        assert "billing" in row[0]["tags_str"]

    def test_resolution_hours_column_exists(self, tickets):
        df = TicketTransformer().transform(tickets)
        assert "resolution_hours" in df.columns

    def test_empty_tags_become_empty_string(self, tickets):
        df = TicketTransformer().transform(tickets)
        row = df.filter(df["source_id"] == "1002").to_dicts()
        assert row[0]["tags_str"] == ""

    def test_empty_input(self):
        df = TicketTransformer().transform([])
        assert df.is_empty()
