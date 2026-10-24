from django.contrib import admin

from .models import CalendarEvent, Fundamentals, FxRate, MacroPoint, NewsItem, PriceDaily


@admin.register(PriceDaily)
class PriceDailyAdmin(admin.ModelAdmin):
    list_display = ["security", "date", "close"]
    list_filter = ["date"]
    search_fields = ["security__ticker"]
    raw_id_fields = ["security"]


@admin.register(FxRate)
class FxRateAdmin(admin.ModelAdmin):
    list_display = ["date", "usd_krw"]


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ["date", "kind", "security", "title"]
    list_filter = ["kind"]
    search_fields = ["security__ticker", "title"]
    raw_id_fields = ["security"]


@admin.register(NewsItem)
class NewsItemAdmin(admin.ModelAdmin):
    list_display = ["published_at", "security", "title", "source"]
    search_fields = ["security__ticker", "title"]
    raw_id_fields = ["security"]


@admin.register(Fundamentals)
class FundamentalsAdmin(admin.ModelAdmin):
    list_display = ["security", "as_of", "eps_ttm", "revenue_ttm", "updated_at"]
    raw_id_fields = ["security"]


@admin.register(MacroPoint)
class MacroPointAdmin(admin.ModelAdmin):
    list_display = ["series", "date", "value"]
    list_filter = ["series"]
