from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .analytics import build_dashboard_data
from .data_import import import_prices_from_csv
from .forms import SupportQueryForm, TransactionForm
from .gemini_llm import ask_gemini
from .models import Portfolio, SupportQuery, Transaction


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        Portfolio.objects.get_or_create(user=user, defaults={"name": "My Portfolio"})
        messages.success(request, "Account created successfully.")
        return redirect("dashboard")

    return render(request, "portfolio/register.html", {"form": form})


def user_login(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data["username"],
            password=form.cleaned_data["password"],
        )
        if user:
            login(request, user)
            Portfolio.objects.get_or_create(user=user, defaults={"name": "My Portfolio"})
            messages.success(request, "Logged in successfully.")
            return redirect("dashboard")

        messages.error(request, "Invalid username or password.")

    return render(request, "portfolio/login.html", {"form": form})


def user_logout(request):
    logout(request)
    return redirect("/login/")


@login_required(login_url="/login/")
def dashboard(request):
    portfolio = Portfolio.objects.filter(user=request.user).first()
    if not portfolio:
        portfolio = Portfolio.objects.create(user=request.user, name="My Portfolio")

    selected_stock_id = request.GET.get("stock_id")
    try:
        selected_stock_id = int(selected_stock_id) if selected_stock_id else None
    except ValueError:
        selected_stock_id = None

    context = build_dashboard_data(portfolio, selected_stock_id=selected_stock_id)
    return render(request, "portfolio/dashboard.html", context)


@login_required
def add_transaction(request):
    portfolio = Portfolio.objects.filter(user=request.user).first()
    if not portfolio:
        portfolio = Portfolio.objects.create(user=request.user, name="My Portfolio")

    if request.method == "POST":
        form = TransactionForm(request.POST, portfolio=portfolio)
        if form.is_valid():
            tx = form.save(commit=False)
            tx.portfolio = portfolio
            tx.save()
            messages.success(request, "Transaction added successfully.")
            return redirect("dashboard")
    else:
        form = TransactionForm(portfolio=portfolio)

    return render(request, "portfolio/transaction_form.html", {"form": form})


@login_required
def transaction_history(request):
    portfolio = get_object_or_404(Portfolio, user=request.user)

    txs = (
        Transaction.objects.filter(portfolio=portfolio)
        .select_related("stock")
        .order_by("-transaction_date", "-id")
    )

    return render(
        request,
        "portfolio/transaction_history.html",
        {"transactions": txs, "portfolio": portfolio},
    )


@login_required
def refresh_prices(request):
    if request.method != "POST":
        return redirect("dashboard")

    created, updated = import_prices_from_csv()
    messages.success(
        request,
        f"Market data refreshed. Created: {created}, Updated: {updated}",
    )
    return redirect("dashboard")


@login_required
def edit_transaction(request, pk):
    portfolio = get_object_or_404(Portfolio, user=request.user)
    tx = get_object_or_404(Transaction, pk=pk, portfolio=portfolio)

    if request.method == "POST":
        form = TransactionForm(request.POST, instance=tx, portfolio=portfolio)
        if form.is_valid():
            tx_obj = form.save(commit=False)
            tx_obj.portfolio = portfolio
            tx_obj.save()
            messages.success(request, "Transaction updated successfully.")
            return redirect("transaction_history")
    else:
        form = TransactionForm(instance=tx, portfolio=portfolio)

    return render(
        request,
        "portfolio/transaction_form.html",
        {"form": form, "is_edit": True},
    )


@login_required
def delete_transaction(request, pk):
    portfolio = get_object_or_404(Portfolio, user=request.user)
    tx = get_object_or_404(Transaction, pk=pk, portfolio=portfolio)

    if request.method == "POST":
        tx.delete()
        messages.success(request, "Transaction deleted successfully.")
        return redirect("transaction_history")

    return render(request, "portfolio/transaction_delete_confirm.html", {"tx": tx})


@login_required
def ai_assistant(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=400)

    user_msg = (request.POST.get("message") or "").strip()
    if not user_msg:
        return JsonResponse({"reply": "Please type a question."})

    portfolio = Portfolio.objects.filter(user=request.user).first()
    if not portfolio:
        portfolio = Portfolio.objects.create(user=request.user, name="My Portfolio")

    data = build_dashboard_data(portfolio)

    holdings = data.get("holdings", [])
    ai = data.get("ai", {})

    context_lines = [
        f"Total portfolio value: ₹ {data.get('total_value')}",
        f"Holdings count: {len(holdings)}",
    ]

    if holdings:
        context_lines.append("Holdings (top):")
        for h in holdings[:12]:
            context_lines.append(
                f"- {h['stock_symbol']} qty={h['quantity']} latest={h['latest_price']} value={h['value']}"
            )

    context_lines.append("AI indicators (selected chart stock):")
    context_lines.append(f"- Trend: {ai.get('trend')}")
    context_lines.append(f"- Signal: {ai.get('signal')}")
    context_lines.append(f"- Confidence: {ai.get('confidence')}")
    context_lines.append(f"- Risk: {ai.get('risk_level')} (vol={ai.get('volatility')}%)")
    context_lines.append(f"- RSI: {ai.get('rsi')} ({ai.get('rsi_state')})")
    context_lines.append(f"- Forecast: {ai.get('forecast_next')} ({ai.get('forecast_direction')})")
    context_lines.append(f"- Explanation: {ai.get('explanation')}")

    context_text = "\n".join(context_lines)

    try:
        reply = ask_gemini(user_msg, context_text=context_text)
    except Exception as e:
        reply = f"AI assistant error: {str(e)}"

    return JsonResponse({"reply": reply})


@login_required
def submit_query(request):
    form = SupportQueryForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        q = form.save(commit=False)
        q.user = request.user
        q.save()
        messages.success(request, "Your query has been sent to the admin.")
        return redirect("dashboard")

    return render(request, "portfolio/submit_query.html", {"form": form})


@login_required
def my_queries(request):
    queries = SupportQuery.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "portfolio/my_queries.html", {"queries": queries})