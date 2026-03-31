from django.contrib import admin
from .models import Stock, HistoricalPrice, Portfolio, Transaction
from .models import SupportQuery

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ("symbol",)
    search_fields = ("symbol",)


@admin.register(HistoricalPrice)
class HistoricalPriceAdmin(admin.ModelAdmin):
    list_display = (
        "stock",
        "date",
        "close_price",
        "adjusted_close_price",
        "volume",
    )
    list_filter = ("stock", "date")
    search_fields = ("stock__symbol",)


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "portfolio",
        "stock",
        "transaction_type",
        "quantity",
        "price",
        "transaction_date",
    )
    list_filter = ("transaction_type", "portfolio")


@admin.register(SupportQuery)
class SupportQueryAdmin(admin.ModelAdmin):
    list_display = ("user", "subject", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("user__username", "subject", "message")
