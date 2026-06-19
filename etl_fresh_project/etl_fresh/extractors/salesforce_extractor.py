"""
Week 1 - Day 3-5: OAuth2 + SOQL + nextRecordsUrl cursor
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

from config.models import SalesforceSettings, UnifiedCustomer
from utils.logger import get_logger

logger = get_logger("salesforce_extractor")


class SalesforceExtractor:
    

    def __init__(self, settings: Optional[SalesforceSettings] = None):
        self.settings = settings or SalesforceSettings()
        self.session = requests.Session()
        self._access_token: Optional[str] = None
        self._instance_url: Optional[str] = None

    def authenticate(self):
        """OAuth2 token lena Salesforce se."""
        payload = {
            "grant_type":    "password",
            "client_id":     self.settings.client_id,
            "client_secret": self.settings.client_secret,
            "username":      self.settings.username,
            "password":      self.settings.password + self.settings.security_token,
        }
        resp = requests.post(
            "https://login.salesforce.com/services/oauth2/token",
            data=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._instance_url = data["instance_url"]
        self.session.headers.update({
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type":  "application/json",
        })
        logger.info(f"Salesforce auth ho gaya: {self._instance_url}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(
            (requests.Timeout, requests.ConnectionError)
        ),
    )
    def _get(self, url: str, params: dict = None) -> dict:
        if not self._access_token:
            self.authenticate()

        resp = self.session.get(url, params=params or {}, timeout=30)

        # Token expire — dobara auth
        if resp.status_code == 401:
            logger.warning("Token expire ho gaya. Re-authenticating...")
            self.authenticate()
            resp = self.session.get(url, params=params or {}, timeout=30)

        resp.raise_for_status()
        return resp.json()

    def extract_accounts(
        self,
        batch_size: int = 200,
        modified_after: Optional[datetime] = None,
    ) -> Generator[List[UnifiedCustomer], None, None]:
        """SOQL + nextRecordsUrl se accounts fetch karo."""
        if not self._access_token:
            self.authenticate()

        where = ""
        if modified_after:
            ts = modified_after.strftime("%Y-%m-%dT%H:%M:%SZ")
            where = f"WHERE LastModifiedDate >= {ts}"

        soql = (
            f"SELECT Id, Name, BillingCountry, Phone, Website, "
            f"Industry, Type, CreatedDate, LastModifiedDate, "
            f"AnnualRevenue, NumberOfEmployees "
            f"FROM Account {where} "
            f"ORDER BY LastModifiedDate DESC "
            f"LIMIT {batch_size}"
        )

        url    = f"{self._instance_url}/services/data/v58.0/query"
        params = {"q": soql}
        page   = 1

        while True:
            logger.info(f"Salesforce accounts page {page}...")
            data = self._get(url, params)

            batch: List[UnifiedCustomer] = []
            for raw in data.get("records", []):
                try:
                    batch.append(self._map_account(raw))
                except Exception as e:
                    logger.error(f"Account map nahi hua {raw.get('Id')}: {e}")

            logger.info(f"Page {page}: {len(batch)} accounts mile")
            yield batch

            next_url = data.get("nextRecordsUrl")
            if not next_url:
                break

            url    = f"{self._instance_url}{next_url}"
            params = {}
            page  += 1

    def _map_account(self, raw: dict) -> UnifiedCustomer:
        def parse_dt(v):
            if not v:
                return None
            return datetime.fromisoformat(v.replace("Z", "+00:00"))

        return UnifiedCustomer(
            id=f"sf_{raw['Id']}",
            source="salesforce",
            source_id=raw["Id"],
            email=f"sf_{raw['Id']}@salesforce.placeholder",
            name=raw.get("Name", "Unknown"),
            phone=raw.get("Phone"),
            company=raw.get("Name"),
            country=raw.get("BillingCountry"),
            created_at=parse_dt(raw.get("CreatedDate")),
            updated_at=parse_dt(raw.get("LastModifiedDate")),
            metadata={
                "industry":       raw.get("Industry"),
                "type":           raw.get("Type"),
                "annual_revenue": raw.get("AnnualRevenue"),
                "employees":      raw.get("NumberOfEmployees"),
            },
        )
