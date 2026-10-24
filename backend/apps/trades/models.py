from django.conf import settings
from django.db import models

from apps.securities.models import Security


class Person(models.Model):
    """추적 대상 인물. 관리자 화면에서 추가·비활성화하고 수집 출처를 정한다."""

    class Kind(models.TextChoices):
        PRESIDENT = "PRESIDENT", "대통령"
        HOUSE = "HOUSE", "하원의원"
        SENATE = "SENATE", "상원의원"
        INVESTOR = "INVESTOR", "투자자"
        PRINCIPLE = "PRINCIPLE", "투자 원칙"

    slug = models.SlugField(unique=True)
    name = models.CharField("영문 이름", max_length=100)
    name_ko = models.CharField("한글 이름", max_length=100)
    kind = models.CharField("구분", max_length=10, choices=Kind.choices)
    title = models.CharField("소속·설명", max_length=200, blank=True)
    note = models.CharField("주의 문구", max_length=200, blank=True, help_text="예: 2025년 펀드 등록 해지, 최신 공시 없음")
    is_current_president = models.BooleanField(
        "현직 대통령", default=False, help_text="켜면 화면에 '현직 대통령'으로 표시됩니다. 한 명만 켜세요."
    )
    active = models.BooleanField("수집·표시", default=True)
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=100)

    # 수집 출처 설정
    cik = models.PositiveIntegerField("SEC CIK", null=True, blank=True, help_text="13F·Form 4를 내는 펀드나 본인의 CIK")
    track_13f = models.BooleanField("13F 분기 보유", default=False)
    track_form4 = models.BooleanField("Form 4 (본인이 10% 대주주·임원으로 낸 매매)", default=False)
    track_ark = models.BooleanField("ARK ETF 일간 보유 변화", default=False)
    house_last_name = models.CharField("하원 공시 성", max_length=50, blank=True)
    house_state = models.CharField("하원 주 (예: CA)", max_length=2, blank=True)
    senate_first_name = models.CharField("상원 공시 이름", max_length=50, blank=True)
    senate_last_name = models.CharField("상원 공시 성", max_length=50, blank=True)
    source_url = models.URLField("공시 원문 위치", blank=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = verbose_name_plural = "인물"

    def __str__(self):
        return f"{self.name_ko} ({self.get_kind_display()})"


class Source(models.TextChoices):
    F13 = "13F", "13F 분기 보유"
    ARK = "ARK", "ARK 일간 보유"
    FORM4 = "FORM4", "Form 4"
    HOUSE = "HOUSE", "하원 거래 신고"
    SENATE = "SENATE", "상원 거래 신고"
    OGE = "OGE", "OGE 278-T"
    MANUAL = "MANUAL", "직접 입력"


class Filing(models.Model):
    """공시 한 건. 같은 공시를 두 번 처리하지 않도록 (출처, 키)로 구분한다."""

    person = models.ForeignKey(Person, on_delete=models.CASCADE, null=True, blank=True, related_name="filings")
    security = models.ForeignKey(
        Security, on_delete=models.CASCADE, null=True, blank=True, related_name="insider_filings",
        help_text="내부자 Form 4는 발행 회사",
    )
    source = models.CharField(max_length=8, choices=Source.choices)
    key = models.CharField("공시 번호", max_length=100)
    filed_at = models.DateField("공시일")
    period_end = models.DateField("기준일", null=True, blank=True)
    url = models.URLField("원문", max_length=500, blank=True)
    parsed = models.BooleanField("내용 읽음", default=True, help_text="스캔본처럼 읽지 못한 공시는 원문 링크만 보여준다")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["source", "key"], name="uniq_filing")]
        ordering = ["-filed_at", "-id"]
        verbose_name = verbose_name_plural = "공시"

    def __str__(self):
        return f"{self.get_source_display()} {self.key}"


