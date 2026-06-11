"""
loaders/db_loader.py
PostgreSQL mein data load karta hai — UPSERT logic ke saath.
Week 3 - Day 1-6
"""

from datetime import datetime
from typing import List

import polars as pl
from sqlalchemy import create_engine, text

from config.models import DatabaseSettings
from utils.logger import get_logger

logger = get_logger("db_loader")

# ─────────────────────────────────────────────
# TABLE DDL — automatically banti hain
# ─────────────────────────────────────────────

CUSTOMERS_DDL = """
CREATE TABLE IF NOT EXISTS dim_customers (
    id               VARCHAR(150) PRIMARY KEY,
    source           VARCHAR(50)  NOT NULL,
    source_id        VARCHAR(150) NOT NULL,
    email            VARCHAR(255),
    name             VARCHAR(500),
    company          VARCHAR(500),
    phone            VARCHAR(100),
    status           VARCHAR(50),
    currency         VARCHAR(10),
    country          VARCHAR(100),
    total_spent      NUMERIC(18,2) DEFAULT 0,
    created_at       TIMESTAMP,
    dw_inserted_at   TIMESTAMP DEFAULT NOW(),
    dw_updated_at    TIMESTAMP DEFAULT NOW(),
    dw_source_system VARCHAR(100),
    UNIQUE (source, source_id)
);
"""

PAYMENTS_DDL = """
CREATE TABLE IF NOT EXISTS fact_payments (
    id              VARCHAR(150) PRIMARY KEY,
    source          VARCHAR(50)  NOT NULL,
    source_id       VARCHAR(150) NOT NULL,
    customer_id     VARCHAR(150),
    amount_usd      NUMERIC(18,2),
    currency        VARCHAR(10),
    status          VARCHAR(50),
    description     TEXT,
    payment_method  VARCHAR(100),
    created_at      TIMESTAMP,
    dw_inserted_at  TIMESTAMP DEFAULT NOW(),
    UNIQUE (source, source_id)
);
"""

TICKETS_DDL = """
CREATE TABLE IF NOT EXISTS fact_tickets (
    id                  VARCHAR(150) PRIMARY KEY,
    source              VARCHAR(50)  NOT NULL,
    source_id           VARCHAR(150) NOT NULL,
    subject             TEXT,
    status              VARCHAR(50),
    priority            VARCHAR(50),
    requester_email     VARCHAR(255),
    assignee_email      VARCHAR(255),
    tags_str            TEXT,
    resolution_hours    NUMERIC(10,2),
    created_at          TIMESTAMP,
    updated_at          TIMESTAMP,
    solved_at           TIMESTAMP,
    satisfaction_rating VARCHAR(50),
    dw_inserted_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (source, source_id)
);
"""

ETL_LOG_DDL = """
CREATE TABLE IF NOT EXISTS etl_run_log (
    run_id              VARCHAR(100) PRIMARY KEY,
    source              VARCHAR(50),
    entity_type         VARCHAR(100),
    status              VARCHAR(50),
    records_extracted   INTEGER DEFAULT 0,
    records_loaded      INTEGER DEFAULT 0,
    records_failed      INTEGER DEFAULT 0,
    started_at          TIMESTAMP,
    completed_at        TIMESTAMP,
    error_message       TEXT
);
"""


