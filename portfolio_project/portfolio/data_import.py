import csv
import heapq
import os
from datetime import date, datetime
from typing import TypedDict

from django.conf import settings

from .models import HistoricalPrice, Stock


class HistoricalCsvRow(TypedDict):
    Date: date
    Company: str
    Open: float
    High: float
    Low: float
    Close: float
    Adj_Close: float
    Volume: int
    Dividends: float
    Stock_Splits: float


CSV_FILENAME = "nasdaq100_latest_raw_data.csv"
REQUIRED_COLUMNS = [
    "Date",
    "Company",
    "Open",
    "High",
    "Low",
    "Close",
    "Adj_Close",
    "Volume",
    "Dividends",
    "Stock_Splits",
]


def _is_blank(value: str | None) -> bool:
    return value is None or not value.strip()


def _parse_date(value: str | None) -> date | None:
    if _is_blank(value):
        return None

    assert value is not None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"

    try:
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        return None


def _parse_float(
    value: str | None,
    *,
    field_name: str,
    row_number: int,
    default: float | None = None,
) -> float | None:
    if _is_blank(value):
        return default

    assert value is not None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {field_name} value in row {row_number}.") from exc


def _parse_required_float(value: str | None, *, field_name: str, row_number: int) -> float:
    parsed = _parse_float(value, field_name=field_name, row_number=row_number)
    if parsed is None:
        raise ValueError(f"Missing {field_name} value in row {row_number}.")
    return parsed


def _parse_int(
    value: str | None,
    *,
    field_name: str,
    row_number: int,
    default: int | None = None,
) -> int | None:
    if _is_blank(value):
        return default

    assert value is not None
    try:
        return int(float(value))
    except ValueError as exc:
        raise ValueError(f"Invalid {field_name} value in row {row_number}.") from exc


def _clean_row(row: dict[str, str | None], row_number: int) -> HistoricalCsvRow | None:
    parsed_date = _parse_date(row.get("Date"))
    company_value = (row.get("Company") or "").strip().upper()
    adjusted_close_text = row.get("Adj_Close")

    # Match the previous behavior of dropping rows missing the chart-critical fields.
    if parsed_date is None or not company_value or _is_blank(adjusted_close_text):
        return None

    volume = _parse_int(row.get("Volume"), field_name="Volume", row_number=row_number, default=0)

    return {
        "Date": parsed_date,
        "Company": company_value,
        "Open": _parse_required_float(row.get("Open"), field_name="Open", row_number=row_number),
        "High": _parse_required_float(row.get("High"), field_name="High", row_number=row_number),
        "Low": _parse_required_float(row.get("Low"), field_name="Low", row_number=row_number),
        "Close": _parse_required_float(row.get("Close"), field_name="Close", row_number=row_number),
        "Adj_Close": _parse_required_float(
            adjusted_close_text,
            field_name="Adj_Close",
            row_number=row_number,
        ),
        "Volume": volume if volume is not None else 0,
        "Dividends": _parse_float(
            row.get("Dividends"),
            field_name="Dividends",
            row_number=row_number,
            default=0.0,
        )
        or 0.0,
        "Stock_Splits": _parse_float(
            row.get("Stock_Splits"),
            field_name="Stock_Splits",
            row_number=row_number,
            default=0.0,
        )
        or 0.0,
    }


def _collect_recent_rows(csv_path: str) -> tuple[list[str], dict[str, list[HistoricalCsvRow]]]:
    with open(csv_path, newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = reader.fieldnames

        if fieldnames is None:
            raise ValueError("CSV is missing a header row.")

        missing = [col for col in REQUIRED_COLUMNS if col not in fieldnames]
        if missing:
            raise ValueError(f"CSV is missing required columns: {missing}")

        unique_companies: list[str] = []
        seen_symbols: set[str] = set()
        company_heaps: dict[str, list[tuple[int, int, HistoricalCsvRow]]] = {}
        sequence = 0

        for row_number, row in enumerate(reader, start=2):
            cleaned_row = _clean_row(row, row_number)
            if cleaned_row is None:
                continue

            symbol = cleaned_row["Company"]
            if symbol not in seen_symbols:
                seen_symbols.add(symbol)
                unique_companies.append(symbol)

            # Keep only the newest 120 rows per company while scanning the CSV.
            heap = company_heaps.setdefault(symbol, [])
            item = (cleaned_row["Date"].toordinal(), sequence, cleaned_row)
            sequence += 1

            if len(heap) < 120:
                heapq.heappush(heap, item)
            else:
                heapq.heappushpop(heap, item)

    recent_rows = {
        symbol: [entry[2] for entry in sorted(heap)]
        for symbol, heap in company_heaps.items()
    }
    return unique_companies, recent_rows


def import_prices_from_csv() -> tuple[int, int]:
    """
    Import all unique stocks and recent historical prices for charting.
    """
    csv_path = os.path.join(settings.BASE_DIR, CSV_FILENAME)

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    unique_companies, recent_rows = _collect_recent_rows(csv_path)

    existing_symbols = set(
        Stock.objects.filter(symbol__in=unique_companies).values_list("symbol", flat=True)
    )

    new_stocks = [
        Stock(
            symbol=symbol,
            company_name=symbol,
            sector="",
            exchange="NASDAQ",
        )
        for symbol in unique_companies
        if symbol not in existing_symbols
    ]

    if new_stocks:
        Stock.objects.bulk_create(new_stocks, ignore_conflicts=True)

    stock_map = {
        stock.symbol: stock
        for stock in Stock.objects.filter(symbol__in=unique_companies)
    }

    created_prices = 0
    updated_prices = 0

    for symbol in unique_companies:
        stock = stock_map.get(symbol)
        if not stock:
            continue

        for row in recent_rows.get(symbol, []):
            _, created = HistoricalPrice.objects.update_or_create(
                stock=stock,
                date=row["Date"],
                defaults={
                    "open_price": row["Open"],
                    "high_price": row["High"],
                    "low_price": row["Low"],
                    "close_price": row["Close"],
                    "adjusted_close_price": row["Adj_Close"],
                    "volume": row["Volume"],
                    "dividends": row["Dividends"],
                    "stock_splits": row["Stock_Splits"],
                },
            )

            if created:
                created_prices += 1
            else:
                updated_prices += 1

    return len(new_stocks), created_prices + updated_prices
