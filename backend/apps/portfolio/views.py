from django.db import transaction as db_transaction
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.market.tasks import backfill_security_task

from apps.securities.models import Security

from .models import Account, Transaction, Watch
from .serializers import AccountSerializer, TransactionSerializer
from .summary import build_summary


class AccountViewSet(viewsets.ModelViewSet):
    serializer_class = AccountSerializer

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer

    def get_queryset(self):
        qs = Transaction.objects.filter(user=self.request.user).select_related("security")
        ticker = self.request.query_params.get("ticker")
        account = self.request.query_params.get("account")
        if ticker:
            qs = qs.filter(security__ticker=ticker.upper())
        if account:
            qs = qs.filter(account_id=account)
        return qs

    def perform_create(self, serializer):
        is_new_security = not Transaction.objects.filter(
            user=self.request.user, security=serializer.validated_data["security"]
        ).exists()
        obj = serializer.save(user=self.request.user)
        if is_new_security and not obj.security.prices.exists():
            db_transaction.on_commit(lambda: backfill_security_task.delay(obj.security_id))


@api_view(["GET"])
def summary(request):
    qs = Transaction.objects.filter(user=request.user).select_related("security")
    account = request.query_params.get("account")
    if account:
        qs = qs.filter(account_id=account)
    return Response(build_summary(list(qs)))


@api_view(["GET", "POST"])
def watches(request):
    """관심 종목 목록 / 추가 ({"ticker": "AAPL"})."""
    if request.method == "POST":
        ticker = str(request.data.get("ticker", "")).strip().upper()
        security = get_object_or_404(Security, ticker=ticker, is_active=True)
        _, created = Watch.objects.get_or_create(user=request.user, security=security)
        if created and not security.prices.exists():
            db_transaction.on_commit(lambda: backfill_security_task.delay(security.id))
        return Response({"ticker": ticker}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
    rows = Watch.objects.filter(user=request.user).select_related("security")
    return Response(
        [
            {"ticker": w.security.ticker, "name": w.security.name, "name_ko": w.security.name_ko}
            for w in rows
        ]
    )


@api_view(["DELETE"])
def unwatch(request, ticker):
    Watch.objects.filter(user=request.user, security__ticker=ticker.upper()).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
