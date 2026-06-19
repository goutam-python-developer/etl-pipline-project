
import time
from datetime import datetime
from typing import Generator, List, Optional

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config.models import (
    StripeSettings,
    UnifiedCustomer,
    UnifiedPayment,
    PaymentStatus,
)
from utils.logger import get_logger

logger = get_logger("stripe_extractor")


class StripeExtractor:
    

    BASE_URL = "https://api.stripe.com/v1"

    def __init__(self, settings: Optional[StripeSettings] = None):
        self.settings = settings or StripeSettings()
        self.session = requests.Session()
        self.session.auth = (self.settings.secret_key, "")
        self.session.headers.update({
            "Stripe-Version": self.settings.api_version,
        })

    # ── Retry decorator: network error pe 3 baar try karega ──
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(
            (requests.Timeout, requests.ConnectionError)
        ),
    )
    def _get(self, endpoint: str, params: dict = None) -> dict:
        url = f"{self.BASE_URL}/{endpoint}"
        response = self.session.get(url, params=params or {}, timeout=30)

        # Rate limit handle karo
        if response.status_code == 429:
            wait_sec = int(response.headers.get("Retry-After", 10))
            logger.warning(f"Rate limit! {wait_sec}s wait kar raha hoon...")
            time.sleep(wait_sec)
            response = self.session.get(url, params=params or {}, timeout=30)

        response.raise_for_status()
        return response.json()

    # ─────────────────────────────────────────
    # CUSTOMERS
    # ─────────────────────────────────────────

    def extract_customers(
        self,
        limit: int = 100,
        created_after: Optional[datetime] = None,
    ) -> Generator[List[UnifiedCustomer], None, None]:
        """
        Cursor-based pagination se customers fetch karta hai.
        Ek batch mein 'limit' customers aate hain.
        """
        params: dict = {"limit": limit}
        if created_after:
            params["created[gte]"] = int(created_after.timestamp())

        starting_after = None
        page = 1

        while True:
            if starting_after:
                params["starting_after"] = starting_after

            logger.info(f"Stripe customers page {page} fetch ho rahi hai...")
            data = self._get("customers", params)

            batch: List[UnifiedCustomer] = []
            for raw in data.get("data", []):
                try:
                    batch.append(self._map_customer(raw))
                except Exception as e:
                    logger.error(f"Customer map nahi hua {raw.get('id')}: {e}")

            logger.info(f"Page {page}: {len(batch)} customers mile")
            yield batch

            # Aur records hain?
            if not data.get("has_more"):
                break

            starting_after = data["data"][-1]["id"]
            page += 1

    def _map_customer(self, raw: dict) -> UnifiedCustomer:
        return UnifiedCustomer(
            id=f"stripe_{raw['id']}",
            source="stripe",
            source_id=raw["id"],
            email=raw.get("email") or "unknown@stripe.com",
            name=raw.get("name") or raw.get("description") or "Unknown",
            phone=raw.get("phone"),
            currency=raw.get("currency", "USD"),
            country=(
                raw.get("address", {}).get("country")
                if raw.get("address") else None
            ),
            created_at=(
                datetime.fromtimestamp(raw["created"])
                if raw.get("created") else None
            ),
            metadata=raw.get("metadata", {}),
        )

    # ─────────────────────────────────────────
    # PAYMENTS
    # ─────────────────────────────────────────

    def extract_payments(
        self,
        limit: int = 100,
        created_after: Optional[datetime] = None,
    ) -> Generator[List[UnifiedPayment], None, None]:
        """Stripe charges/payments cursor pagination se."""
        params: dict = {"limit": limit}
        if created_after:
            params["created[gte]"] = int(created_after.timestamp())

        starting_after = None
        page = 1

        while True:
            if starting_after:
                params["starting_after"] = starting_after

            logger.info(f"Stripe payments page {page} fetch ho rahi hai...")
            data = self._get("charges", params)

            batch: List[UnifiedPayment] = []
            for raw in data.get("data", []):
                try:
                    batch.append(self._map_payment(raw))
                except Exception as e:
                    logger.error(f"Payment map nahi hua {raw.get('id')}: {e}")

            logger.info(f"Page {page}: {len(batch)} payments mile")
            yield batch

            if not data.get("has_more"):
                break

            starting_after = data["data"][-1]["id"]
            page += 1

    def _map_payment(self, raw: dict) -> UnifiedPayment:
        status_map = {
            "succeeded": PaymentStatus.SUCCEEDED,
            "failed":    PaymentStatus.FAILED,
            "pending":   PaymentStatus.PENDING,
        }
        return UnifiedPayment(
            id=f"stripe_{raw['id']}",
            source="stripe",
            source_id=raw["id"],
            customer_id=raw.get("customer"),
            amount=raw.get("amount", 0),
            currency=raw.get("currency", "USD"),
            status=status_map.get(raw.get("status", ""), PaymentStatus.PENDING),
            description=raw.get("description"),
            payment_method=(
                raw.get("payment_method_details", {}).get("type")
            ),
            created_at=(
                datetime.fromtimestamp(raw["created"])
                if raw.get("created") else None
            ),
            metadata=raw.get("metadata", {}),
        )
