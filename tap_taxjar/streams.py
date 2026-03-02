"""Stream type classes for tap-taxjar."""

from __future__ import annotations

import time
import typing as t
from datetime import datetime, timedelta, timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from singer_sdk import typing as th

from tap_taxjar.client import TaxJarStream

REQUEST_TIMEOUT = 30
MAX_RETRIES = 5
RETRY_BACKOFF_FACTOR = 1
RETRY_STATUS_FORCELIST = (429, 500, 502, 503, 504)
DETAIL_REQUEST_DELAY = 0.05


def _build_session(auth_headers: dict) -> requests.Session:
    """Build a requests.Session with retry/backoff on transient failures."""
    session = requests.Session()
    session.headers.update(auth_headers)
    retry_strategy = Retry(
        total=MAX_RETRIES,
        backoff_factor=RETRY_BACKOFF_FACTOR,
        status_forcelist=RETRY_STATUS_FORCELIST,
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class TransactionsStream(TaxJarStream):
    """Stream for detailed transaction records."""

    name = "transactions"
    path = "/transactions"
    primary_keys: t.ClassVar[list[str]] = ["transaction_id"]
    replication_key = None
    schema = th.PropertiesList(
        th.Property("transaction_id", th.StringType),
        th.Property("transaction_date", th.StringType),
        th.Property("amount", th.StringType),
        th.Property("sales_tax", th.StringType),
        th.Property("from_country", th.StringType),
        th.Property("to_country", th.StringType),
        th.Property("user_id", th.IntegerType),
        th.Property("transaction_reference_id", th.StringType),
        th.Property("to_zip", th.StringType),
        th.Property("to_street", th.StringType),
        th.Property("to_state", th.StringType),
        th.Property("to_city", th.StringType),
        th.Property("shipping", th.StringType),
        th.Property("from_zip", th.StringType),
        th.Property("from_street", th.StringType),
        th.Property("from_state", th.StringType),
        th.Property("from_city", th.StringType),
        th.Property("exemption_type", th.StringType),
        th.Property("customer_id", th.StringType),
        th.Property("provider", th.StringType),
        th.Property("line_items", th.ArrayType(
            th.ObjectType(
                th.Property("unit_price", th.StringType),
                th.Property("sales_tax", th.StringType),
                th.Property("quantity", th.IntegerType),
                th.Property("product_tax_code", th.StringType),
                th.Property("product_identifier", th.StringType),
                th.Property("id", th.IntegerType),
                th.Property("discount", th.StringType),
                th.Property("description", th.StringType),
            )
        )),
    ).to_dict()

    def get_records(self, context: dict | None) -> t.Iterable[dict]:
        days_back = self.config.get("days_back", 21)
        start_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        end_date = datetime.now(timezone.utc)
        current_date = start_date

        session = _build_session(self.authenticator.auth_headers)

        while current_date <= end_date:
            current_date_str = current_date.strftime("%Y/%m/%d")
            self.logger.info(f"Fetching transactions from {current_date_str}")

            orders = self._fetch_order_ids(session, current_date_str)
            order_count = 0

            for order in orders:
                record = self._fetch_order_detail(session, order)
                if record is not None:
                    order_count += 1
                    yield record
                time.sleep(DETAIL_REQUEST_DELAY)

            self.logger.info(
                f"Loaded {order_count} transactions from {current_date_str}"
            )
            current_date += timedelta(days=1)

        session.close()

    def _fetch_order_ids(
        self, session: requests.Session, date_str: str
    ) -> list[str]:
        """Fetch order IDs for a given date with retry handling."""
        url = f"{self.url_base}/transactions/orders"
        params = {
            "transaction_date": date_str,
            "provider": "upsellery",
        }
        resp = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()["orders"]

    def _fetch_order_detail(
        self, session: requests.Session, order_id: str
    ) -> dict | None:
        """Fetch a single order's detail with retry handling."""
        url = f"{self.url_base}/transactions/orders/{order_id}"
        params = {"provider": "upsellery"}
        try:
            resp = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json().get("order", {})
        except requests.exceptions.RequestException:
            self.logger.warning(
                f"Failed to fetch detail for order {order_id} after retries, "
                "skipping."
            )
            return None
