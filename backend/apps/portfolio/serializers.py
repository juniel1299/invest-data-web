from rest_framework import serializers

from apps.securities.models import Security

from .calculations import OversellError, build_positions
from .models import Account, Transaction


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ["id", "name", "broker", "created_at"]
        read_only_fields = ["id", "created_at"]


class TransactionSerializer(serializers.ModelSerializer):
    ticker = serializers.SlugRelatedField(
        source="security", slug_field="ticker", queryset=Security.objects.filter(is_active=True)
    )
    name = serializers.CharField(source="security.name", read_only=True)
    name_ko = serializers.CharField(source="security.name_ko", read_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id",
            "account",
            "ticker",
            "name",
            "name_ko",
            "side",
            "quantity",
            "price",
            "fx_rate",
            "traded_at",
            "memo",
        ]
        read_only_fields = ["id"]

    def to_internal_value(self, data):
        if isinstance(data.get("ticker"), str):
            data = {**data, "ticker": data["ticker"].strip().upper()}
        return super().to_internal_value(data)

    def validate_account(self, account):
        if account and account.user_id != self.context["request"].user.id:
            raise serializers.ValidationError("내 계좌가 아닙니다.")
        return account

    def validate(self, attrs):
        for f in ("quantity", "price"):
            if f in attrs and attrs[f] <= 0:
                raise serializers.ValidationError({f: "0보다 커야 합니다."})
        if attrs.get("fx_rate") is not None and attrs["fx_rate"] <= 0:
            raise serializers.ValidationError({"fx_rate": "0보다 커야 합니다."})
        self._check_no_oversell(attrs)
        return attrs

    def _check_no_oversell(self, attrs):
        """이 거래를 반영해도 어느 시점에서든 보유 수량이 음수가 되지 않는지 확인한다."""
        user = self.context["request"].user
        candidate = Transaction(**{**self._current_values(), **attrs, "user": user})
        candidate.id = self.instance.id if self.instance else None
        securities = {candidate.security_id}
        if self.instance:
            securities.add(self.instance.security_id)
        others = Transaction.objects.filter(user=user, security_id__in=securities).select_related("security")
        if self.instance:
            others = others.exclude(pk=self.instance.pk)
        try:
            build_positions([*others, candidate], fx_lookup=lambda _: None)
        except OversellError as exc:
            raise serializers.ValidationError({"quantity": str(exc)})

    def _current_values(self):
        if not self.instance:
            return {}
        fields = ["account", "security", "side", "quantity", "price", "fx_rate", "traded_at", "memo"]
        return {f: getattr(self.instance, f) for f in fields}
