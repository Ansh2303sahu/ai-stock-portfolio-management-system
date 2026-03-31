from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    # Transactions
    path("transactions/add/", views.add_transaction, name="add_transaction"),
    path("transactions/", views.transaction_history, name="transaction_history"),
    path("transactions/<int:pk>/edit/", views.edit_transaction, name="edit_transaction"),
    path("transactions/<int:pk>/delete/", views.delete_transaction, name="delete_transaction"),

    # Market data refresh
    path("refresh-prices/", views.refresh_prices, name="refresh_prices"),

    # AI Assistant
    path("assistant/", views.ai_assistant, name="ai_assistant"),

    # Auth
    path("login/", views.user_login, name="login"),
    path("logout/", views.user_logout, name="logout"),
    path("register/", views.register, name="register"),

    # Support
    path("support/new/", views.submit_query, name="submit_query"),
    path("support/my/", views.my_queries, name="my_queries"),
]