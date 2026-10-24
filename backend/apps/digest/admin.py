from django.contrib import admin

from . import mailer
from .models import DailySummary


@admin.register(DailySummary)
class DailySummaryAdmin(admin.ModelAdmin):
    list_display = ["date", "user", "emailed_at", "created_at"]
    list_filter = ["date"]
    search_fields = ["user__email"]
    readonly_fields = ["user", "date", "data", "created_at", "emailed_at"]
    actions = ["resend"]

    @admin.action(description="선택한 요약 이메일 다시 보내기")
    def resend(self, request, queryset):
        for s in queryset.select_related("user"):
            mailer.send(s)
        self.message_user(request, f"{queryset.count()}건 보냈습니다.")
