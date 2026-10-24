from django.contrib import admin

from .models import Account, Transaction


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ["name", "broker", "user", "created_at"]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["traded_at", "user", "security", "side", "quantity", "price", "fx_rate"]
    list_filter = ["side", "traded_at"]
    search_fields = ["security__ticker", "user__email"]
    raw_id_fields = ["security"]