class DatabaseLoader:
    """
    Transformed DataFrames ko PostgreSQL mein load karta hai.
    UPSERT = INSERT + ON CONFLICT DO UPDATE (no duplicates).
    Week 3, Day 4-6.
    """

    def __init__(self, settings: DatabaseSettings = None):
        self.settings = settings or DatabaseSettings()
        self.engine   = create_engine(
            self.settings.url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
        self._init_tables()

    def _init_tables(self):
        """Saari tables banao agar exist na karein."""
        with self.engine.connect() as conn:
            for ddl in [CUSTOMERS_DDL, PAYMENTS_DDL, TICKETS_DDL, ETL_LOG_DDL]:
                conn.execute(text(ddl))
            conn.commit()
        logger.info("Database tables ready hain")

    # ─────────────────────────────────────────
    # UPSERT helpers
    # ─────────────────────────────────────────

    @staticmethod
    def _chunks(lst, size):
        for i in range(0, len(lst), size):
            yield lst[i : i + size]

    # ─────────────────────────────────────────
    # CUSTOMERS UPSERT
    # ─────────────────────────────────────────

    def upsert_customers(self, df: pl.DataFrame) -> int:
        if df.is_empty():
            return 0

        pdf = df.to_pandas()
        pdf["dw_updated_at"] = datetime.utcnow().isoformat()

        records = pdf.to_dict(orient="records")
        total   = 0

        with self.engine.connect() as conn:
            for chunk in self._chunks(records, 500):
                stmt = text("""
                    INSERT INTO dim_customers
                        (id, source, source_id, email, name, company,
                         phone, status, currency, country, total_spent,
                         created_at, dw_inserted_at, dw_updated_at, dw_source_system)
                    VALUES
                        (:id, :source, :source_id, :email, :name, :company,
                         :phone, :status, :currency, :country, :total_spent,
                         :created_at, :dw_inserted_at, :dw_updated_at, :dw_source_system)
                    ON CONFLICT (source, source_id) DO UPDATE SET
                        email           = EXCLUDED.email,
                        name            = EXCLUDED.name,
                        company         = EXCLUDED.company,
                        phone           = EXCLUDED.phone,
                        status          = EXCLUDED.status,
                        currency        = EXCLUDED.currency,
                        country         = EXCLUDED.country,
                        total_spent     = EXCLUDED.total_spent,
                        dw_updated_at   = EXCLUDED.dw_updated_at
                """)
                conn.execute(stmt, chunk)
                total += len(chunk)
            conn.commit()

        logger.info(f"{total} customer records upsert ho gaye → dim_customers")
        return total

    # ─────────────────────────────────────────
    # PAYMENTS UPSERT
    # ─────────────────────────────────────────

    def upsert_payments(self, df: pl.DataFrame) -> int:
        if df.is_empty():
            return 0

        need = [
            "id", "source", "source_id", "customer_id", "amount_usd",
            "currency", "status", "description", "payment_method",
            "created_at", "dw_inserted_at",
        ]
        pdf     = df.to_pandas()
        avail   = [c for c in need if c in pdf.columns]
        records = pdf[avail].fillna("").to_dict(orient="records")
        total   = 0

        with self.engine.connect() as conn:
            for chunk in self._chunks(records, 500):
                stmt = text("""
                    INSERT INTO fact_payments
                        (id, source, source_id, customer_id, amount_usd,
                         currency, status, description, payment_method,
                         created_at, dw_inserted_at)
                    VALUES
                        (:id, :source, :source_id, :customer_id, :amount_usd,
                         :currency, :status, :description, :payment_method,
                         :created_at, :dw_inserted_at)
                    ON CONFLICT (source, source_id) DO UPDATE SET
                        status      = EXCLUDED.status,
                        amount_usd  = EXCLUDED.amount_usd,
                        customer_id = EXCLUDED.customer_id
                """)
                conn.execute(stmt, chunk)
                total += len(chunk)
            conn.commit()

        logger.info(f"{total} payment records upsert ho gaye → fact_payments")
        return total

    # ─────────────────────────────────────────
    # TICKETS UPSERT
    # ─────────────────────────────────────────

    def upsert_tickets(self, df: pl.DataFrame) -> int:
        if df.is_empty():
            return 0

        need = [
            "id", "source", "source_id", "subject", "status", "priority",
            "requester_email", "assignee_email", "tags_str",
            "resolution_hours", "created_at", "updated_at",
            "solved_at", "satisfaction_rating", "dw_inserted_at",
        ]
        pdf     = df.to_pandas()
        avail   = [c for c in need if c in pdf.columns]
        records = pdf[avail].fillna("").to_dict(orient="records")
        total   = 0

        with self.engine.connect() as conn:
            for chunk in self._chunks(records, 500):
                stmt = text("""
                    INSERT INTO fact_tickets
                        (id, source, source_id, subject, status, priority,
                         requester_email, assignee_email, tags_str,
                         resolution_hours, created_at, updated_at,
                         solved_at, satisfaction_rating, dw_inserted_at)
                    VALUES
                        (:id, :source, :source_id, :subject, :status, :priority,
                         :requester_email, :assignee_email, :tags_str,
                         :resolution_hours, :created_at, :updated_at,
                         :solved_at, :satisfaction_rating, :dw_inserted_at)
                    ON CONFLICT (source, source_id) DO UPDATE SET
                        status              = EXCLUDED.status,
                        resolution_hours    = EXCLUDED.resolution_hours,
                        satisfaction_rating = EXCLUDED.satisfaction_rating,
                        solved_at           = EXCLUDED.solved_at,
                        updated_at          = EXCLUDED.updated_at
                """)
                conn.execute(stmt, chunk)
                total += len(chunk)
            conn.commit()

        logger.info(f"{total} ticket records upsert ho gaye → fact_tickets")
        return total

    # ─────────────────────────────────────────
    # ETL RUN LOG
    # ─────────────────────────────────────────

    def log_run(self, record: dict):
        try:
            with self.engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO etl_run_log
                        (run_id, source, entity_type, status,
                         records_extracted, records_loaded, records_failed,
                         started_at, completed_at, error_message)
                    VALUES
                        (:run_id, :source, :entity_type, :status,
                         :records_extracted, :records_loaded, :records_failed,
                         :started_at, :completed_at, :error_message)
                    ON CONFLICT (run_id) DO UPDATE SET
                        status       = EXCLUDED.status,
                        records_loaded = EXCLUDED.records_loaded,
                        completed_at = EXCLUDED.completed_at,
                        error_message = EXCLUDED.error_message
                """), record)
                conn.commit()
        except Exception as e:
            logger.warning(f"Run log save nahi hua: {e}")
