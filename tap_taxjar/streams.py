"""Stream type classes for tap-taxjar."""

from __future__ import annotations

import typing as t
from importlib import resources
from datetime import datetime, timedelta
import requests

from singer_sdk import typing as th

from tap_taxjar.client import TaxJarStream


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
        start_date = datetime.utcnow() - timedelta(days=days_back)
        end_date = datetime.utcnow()
        current_date = start_date

        while current_date <= end_date:
            current_date_str = current_date.strftime("%Y/%m/%d")
            self.logger.info(f"Fetching transactions from {current_date_str}")
            url = f"{self.url_base}/transactions/orders"
            params = {
                "transaction_date": current_date_str,
                "provider": "upsellery"
            }
            headers = self.authenticator.auth_headers
            resp = requests.get(url, headers=headers, params=params)
            orders = resp.json()["orders"]
            order_count = 0
            for order in orders:
                params = {'provider': 'upsellery'}
                detail_resp = requests.get(
                    f"{self.url_base}/transactions/orders/{order}", headers=headers, params=params
                )
                if detail_resp.ok:
                    order_count +=1
                    yield detail_resp.json().get("order", {})
            self.logger.info(f"Loaded {order_count} transactions from {current_date_str}")
            current_date += timedelta(days=1)
