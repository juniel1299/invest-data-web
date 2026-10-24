from django.core.management.base import BaseCommand

from apps.trades.models import Person

K = Person.Kind

# 기획서의 1차 명단. 이미 있는 인물은 건드리지 않으므로 관리자 화면에서 고친 값이 유지된다.
# CIK는 SEC EDGAR 회사 검색(https://www.sec.gov/edgar/search/)에서 확인할 수 있다.
PEOPLE = [
    dict(slug="trump", name="Donald J. Trump", name_ko="도널드 트럼프", kind=K.PRESIDENT, title="미국 대통령",
         is_current_president=True, sort_order=1,
         note="대통령 거래 보고(OGE 278-T)는 PDF로만 나와 관리자 화면에서 입력합니다.",
         source_url="https://extapps2.oge.gov/201/Presiden.nsf/PAS+Index?OpenView"),
    dict(slug="pelosi", name="Nancy Pelosi", name_ko="낸시 펠로시", kind=K.HOUSE, title="하원 (민주, 캘리포니아)",
         house_last_name="Pelosi", house_state="CA", sort_order=10, note="남편 폴 펠로시 명의 거래 포함"),
    dict(slug="gottheimer", name="Josh Gottheimer", name_ko="조시 고트하이머", kind=K.HOUSE, title="하원 (민주, 뉴저지)",
         house_last_name="Gottheimer", house_state="NJ", sort_order=11),
    dict(slug="khanna", name="Ro Khanna", name_ko="로 칸나", kind=K.HOUSE, title="하원 (민주, 캘리포니아)",
         house_last_name="Khanna", house_state="CA", sort_order=12),
    dict(slug="mccaul", name="Michael McCaul", name_ko="마이클 맥콜", kind=K.HOUSE, title="하원 (공화, 텍사스)",
         house_last_name="McCaul", house_state="TX", sort_order=13),
    dict(slug="bresnahan", name="Rob Bresnahan", name_ko="롭 브레스내한", kind=K.HOUSE, title="하원 (공화, 펜실베이니아)",
         house_last_name="Bresnahan", house_state="PA", sort_order=14),
    dict(slug="tuberville", name="Tommy Tuberville", name_ko="토미 터버빌", kind=K.SENATE, title="상원 (공화, 앨라배마)",
         senate_first_name="Tommy", senate_last_name="Tuberville", sort_order=20),
    dict(slug="mullin", name="Markwayne Mullin", name_ko="마크웨인 멀린", kind=K.SENATE, title="상원 (공화, 오클라호마)",
         senate_first_name="Markwayne", senate_last_name="Mullin", sort_order=21),
    dict(slug="buffett", name="Warren Buffett", name_ko="워런 버핏", kind=K.INVESTOR, title="버크셔 해서웨이",
         cik=1067983, track_13f=True, track_form4=True, sort_order=30),
    dict(slug="cathie-wood", name="Cathie Wood", name_ko="캐시 우드", kind=K.INVESTOR, title="ARK Invest (ETF 일간 보유 변화)",
         cik=1697748, track_ark=True, sort_order=31),
    dict(slug="dalio", name="Ray Dalio", name_ko="레이 달리오", kind=K.INVESTOR, title="브리지워터 어소시에이츠",
         cik=1350694, track_13f=True, sort_order=32, note="달리오는 경영에서 물러나 펀드 기준으로 표시"),
    dict(slug="soros", name="George Soros", name_ko="조지 소로스", kind=K.INVESTOR, title="소로스 펀드 매니지먼트",
         cik=1029160, track_13f=True, sort_order=33, note="현재 운용은 아들 알렉스 소로스"),
    dict(slug="ackman", name="Bill Ackman", name_ko="빌 애크먼", kind=K.INVESTOR, title="퍼싱 스퀘어",
         cik=1336528, track_13f=True, track_form4=True, sort_order=34),
    dict(slug="icahn", name="Carl Icahn", name_ko="칼 아이칸", kind=K.INVESTOR, title="아이칸 엔터프라이즈",
         cik=921669, track_13f=True, track_form4=True, sort_order=35),
    dict(slug="druckenmiller", name="Stanley Druckenmiller", name_ko="스탠리 드러켄밀러", kind=K.INVESTOR,
         title="듀케인 패밀리 오피스", cik=1536411, track_13f=True, sort_order=36),
    dict(slug="tepper", name="David Tepper", name_ko="데이비드 테퍼", kind=K.INVESTOR, title="아팔루사",
         cik=1656456, track_13f=True, sort_order=37),
    dict(slug="klarman", name="Seth Klarman", name_ko="세스 클라만", kind=K.INVESTOR, title="바우포스트 그룹",
         cik=1061768, track_13f=True, sort_order=38),
    dict(slug="marks", name="Howard Marks", name_ko="하워드 막스", kind=K.INVESTOR, title="오크트리 캐피털",
         cik=949509, track_13f=True, sort_order=39),
    dict(slug="burry", name="Michael Burry", name_ko="마이클 버리", kind=K.INVESTOR, title="사이온 애셋 매니지먼트",
         cik=1649339, track_13f=True, sort_order=40, note="2025년 11월 펀드 등록 해지, 이후 최신 공시 없음"),
    dict(slug="lynch", name="Peter Lynch", name_ko="피터 린치", kind=K.PRINCIPLE, title="PEG 비율로 성장주 점검",
         sort_order=50, note="1990년 은퇴, 매매 공시 없음"),
    dict(slug="graham", name="Benjamin Graham", name_ko="벤저민 그레이엄", kind=K.PRINCIPLE, title="PER·PBR·그레이엄 넘버로 가치주 점검",
         sort_order=51, note="매매 공시 없음"),
    dict(slug="bogle", name="John Bogle", name_ko="존 보글", kind=K.PRINCIPLE, title="내 수익률과 S&P 500 비교",
         sort_order=52, note="매매 공시 없음"),
]


class Command(BaseCommand):
    help = "추적 인물 기본 명단을 넣습니다. 이미 있는 인물은 그대로 둡니다."

    def handle(self, *args, **options):
        created = 0
        for p in PEOPLE:
            p = dict(p)
            _, new = Person.objects.get_or_create(slug=p.pop("slug"), defaults=p)
            created += new
        self.stdout.write(self.style.SUCCESS(f"인물 {created}명 추가 (전체 {Person.objects.count()}명)"))
