from django.contrib import admin

from . import alerts
from .models import DisclosedTrade, Filing, Follow, HoldingSnapshot, Notification, Person, Source
from .services import resolve_security


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ["name_ko", "kind", "title", "is_current_president", "active", "track_13f", "track_form4", "track_ark", "sort_order"]
    list_filter = ["kind", "active"]
    list_editable = ["active", "sort_order"]
    search_fields = ["name", "name_ko"]
    fieldsets = [
        (None, {"fields": ["slug", "name", "name_ko", "kind", "title", "note", "is_current_president", "active", "sort_order"]}),
        ("수집 출처", {"fields": ["cik", "track_13f", "track_form4", "track_ark", "house_last_name", "house_state",
                              "senate_first_name", "senate_last_name", "source_url"]}),
    ]


class TradeInline(admin.TabularInline):
    model = DisclosedTrade
    fields = ["ticker", "asset_name", "action", "traded_at", "amount_min", "amount_max", "shares", "price", "owner", "detail"]
    extra = 3


@admin.register(Filing)
class FilingAdmin(admin.ModelAdmin):
    """대통령 278-T처럼 PDF로만 나오는 공시는 여기서 공시 한 건과 거래 줄을 함께 입력한다."""

    list_display = ["filed_at", "source", "person", "security", "key", "parsed"]
    list_filter = ["source", "parsed"]
    search_fields = ["key", "person__name_ko", "security__ticker"]
    inlines = [TradeInline]

    def get_changeform_initial_data(self, request):
        return {"source": Source.OGE, **super().get_changeform_initial_data(request)}

    def save_formset(self, request, form, formset, change):
        filing = form.instance
        trades = formset.save(commit=False)
        start = (filing.trades.order_by("-row").values_list("row", flat=True).first() or 0) + 1
        new = []
        for i, t in enumerate(trades):
            if t.pk is None:
                t.row = start + i
                new.append(t)
            t.person = filing.person
            t.filed_at = filing.filed_at
            t.ticker = t.ticker.upper()
            t.security = resolve_security(t.ticker)
            t.save()
        for obj in formset.deleted_objects:
            obj.delete()
        # 직접 입력한 최근 거래도 팔로워·보유자에게 알린다
        alerts.dispatch(new)


@admin.register(DisclosedTrade)
class DisclosedTradeAdmin(admin.ModelAdmin):
    list_display = ["filed_at", "traded_at", "person", "actor_name", "ticker", "action", "amount_min", "amount_max", "shares"]
    list_filter = ["action", "filing__source", "person"]
    search_fields = ["ticker", "asset_name", "actor_name"]
    raw_id_fields = ["filing", "security"]


admin.site.register(HoldingSnapshot)
admin.site.register(Follow)
admin.site.register(Notification)
