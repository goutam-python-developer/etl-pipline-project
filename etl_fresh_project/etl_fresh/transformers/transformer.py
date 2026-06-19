"""
transformers/transformer.py
Data cleaning aur transformation.
Week 2 - Day 1-6: Polars + Pandas
"""

from datetime import datetime
from typing import List

import polars as pl

from config.models import UnifiedCustomer, UnifiedPayment, UnifiedTicket
from utils.logger import get_logger

logger = get_logger("transformer")


# ─────────────────────────────────────────────────────────
# CUSTOMER TRANSFORMER
# ─────────────────────────────────────────────────────────

class CustomerTransformer:
    

    def transform(self, customers: List[UnifiedCustomer]) -> pl.DataFrame:
        if not customers:
            return pl.DataFrame()

        # Pydantic models → dicts → Polars DataFrame
        rows = []
        for c in customers:
            d = c.model_dump()
            d["total_spent"]   = float(d["total_spent"])
            d["metadata_json"] = str(d.pop("metadata", {}))
            # datetime → string
            for k in ("created_at", "updated_at", "extracted_at"):
                if d.get(k) and hasattr(d[k], "isoformat"):
                    d[k] = d[k].isoformat()
            rows.append(d)

        df = pl.DataFrame(rows)
        df = self._handle_nulls(df)
        df = self._normalize_currency(df)
        df = self._deduplicate(df)
        df = self._add_meta(df)

        logger.info(f"Customer transform complete: {len(df)} records")
        return df

    def _handle_nulls(self, df: pl.DataFrame) -> pl.DataFrame:
        return df.with_columns([
            pl.col("company").fill_null("Unknown Company"),
            pl.col("phone").fill_null(""),
            pl.col("country").fill_null("Unknown"),
            pl.col("total_spent").fill_null(0.0),
            pl.col("currency").fill_null("USD"),
        ])

    def _normalize_currency(self, df: pl.DataFrame) -> pl.DataFrame:
        if "currency" in df.columns:
            df = df.with_columns([
                pl.col("currency").str.to_uppercase()
            ])
        return df

    def _deduplicate(self, df: pl.DataFrame) -> pl.DataFrame:
        """Ek hi source + source_id ka ek record rakho."""
        return df.unique(subset=["source", "source_id"], keep="last")

    def _add_meta(self, df: pl.DataFrame) -> pl.DataFrame:
        return df.with_columns([
            pl.lit(datetime.utcnow().isoformat()).alias("dw_inserted_at"),
            pl.lit("etl_pipeline").alias("dw_source_system"),
        ])


# ─────────────────────────────────────────────────────────
# PAYMENT TRANSFORMER
# ─────────────────────────────────────────────────────────

class PaymentTransformer:
    """Stripe payment data clean karta hai."""

    def transform(self, payments: List[UnifiedPayment]) -> pl.DataFrame:
        if not payments:
            return pl.DataFrame()

        rows = []
        for p in payments:
            d = p.model_dump()
            d["amount_usd"] = float(d.pop("amount", 0))
            d.pop("metadata", None)
            for k in ("created_at", "extracted_at"):
                if d.get(k) and hasattr(d[k], "isoformat"):
                    d[k] = d[k].isoformat()
            rows.append(d)

        df = pl.DataFrame(rows)
        df = df.with_columns([
            pl.col("customer_id").fill_null(""),
            pl.col("description").fill_null(""),
            pl.col("payment_method").fill_null("unknown"),
            pl.col("amount_usd").round(2),
        ])
        df = df.unique(subset=["source", "source_id"], keep="last")
        df = df.with_columns([
            pl.lit(datetime.utcnow().isoformat()).alias("dw_inserted_at"),
        ])

        logger.info(f"Payment transform complete: {len(df)} records")
        return df


# ─────────────────────────────────────────────────────────
# TICKET TRANSFORMER
# ─────────────────────────────────────────────────────────

class TicketTransformer:
    """Zendesk ticket data clean karta hai."""

    def transform(self, tickets: List[UnifiedTicket]) -> pl.DataFrame:
        if not tickets:
            return pl.DataFrame()

        rows = []
        for t in tickets:
            d = t.model_dump()
            d["tags_str"] = ",".join(d.pop("tags", []))
            d.pop("metadata", None)
            for k in ("created_at", "updated_at", "solved_at", "extracted_at"):
                if d.get(k) and hasattr(d[k], "isoformat"):
                    d[k] = d[k].isoformat()
            rows.append(d)

        df = pl.DataFrame(rows)
        df = df.with_columns([
            pl.col("description").fill_null(""),
            pl.col("priority").fill_null("normal"),
            pl.col("requester_email").fill_null(""),
            pl.col("assignee_email").fill_null(""),
            pl.col("satisfaction_rating").fill_null(""),
        ])
        df = self._resolution_hours(df)
        df = df.unique(subset=["source", "source_id"], keep="last")
        df = df.with_columns([
            pl.lit(datetime.utcnow().isoformat()).alias("dw_inserted_at"),
        ])

        logger.info(f"Ticket transform complete: {len(df)} records")
        return df

    def _resolution_hours(self, df: pl.DataFrame) -> pl.DataFrame:
        """Ticket solve hone mein kitne ghante lage."""
        try:
            df = df.with_columns([
                pl.col("created_at").str.strptime(
                    pl.Datetime, format=None, strict=False
                ).alias("_c"),
                pl.col("solved_at").str.strptime(
                    pl.Datetime, format=None, strict=False
                ).alias("_s"),
            ]).with_columns([
                (
                    (pl.col("_s") - pl.col("_c"))
                    .dt.total_seconds() / 3600.0
                ).round(2).fill_null(-1.0).alias("resolution_hours")
            ]).drop(["_c", "_s"])
        except Exception as e:
            logger.warning(f"Resolution hours compute nahi hua: {e}")
            df = df.with_columns([pl.lit(-1.0).alias("resolution_hours")])
        return df


# ─────────────────────────────────────────────────────────
# UNIFIED SCHEMA MAPPER  (Week 2 - Day 4-6)
# ─────────────────────────────────────────────────────────

class UnifiedSchemaMapper:
   

    CUSTOMER_COLS = [
        "id", "source", "source_id", "email", "name",
        "company", "phone", "status", "currency", "country",
        "total_spent", "created_at", "dw_inserted_at", "dw_source_system",
    ]

    def map_customers(self, df: pl.DataFrame) -> pl.DataFrame:
        cols = [c for c in self.CUSTOMER_COLS if c in df.columns]
        return df.select(cols)
