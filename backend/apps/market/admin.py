from django.contrib import admin

from .models import FxRate, PriceDaily


@admin.register(PriceDaily)
class PriceDailyAdmin(admin.ModelAdmin):
    list_display = ["security", "date", "close"]
    list_filter = ["date"]
    search_fields = ["security__ticker"]
    raw_id_fields = ["security"]


@admin.register(FxRate)
class FxRateAdmin(admin.ModelAdmin):
    list_display = ["date", "usd_krw"]
