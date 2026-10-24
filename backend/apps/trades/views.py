from datetime import date, timedelta

from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.market.views import user_securities
from apps.portfolio.models import Transaction
from apps.portfolio.summary import build_summary

from . import principles
from .models import DisclosedTrade, Follow, HoldingSnapshot, Notification, Person, Source

FEED_LIMIT = 100


def _f(v, places=2):
    return None if v is None else round(float(v), places)


def person_brief(p):
    return {"slug": p.slug, "name": p.name, "name_ko": p.name_ko, "kind": p.kind, "kind_label": p.get_kind_display()}


def trade_json(t, mine=frozenset()):
    sec = t.security
    return {
        "id": t.id,
        "person": person_brief(t.person) if t.person else None,
        "actor_name": t.actor_name,
        "actor_title": t.actor_title,
        "ticker": sec.ticker if sec else t.ticker,
        "name": (sec.name_ko or sec.name) if sec else t.asset_name,
        "has_security": sec is not None,
        "action": t.action,
        "action_label": t.get_action_display(),
        "is_buy": t.is_buy,
        "traded_at": t.traded_at.isoformat() if t.traded_at else None,
        "filed_at": t.filed_at.isoformat(),
        "delay_days": (t.filed_at - t.traded_at).days if t.traded_at else None,
        "amount_min": _f(t.amount_min, 0),
        "amount_max": _f(t.amount_max, 0),
        "shares": _f(t.shares, 0),
        "price": _f(t.price),
        "value_usd": _f(t.value_usd, 0),
        "owner": t.owner,
        "detail": t.detail,
        "source": t.filing.source,
        "source_label": t.filing.get_source_display(),
        "url": t.filing.url,
        "overlap": t.security_id in mine,
    }


def _my_security_ids(user):
    return frozenset(user_securities(user).values_list("id", flat=True))


def _trades():
    return DisclosedTrade.objects.select_related("person", "security", "filing")


@api_view(["GET"])
def people(request):
    since = date.today() - timedelta(days=90)
    qs = Person.objects.filter(active=True).annotate(
        last_filed_at=Max("filings__filed_at"),
        recent_trades=Count("trades", filter=Q(trades__filed_at__gte=since), distinct=True),
    )
    if request.query_params.get("kind"):
        qs = qs.filter(kind=request.query_params["kind"])
    following = set(Follow.objects.filter(user=request.user).values_list("person_id", flat=True))
    return Response(
        [
            {
                **person_brief(p),
                "title": p.title,
                "note": p.note,
                "is_current_president": p.is_current_president,
                "is_following": p.id in following,
                "last_filed_at": p.last_filed_at.isoformat() if p.last_filed_at else None,
                "recent_trades": p.recent_trades,
            }
            for p in qs
        ]
    )


def latest_holdings(person):
    """가장 최근 보유 기록 (ARK는 ETF별 최신을 합친다)과 직전 대비 변화."""
    source = Source.ARK if person.track_ark else Source.F13
    snaps = HoldingSnapshot.objects.filter(person=person, source=source)
    funds = snaps.values("fund").annotate(d=Max("as_of"))
    merged, prev_shares, as_of = {}, {}, None
    for f in funds:
        cur = snaps.filter(fund=f["fund"], as_of=f["d"]).select_related("security")
        prev_d = snaps.filter(fund=f["fund"], as_of__lt=f["d"]).aggregate(d=Max("as_of"))["d"]
        prev = {h.key: h.shares for h in snaps.filter(fund=f["fund"], as_of=prev_d)} if prev_d else None
        as_of = max(filter(None, [as_of, f["d"]]))
        for h in cur:
            key = h.ticker or h.key
            row = merged.setdefault(key, {"ticker": h.ticker, "name": h.name, "security": h.security, "shares": 0, "value": 0, "prev": 0, "has_prev": prev is not None})
            row["shares"] += h.shares
            row["value"] += h.value_usd or 0
            if prev is not None:
                row["prev"] += prev.get(h.key, 0)
    total = sum(r["value"] for r in merged.values()) or 1
    rows = []
    for r in sorted(merged.values(), key=lambda r: r["value"], reverse=True):
        change = None
        if r["has_prev"]:
            change = "NEW" if not r["prev"] else _f((r["shares"] - r["prev"]) / r["prev"] * 100, 1)
        sec = r["security"]
        rows.append(
            {
                "ticker": sec.ticker if sec else r["ticker"],
                "name": (sec.name_ko or sec.name) if sec else r["name"],
                "has_security": sec is not None,
                "shares": _f(r["shares"], 0),
                "value_usd": _f(r["value"], 0),
                "weight": _f(r["value"] / total * 100),
                "change_pct": change,
            }
        )
    return as_of, rows


