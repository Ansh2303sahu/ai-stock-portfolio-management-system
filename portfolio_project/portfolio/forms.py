from typing import cast

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Sum

from .models import Transaction, SupportQuery, Stock


class TransactionForm(forms.ModelForm):
    """
    Validates BUY/SELL transactions.
    For SELL, ensures user can't sell more than owned.
    Portfolio must be provided by the view via: TransactionForm(..., portfolio=portfolio)
    """

    def __init__(self, *args, **kwargs):
        self.portfolio = kwargs.pop("portfolio", None)
        super().__init__(*args, **kwargs)

        stock_field = cast(forms.ModelChoiceField, self.fields["stock"])
        stock_field.queryset = Stock.objects.all().order_by("symbol")
        stock_field.empty_label = "Select a stock"

        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "form-control")

    class Meta:
        model = Transaction
        fields = [
            "stock",
            "transaction_type",
            "quantity",
            "price",
            "transaction_date",
        ]
        widgets = {
            "transaction_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned = super().clean()

        stock = cleaned.get("stock")
        ttype = cleaned.get("transaction_type")
        qty = cleaned.get("quantity")

        if not stock or not ttype or qty in (None, ""):
            return cleaned

        if qty <= 0:
            self.add_error("quantity", "Quantity must be greater than 0.")
            return cleaned

        portfolio = getattr(self.instance, "portfolio", None) or self.portfolio

        if not portfolio:
            return cleaned

        if ttype == "SELL":
            qs = Transaction.objects.filter(portfolio=portfolio, stock=stock)

            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            buy = qs.filter(transaction_type="BUY").aggregate(s=Sum("quantity"))["s"] or 0
            sell = qs.filter(transaction_type="SELL").aggregate(s=Sum("quantity"))["s"] or 0
            owned = buy - sell

            if qty > owned:
                raise ValidationError(
                    {"quantity": f"You cannot sell {qty} shares. You only own {owned}."}
                )

        return cleaned


class SupportQueryForm(forms.ModelForm):
    class Meta:
        model = SupportQuery
        fields = ["subject", "message"]
        widgets = {
            "subject": forms.TextInput(attrs={"class": "form-control"}),
            "message": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }