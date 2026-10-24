from django.db.models import Case, IntegerField, Q, Value, When
from rest_framework import generics

from .models import Security
from .serializers import SecuritySerializer


class SecuritySearchView(generics.ListAPIView):
    """티커·영문명·한글명으로 종목 검색 (자동완성용, 최대 20개)."""

    serializer_class = SecuritySerializer

    def get_queryset(self):
        q = self.request.query_params.get("q", "").strip()
        if not q:
            return Security.objects.none()
        return (
            Security.objects.filter(is_active=True)
            .filter(Q(ticker__istartswith=q) | Q(name__icontains=q) | Q(name_ko__icontains=q))
            .annotate(
                rank=Case(
                    When(ticker__iexact=q, then=Value(0)),
                    When(ticker__istartswith=q, then=Value(1)),
                    default=Value(2),
                    output_field=IntegerField(),
                )
            )
            .order_by("rank", "ticker")[:20]
        )
