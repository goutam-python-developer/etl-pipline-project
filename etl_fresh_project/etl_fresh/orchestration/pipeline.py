

import uuid
import time
from datetime import datetime, timedelta

from extractors.stripe_extractor     import StripeExtractor
from extractors.salesforce_extractor import SalesforceExtractor
from extractors.zendesk_extractor    import ZendeskExtractor
from transformers.transformer        import (
    CustomerTransformer, PaymentTransformer,
    TicketTransformer, UnifiedSchemaMapper,
)
from loaders.db_loader  import DatabaseLoader
from utils.alerting     import SlackAlerter, EmailAlerter
from utils.logger       import get_logger

logger = get_logger("pipeline")


class ETLPipeline:
    

    def __init__(self):
        self.db     = DatabaseLoader()
        self.slack  = SlackAlerter()
        self.email  = EmailAlerter()
        self.mapper = UnifiedSchemaMapper()

    # ─────────────────────────────────────────
    # STRIPE CUSTOMERS
    # ─────────────────────────────────────────

    def run_stripe_customers(self, hours: int = 24) -> dict:
        run_id = str(uuid.uuid4())[:8]
        source = "stripe"
        entity = "customers"
        t0     = time.time()
        extracted = loaded = 0

        logger.info(f"[{run_id}] Stripe customers pipeline shuru...")
        since = datetime.utcnow() - timedelta(hours=hours)

        try:
            ext = StripeExtractor()
            tr  = CustomerTransformer()

            for batch in ext.extract_customers(created_after=since):
                extracted += len(batch)
                df  = tr.transform(batch)
                df  = self.mapper.map_customers(df)
                loaded += self.db.upsert_customers(df)

            dur = time.time() - t0
            self.slack.send_success(run_id, source, entity, loaded, dur)
            self._log(run_id, source, entity, "success", extracted, loaded)
            logger.info(f"[{run_id}] ✅ Done — {loaded} records")
            return {"status": "success", "loaded": loaded}

        except Exception as e:
            logger.error(f"[{run_id}] ❌ Failed: {e}")
            self.slack.send_failure(run_id, source, entity, str(e))
            self.email.send_failure(run_id, source, str(e))
            self._log(run_id, source, entity, "failed", extracted, loaded, str(e))
            return {"status": "failed", "error": str(e)}

    # ─────────────────────────────────────────
    # STRIPE PAYMENTS
    # ─────────────────────────────────────────

    def run_stripe_payments(self, hours: int = 24) -> dict:
        run_id = str(uuid.uuid4())[:8]
        source = "stripe"
        entity = "payments"
        t0     = time.time()
        extracted = loaded = 0

        logger.info(f"[{run_id}] Stripe payments pipeline shuru...")
        since = datetime.utcnow() - timedelta(hours=hours)

        try:
            ext = StripeExtractor()
            tr  = PaymentTransformer()

            for batch in ext.extract_payments(created_after=since):
                extracted += len(batch)
                df     = tr.transform(batch)
                loaded += self.db.upsert_payments(df)

            dur = time.time() - t0
            self.slack.send_success(run_id, source, entity, loaded, dur)
            self._log(run_id, source, entity, "success", extracted, loaded)
            logger.info(f"[{run_id}] ✅ Done — {loaded} records")
            return {"status": "success", "loaded": loaded}

        except Exception as e:
            logger.error(f"[{run_id}] ❌ Failed: {e}")
            self.slack.send_failure(run_id, source, entity, str(e))
            self._log(run_id, source, entity, "failed", extracted, loaded, str(e))
            return {"status": "failed", "error": str(e)}

    # ─────────────────────────────────────────
    # SALESFORCE ACCOUNTS
    # ─────────────────────────────────────────

    def run_salesforce_accounts(self, hours: int = 24) -> dict:
        run_id = str(uuid.uuid4())[:8]
        source = "salesforce"
        entity = "accounts"
        t0     = time.time()
        extracted = loaded = 0

        logger.info(f"[{run_id}] Salesforce accounts pipeline shuru...")
        since = datetime.utcnow() - timedelta(hours=hours)

        try:
            ext = SalesforceExtractor()
            tr  = CustomerTransformer()

            for batch in ext.extract_accounts(modified_after=since):
                extracted += len(batch)
                df  = tr.transform(batch)
                df  = self.mapper.map_customers(df)
                loaded += self.db.upsert_customers(df)

            dur = time.time() - t0
            self.slack.send_success(run_id, source, entity, loaded, dur)
            self._log(run_id, source, entity, "success", extracted, loaded)
            logger.info(f"[{run_id}] ✅ Done — {loaded} records")
            return {"status": "success", "loaded": loaded}

        except Exception as e:
            logger.error(f"[{run_id}] ❌ Failed: {e}")
            self.slack.send_failure(run_id, source, entity, str(e))
            self._log(run_id, source, entity, "failed", extracted, loaded, str(e))
            return {"status": "failed", "error": str(e)}

    # ─────────────────────────────────────────
    # ZENDESK TICKETS
    # ─────────────────────────────────────────

    def run_zendesk_tickets(self, hours: int = 24) -> dict:
        run_id = str(uuid.uuid4())[:8]
        source = "zendesk"
        entity = "tickets"
        t0     = time.time()
        extracted = loaded = 0

        logger.info(f"[{run_id}] Zendesk tickets pipeline shuru...")
        since = datetime.utcnow() - timedelta(hours=hours)

        try:
            ext = ZendeskExtractor()
            tr  = TicketTransformer()

            for batch in ext.extract_tickets(updated_after=since):
                extracted += len(batch)
                df     = tr.transform(batch)
                loaded += self.db.upsert_tickets(df)

            dur = time.time() - t0
            self.slack.send_success(run_id, source, entity, loaded, dur)
            self._log(run_id, source, entity, "success", extracted, loaded)
            logger.info(f"[{run_id}] ✅ Done — {loaded} records")
            return {"status": "success", "loaded": loaded}

        except Exception as e:
            logger.error(f"[{run_id}] ❌ Failed: {e}")
            self.slack.send_failure(run_id, source, entity, str(e))
            self._log(run_id, source, entity, "failed", extracted, loaded, str(e))
            return {"status": "failed", "error": str(e)}

    # ─────────────────────────────────────────
    # FULL PIPELINE
    # ─────────────────────────────────────────

    def run_all(self, hours: int = 24):
        logger.info("=" * 55)
        logger.info("  FULL ETL PIPELINE SHURU HO RAHA HAI")
        logger.info("=" * 55)

        results = {
            "stripe_customers":    self.run_stripe_customers(hours),
            "stripe_payments":     self.run_stripe_payments(hours),
            "salesforce_accounts": self.run_salesforce_accounts(hours),
            "zendesk_tickets":     self.run_zendesk_tickets(hours),
        }

        passed = sum(1 for r in results.values() if r.get("status") == "success")
        failed = len(results) - passed

        logger.info("=" * 55)
        logger.info(f"  COMPLETE: {passed} success, {failed} failed")
        logger.info("=" * 55)
        return results

    def _log(self, run_id, source, entity, status,
             extracted, loaded, error=None):
        self.db.log_run({
            "run_id":            run_id,
            "source":            source,
            "entity_type":       entity,
            "status":            status,
            "records_extracted": extracted,
            "records_loaded":    loaded,
            "records_failed":    0 if status == "success" else 1,
            "started_at":        datetime.utcnow().isoformat(),
            "completed_at":      datetime.utcnow().isoformat(),
            "error_message":     error or "",
        })


# ── Direct chalane ke liye ──
if __name__ == "__main__":
    ETLPipeline().run_all(hours=24)
