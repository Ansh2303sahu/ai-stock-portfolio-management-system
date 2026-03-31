from django.db import models
from django.contrib.auth.models import User


class Stock(models.Model):
    symbol = models.CharField(max_length=10, unique=True)
    company_name = models.CharField(max_length=100, blank=True)
    sector = models.CharField(max_length=50, blank=True)
    exchange = models.CharField(max_length=50, default="NASDAQ")

    def __str__(self):
        if self.company_name and self.company_name != self.symbol:
            return f"{self.symbol} - {self.company_name}"
        return self.symbol


class HistoricalPrice(models.Model):
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE)
    date = models.DateField()

    open_price = models.FloatField()
    high_price = models.FloatField()
    low_price = models.FloatField()
    close_price = models.FloatField()
    adjusted_close_price = models.FloatField()

    volume = models.BigIntegerField()
    dividends = models.FloatField(default=0.0)
    stock_splits = models.FloatField(default=0.0)

    class Meta:
        unique_together = ("stock", "date")
        ordering = ["date"]

    def __str__(self):
        return f"{self.stock.symbol} - {self.date}"


class Portfolio(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.user.username})"


class Transaction(models.Model):
    BUY = "BUY"
    SELL = "SELL"

    TRANSACTION_TYPES = [
        (BUY, "Buy"),
        (SELL, "Sell"),
    ]

    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE)
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE)

    transaction_type = models.CharField(
        max_length=4,
        choices=TRANSACTION_TYPES
    )

    quantity = models.IntegerField()
    price = models.FloatField()
    transaction_date = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type} {self.stock.symbol} ({self.quantity})"


class SupportQuery(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("REPLIED", "Replied"),
        ("CLOSED", "Closed"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subject = models.CharField(max_length=200)
    message = models.TextField()

    admin_reply = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.subject}"