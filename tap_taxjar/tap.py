"""TaxJar tap class."""

from __future__ import annotations

from singer_sdk import Tap
from singer_sdk import typing as th

from tap_taxjar import streams


class TapTaxJar(Tap):
    """TaxJar tap class."""

    name = "tap-taxjar"

    config_jsonschema = th.PropertiesList(
        th.Property(
            "api_key",
            th.StringType(nullable=False),
            required=True,
            secret=True,
            title="API Key",
            description="The TaxJar API key",
        ),
        th.Property(
            "days_back",
            th.IntegerType(nullable=False),
            default=21,
            title="Days Back",
            description="How many days back to pull transactions from",
        ),
    ).to_dict()

    def discover_streams(self) -> list[streams.TaxJarStream]:
        """Return a list of discovered streams.

        Returns:
            A list of discovered streams.
        """
        return [
            streams.TransactionsStream(self),
        ]


if __name__ == "__main__":
    TapTaxJar.cli()