class DisclosedTrade(models.Model):
    """공시된 거래 한 건. 13F·ARK는 보유 변화에서 추정한 매매다."""

    class Action(models.TextChoices):
        BUY = "BUY", "매수"
        SELL = "SELL", "매도"
        PARTIAL_SELL = "PARTIAL_SELL", "일부 매도"
        EXCHANGE = "EXCHANGE", "교환"
        NEW = "NEW", "신규 편입"
        ADD = "ADD", "비중 확대"
        REDUCE = "REDUCE", "비중 축소"
        EXIT = "EXIT", "전량 매도"

    BUY_SIDE = {"BUY", "NEW", "ADD"}

    filing = models.ForeignKey(Filing, on_delete=models.CASCADE, related_name="trades")
    row = models.PositiveIntegerField(default=0)
    person = models.ForeignKey(Person, on_delete=models.CASCADE, null=True, blank=True, related_name="trades")
    security = models.ForeignKey(Security, on_delete=models.SET_NULL, null=True, blank=True, related_name="disclosed_trades")
    ticker = models.CharField("티커(공시 표기)", max_length=16, blank=True)
    asset_name = models.CharField("자산명", max_length=255, blank=True)
    action = models.CharField("구분", max_length=12, choices=Action.choices)
    traded_at = models.DateField("거래일", null=True, blank=True)
    filed_at = models.DateField("공시일")
    amount_min = models.DecimalField("금액 하한(USD)", max_digits=16, decimal_places=2, null=True, blank=True)
    amount_max = models.DecimalField("금액 상한(USD)", max_digits=16, decimal_places=2, null=True, blank=True)
    shares = models.DecimalField("주식 수", max_digits=20, decimal_places=4, null=True, blank=True)
    price = models.DecimalField("단가(USD)", max_digits=16, decimal_places=4, null=True, blank=True)
    owner = models.CharField("명의", max_length=20, blank=True, help_text="본인, 배우자, 공동, 자녀")
    actor_name = models.CharField("거래자(내부자)", max_length=150, blank=True)
    actor_title = models.CharField("직책(내부자)", max_length=150, blank=True)
    detail = models.CharField("비고", max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["filing", "row"], name="uniq_trade_row")]
        ordering = ["-filed_at", "-traded_at", "-id"]
        verbose_name = verbose_name_plural = "공시 거래"

    def __str__(self):
        who = self.person.name_ko if self.person else self.actor_name
        return f"{self.filed_at} {who} {self.get_action_display()} {self.ticker or self.asset_name}"

    @property
    def is_buy(self):
        return self.action in self.BUY_SIDE

    @property
    def value_usd(self):
        if self.shares is not None and self.price is not None:
            return self.shares * self.price
        return None


class HoldingSnapshot(models.Model):
    """13F 분기 말·ARK 일간 보유. 직전 기록과 비교해 매매를 추정한다."""

    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="holdings")
    source = models.CharField(max_length=8, choices=Source.choices)
    fund = models.CharField(max_length=10, blank=True, help_text="ARK ETF 코드")
    as_of = models.DateField("기준일")
    key = models.CharField(max_length=20, help_text="CUSIP 또는 티커")
    cusip = models.CharField(max_length=9, blank=True)
    ticker = models.CharField(max_length=16, blank=True)
    security = models.ForeignKey(Security, on_delete=models.SET_NULL, null=True, blank=True, related_name="famous_holders")
    name = models.CharField(max_length=255)
    shares = models.DecimalField(max_digits=20, decimal_places=4)
    value_usd = models.DecimalField(max_digits=20, decimal_places=2, null=True)
    filing = models.ForeignKey(Filing, on_delete=models.CASCADE, null=True, blank=True, related_name="holdings")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["person", "source", "fund", "as_of", "key"], name="uniq_holding")
        ]
        ordering = ["-as_of", "-value_usd"]
        verbose_name = verbose_name_plural = "보유 기록"


class CusipMap(models.Model):
    """13F에는 티커가 없어 CUSIP을 티커로 바꿔 둔다 (OpenFIGI, 무료)."""

    cusip = models.CharField(max_length=9, primary_key=True)
    ticker = models.CharField(max_length=16, blank=True, help_text="비어 있으면 찾지 못한 CUSIP")
    updated_at = models.DateTimeField(auto_now=True)


class Follow(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="follows")
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="followers")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "person"], name="uniq_follow")]


class Notification(models.Model):
    class Reason(models.TextChoices):
        FOLLOW = "FOLLOW", "팔로우한 인물"
        OVERLAP = "OVERLAP", "내 종목 거래"
        INSIDER = "INSIDER", "내부자 대량 매매"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    trade = models.ForeignKey(DisclosedTrade, on_delete=models.CASCADE, related_name="notifications")
    reason = models.CharField(max_length=8, choices=Reason.choices)
    title = models.CharField(max_length=200)
    body = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    pushed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "trade"], name="uniq_notification")]
        ordering = ["-created_at", "-id"]
