"""
extractors/zendesk_extractor.py
Zendesk se tickets extract karta hai.
Week 1 - Day 3-5: Cursor-based incremental export
"""

from datetime import datetime
from typing import Generator, List, Optional

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config.models import ZendeskSettings, UnifiedTicket, TicketStatus
from utils.logger import get_logger

logger = get_logger("zendesk_extractor")


class ZendeskExtractor:
    """
    Zendesk API se tickets extract karta hai.
    - Basic Auth (email/token)
    - Cursor / incremental pagination
    """

    def __init__(self, settings: Optional[ZendeskSettings] = None):
        self.settings = settings or ZendeskSettings()
        self.base_url  = f"https://{self.settings.subdomain}.zendesk.com/api/v2"
        self.session   = requests.Session()
        self.session.auth = (
            f"{self.settings.email}/token",
            self.settings.api_token,
        )
        self.session.headers["Content-Type"] = "application/json"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(
            (requests.Timeout, requests.ConnectionError)
        ),
    )
    def _get(self, url: str, params: dict = None) -> dict:
        resp = self.session.get(url, params=params or {}, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def extract_tickets(
        self,
        batch_size: int = 100,
        updated_after: Optional[datetime] = None,
    ) -> Generator[List[UnifiedTicket], None, None]:
        """
        Incremental export agar updated_after diya ho,
        warna saare tickets page by page.
        """
        if updated_after:
            url    = f"{self.base_url}/incremental/tickets.json"
            params = {
                "start_time": int(updated_after.timestamp()),
                "per_page":   batch_size,
            }
        else:
            url    = f"{self.base_url}/tickets.json"
            params = {
                "per_page":   batch_size,
                "sort_by":    "created_at",
                "sort_order": "desc",
            }

        page = 1
        while True:
            logger.info(f"Zendesk tickets page {page}...")
            data = self._get(url, params)

            batch: List[UnifiedTicket] = []
            for raw in data.get("tickets", []):
                try:
                    batch.append(self._map_ticket(raw))
                except Exception as e:
                    logger.error(f"Ticket map nahi hua {raw.get('id')}: {e}")

            logger.info(f"Page {page}: {len(batch)} tickets mile")
            yield batch

            # Incremental cursor
            if updated_after:
                if data.get("end_of_stream", False):
                    break
                url    = data.get("next_page", "")
                params = {}
                if not url:
                    break
            else:
                next_page = data.get("next_page")
                if not next_page:
                    break
                url    = next_page
                params = {}

            page += 1

    def _map_ticket(self, raw: dict) -> UnifiedTicket:
        status_map = {
            "new":     TicketStatus.OPEN,
            "open":    TicketStatus.OPEN,
            "pending": TicketStatus.PENDING,
            "solved":  TicketStatus.SOLVED,
            "closed":  TicketStatus.CLOSED,
        }

        def parse_dt(v):
            if not v:
                return None
            return datetime.fromisoformat(v.replace("Z", "+00:00"))

        return UnifiedTicket(
            id=f"zd_{raw['id']}",
            source="zendesk",
            source_id=str(raw["id"]),
            subject=raw.get("subject", "No Subject"),
            description=raw.get("description"),
            status=status_map.get(raw.get("status", "open"), TicketStatus.OPEN),
            priority=raw.get("priority"),
            requester_email=(
                raw.get("via", {})
                   .get("source", {})
                   .get("from", {})
                   .get("address")
            ),
            tags=raw.get("tags", []),
            created_at=parse_dt(raw.get("created_at")),
            updated_at=parse_dt(raw.get("updated_at")),
            solved_at=parse_dt(raw.get("solved_at")),
            satisfaction_rating=str(
                raw.get("satisfaction_rating", {}).get("score", "")
            ),
        )
