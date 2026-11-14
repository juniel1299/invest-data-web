# 배포하기 (무료)

다른 사람이 인터넷에서 `https://...` 주소로 들어올 수 있게 올리는 방법입니다.
서버 한 대에서 `docker-compose.prod.yml` 하나로 전부 띄웁니다.

```
브라우저 ──https──▶ Caddy ─┬─ /            Flutter 웹 (app/ 를 빌드한 파일)
                            └─ /api /admin  Django(gunicorn) ── PostgreSQL
                                             Celery worker·beat ── Redis
```

- 웹과 API가 같은 주소라서 CORS 설정이 필요 없습니다. Flutter 웹은 자기를 내려준 주소의 API를 씁니다.
- Celery가 정해진 시간마다 공시를 모으고 장 마감 이메일을 보내므로, 접속이 없으면 잠드는 무료 호스팅 대신 계속 켜져 있는 서버를 씁니다.

두 가지 중 하나를 고르세요.

| | 오라클 클라우드 무료 서버 | 내 PC + Tailscale Funnel |
| --- | --- | --- |
| 비용 | 무료 (Always Free) | 무료 |
| 켜져 있는 시간 | 24시간 | PC가 켜져 있을 때만 |
| 가입 | 카드 본인확인 필요 (무료 한도 안에서는 청구 없음) | 카드 불필요 |
| 주소 | `https://invest.<서버IP>.sslip.io` | `https://<PC이름>.<tailnet>.ts.net` |

---

## A. 오라클 클라우드 무료 서버

### 1. 서버 만들기
1. https://www.oracle.com/cloud/free/ 에서 가입합니다. 홈 지역은 나중에 못 바꾸니 서울(또는 춘천)을 고르세요.
2. 콘솔 → Compute → Instances → Create instance
   - Image: **Ubuntu 24.04**
   - Shape: **Ampere (VM.Standard.A1.Flex)**, OCPU 2, 메모리 12GB 정도 (무료 한도는 합쳐서 4 OCPU, 24GB)
   - SSH 키를 내려받아 둡니다.
   - "Out of capacity"가 뜨면 다른 가용 영역(AD)을 고르거나 시간을 두고 다시 시도합니다.
3. 인스턴스의 서브넷 → Security List → Ingress Rules에 TCP **80**, **443** (소스 `0.0.0.0/0`)을 추가합니다.

### 2. 서버 준비
```bash
ssh -i <내려받은키> ubuntu@<서버IP>

# 오라클 우분투 이미지는 방화벽이 80/443을 막아 둡니다
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save

# Docker 설치
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu && exit   # 다시 접속하면 sudo 없이 docker 사용
```

### 3. 코드 받고 설정
```bash
git clone https://github.com/juniel1299/invest-data-web.git
cd invest-data-web
cp .env.prod.example .env.prod
nano .env.prod
```
`<서버IP>`가 `1.2.3.4`라면 (점은 하이픈으로 바꿔도 됩니다):
```
SITE_ADDRESS=invest.1-2-3-4.sslip.io
APP_URL=https://invest.1-2-3-4.sslip.io
ALLOWED_HOSTS=invest.1-2-3-4.sslip.io
CSRF_TRUSTED_ORIGINS=https://invest.1-2-3-4.sslip.io
```
`SECRET_KEY`, `POSTGRES_PASSWORD`에는 각각 `python3 -c "import secrets; print(secrets.token_urlsafe(50))"` 결과를 넣고,
나머지(SEC_USER_AGENT, API 키, EMAIL_URL)는 지금 쓰는 `.env` 값을 그대로 옮기면 됩니다.

sslip.io는 가입 없이 `<IP>.sslip.io`를 그 IP로 연결해 주는 무료 주소입니다. Caddy가 https 인증서를 자동으로 받습니다.

### 4. 띄우고 데이터 넣기 → [공통: 띄우기](#공통-띄우기)

### 알아둘 점
- 무료 계정의 서버는 7일 동안 CPU·네트워크·메모리 사용이 아주 낮으면 오라클이 회수할 수 있습니다. 이 서비스는 Celery가 꾸준히 돌아서 보통 해당하지 않지만, 걱정되면 계정을 Pay As You Go로 올려도 무료 한도 안에서는 청구되지 않습니다.
- 저장소가 비공개라면 `git clone` 때 GitHub 아이디와 Personal Access Token을 입력합니다.

---

## B. 내 PC + Tailscale Funnel

PC에서 이미 Docker Compose가 돌고 있다면 가장 빠릅니다. PC가 꺼지면 사이트도 멈춥니다.

1. https://tailscale.com 에서 가입(구글 계정 가능)하고 PC에 Tailscale을 설치해 로그인합니다.
2. 개발용 compose가 떠 있으면 먼저 내립니다: `docker compose down`
3. 저장소 폴더에서 `cp .env.prod.example .env.prod` 후 값을 채웁니다. `<PC이름>.<tailnet>.ts.net` 주소는 Tailscale 관리 화면(Machines)에서 확인합니다.
   ```
   SITE_ADDRESS=:80
   APP_URL=https://<PC이름>.<tailnet>.ts.net
   ALLOWED_HOSTS=<PC이름>.<tailnet>.ts.net
   CSRF_TRUSTED_ORIGINS=https://<PC이름>.<tailnet>.ts.net
   ```
4. [공통: 띄우기](#공통-띄우기)를 따라 띄웁니다.
5. 인터넷에 공개합니다. 처음에는 관리 화면에서 Funnel을 켜라는 링크가 나오니 따라 누릅니다.
   ```bash
   tailscale funnel --bg 80
   ```
   끄려면 `tailscale funnel reset`

---

## 공통: 띄우기

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```
처음에는 Flutter 웹 빌드 때문에 10분쯤 걸립니다. 다 뜨면 데이터를 넣습니다.

```bash
# Windows PowerShell이면 dc 대신 docker compose -f docker-compose.prod.yml --env-file .env.prod 를 그대로 씁니다
alias dc='docker compose -f docker-compose.prod.yml --env-file .env.prod'
dc exec web python manage.py createsuperuser
dc exec web python manage.py sync_securities
dc exec web python manage.py seed_fomc
dc exec web python manage.py seed_people
dc exec web python manage.py update_market_data
dc exec web python manage.py update_trades
```

확인: `https://<주소>/api/health/` 가 `{"status": "ok"}`, `https://<주소>/` 에 로그인 화면.

이후 남들은 그 주소에서 회원가입해서 쓰면 됩니다.

### 자주 쓰는 명령
```bash
dc ps                      # 상태
dc logs -f web worker      # 로그
git pull && dc up -d --build   # 새 코드 반영
dc exec db pg_dump -U invest invest > backup.sql   # DB 백업
```

### 휴대폰 앱
배포 주소로 APK를 빌드하면 PC 와이파이 밖에서도 됩니다.
```bash
cd app && flutter build apk --dart-define=API_BASE_URL=https://<주소>
```
