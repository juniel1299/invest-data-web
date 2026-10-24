"""OpenFIGI: CUSIP → 티커 (무료. 키 없이 분당 25회, 요청당 10개)."""

import time

from django.conf import settings

URL = "https://api.openfigi.com/v3/mapping"


def map_cusips(client, cusips, sleep=time.sleep):
    key = getattr(settings, "OPENFIGI_API_KEY", "")
    batch = 100 if key else 10
    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-OPENFIGI-APIKEY"] = key
    out = {}
    cusips = list(cusips)
    for i in range(0, len(cusips), batch):
        if i:
            sleep(0.3 if key else 2.5)
        chunk = cusips[i : i + batch]
        res = client.post(URL, headers=headers, json=[{"idType": "ID_CUSIP", "idValue": c} for c in chunk])
        res.raise_for_status()
        for cusip, result in zip(chunk, res.json()):
            data = result.get("data") or []
            us = [d for d in data if d.get("exchCode") == "US"] or data
            # OpenFIGI는 클래스 주식을 "BRK/B"처럼 적는다
            out[cusip] = (us[0].get("ticker") or "").replace("/", ".") if us else ""
    return out
