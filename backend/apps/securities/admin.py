from django.contrib import admin

from .models import Security


@admin.register(Security)
class SecurityAdmin(admin.ModelAdmin):
    list_display = ["ticker", "name", "name_ko", "exchange", "is_active", "updated_at"]
    list_filter = ["exchange", "is_active"]
    search_fields = ["ticker", "name", "name_ko"]
    list_editable = ["name_ko"]