@api_view(["GET"])
def person_detail(request, slug):
    p = get_object_or_404(Person, slug=slug, active=True)
    mine = _my_security_ids(request.user)
    as_of, holdings = latest_holdings(p)
    my_tickers = set(user_securities(request.user).values_list("ticker", flat=True))
    overlap = [h for h in holdings if h["ticker"] in my_tickers]
    filings = p.filings.filter(parsed=False)[:10]
    return Response(
        {
            **person_brief(p),
            "title": p.title,
            "note": p.note,
            "is_current_president": p.is_current_president,
            "is_following": Follow.objects.filter(user=request.user, person=p).exists(),
            "source_url": p.source_url,
            "sources": [s for s, on in (("13F", p.track_13f), ("Form 4", p.track_form4), ("ARK", p.track_ark),
                                         ("하원 PTR", bool(p.house_last_name)), ("상원 eFD", bool(p.senate_last_name))) if on],
            "trades": [trade_json(t, mine) for t in _trades().filter(person=p)[:FEED_LIMIT]],
            "unparsed_filings": [{"filed_at": f.filed_at.isoformat(), "url": f.url, "source_label": f.get_source_display()} for f in filings],
            "holdings_as_of": as_of.isoformat() if as_of else None,
            "holdings": holdings[:30],
            "holdings_count": len(holdings),
            "overlap": {"tickers": [h["ticker"] for h in overlap], "weight": _f(sum(h["weight"] or 0 for h in overlap))},
        }
    )


@api_view(["POST", "DELETE"])
def follow(request, slug):
    p = get_object_or_404(Person, slug=slug, active=True)
    if request.method == "DELETE":
        Follow.objects.filter(user=request.user, person=p).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    Follow.objects.get_or_create(user=request.user, person=p)
    return Response({"slug": p.slug, "is_following": True}, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def feed(request):
    """scope: all(기본) | mine(내 보유·관심 종목) | following(팔로우한 인물). kind: 인물 구분 또는 INSIDER."""
    mine = _my_security_ids(request.user)
    qs = _trades().filter(Q(person__isnull=True) | Q(person__active=True))
    scope = request.query_params.get("scope", "all")
    kind = request.query_params.get("kind")
    if scope == "mine":
        qs = qs.filter(security_id__in=mine)
    elif scope == "following":
        qs = qs.filter(person__followers__user=request.user)
    if kind == "INSIDER":
        qs = qs.filter(person__isnull=True)
    elif kind:
        qs = qs.filter(person__kind=kind)
    elif scope != "mine":
        # 내부자 매매는 내 종목 화면에서만 기본으로 보여준다
        qs = qs.filter(person__isnull=False)
    return Response([trade_json(t, mine) for t in qs[:FEED_LIMIT]])


@api_view(["GET"])
def notifications(request):
    qs = Notification.objects.filter(user=request.user).select_related("trade__filing", "trade__person", "trade__security")
    return Response(
        {
            "unread": qs.filter(read_at__isnull=True).count(),
            "items": [
                {
                    "id": n.id,
                    "reason": n.reason,
                    "reason_label": n.get_reason_display(),
                    "title": n.title,
                    "body": n.body,
                    "created_at": n.created_at.isoformat(),
                    "read": n.read_at is not None,
                    "trade": trade_json(n.trade),
                }
                for n in qs[:50]
            ],
        }
    )


@api_view(["POST"])
def read_notifications(request):
    Notification.objects.filter(user=request.user, read_at__isnull=True).update(read_at=timezone.now())
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
def principles_view(request):
    txs = list(Transaction.objects.filter(user=request.user).select_related("security"))
    summary = build_summary(txs)
    held = {h["ticker"] for h in summary["holdings"]}
    secs = user_securities(request.user).select_related("fundamentals")
    return Response(
        {
            "bogle": principles.bogle(txs, summary),
            "securities": [
                {**principles.check_security(s), "held": s.ticker in held}
                for s in sorted(secs, key=lambda s: (s.ticker not in held, s.ticker))
            ],
        }
    )


def security_trades(security, user):
    """종목 상세의 '이 종목을 거래한 사람' 카드."""
    mine = _my_security_ids(user)
    holders = []
    for p in Person.objects.filter(active=True, holdings__security=security).distinct():
        as_of, rows = latest_holdings(p)
        row = next((r for r in rows if r["ticker"] == security.ticker), None)
        if row:
            holders.append({**person_brief(p), "as_of": as_of.isoformat(), "weight": row["weight"], "value_usd": row["value_usd"], "change_pct": row["change_pct"]})
    return {
        "trades": [trade_json(t, mine) for t in _trades().filter(security=security)[:10]],
        "holders": sorted(holders, key=lambda h: -(h["weight"] or 0)),
        "principles": principles.check_security(security),
    }
