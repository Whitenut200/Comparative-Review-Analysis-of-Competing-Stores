import re, time, unicodedata, pandas as pd
from pathlib import Path
from urllib.parse import quote
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

BASE_DIR = Path(r"C:\Users\output")  # 저장 폴더
BASE_DIR.mkdir(parents=True, exist_ok=True) # 상위 폴더 있으면 Go 없으면 만들기

# 유니코드 문자열 정규화
# 즉, 문자열의 유니코드 형태를 통일해서 정규식 필터링이 깨지지 않게 함
def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
   
    # 정규식으로 “허용하지 않는 문자” 제거
    # [^\w\s-]: 문자, 숫자, 밑줄(_), 공백, 하이픈(-) → "" (제거) , 앞뒤 공백제거, 소문자
    s = re.sub(r"[^\w\s-]", "", s).strip().lower() 

    # [-\s]: 공백, 하이픈(-) 연속적으로 나오면 → "_" (치) 
    # ex) "hello world test"   → "hello_world_test", "---awesome---shop"  → "_awesome_shop"
    s = re.sub(r"[-\s]+", "_", s) 

    # s로 반환, 없으면 place 기본값
    return s or "place" 

# 검색페이지 열고 entryIframe으로 전환
def ensure_entry_iframe():
    driver.switch_to.default_content()
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe#entryIframe")))


def open_entry_by_search(query_name: str):
    # 검색 결과에서 상호 클릭 → entryIframe 진입
    driver.switch_to.default_content()
    driver.get(f"https://map.naver.com/p/search/{quote(query_name)}")
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe#searchIframe")))
    time.sleep(0.6)

    # 결과 안정화용 스크롤
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight)"); time.sleep(0.6)

    # 클릭 가능한 상호 → 버튼 찾기
    cand = driver.find_elements(
        By.XPATH,
        "//a[@role='button' and contains(@class,'place_bluelink')]"
        " | //a[@role='button'][.//span[contains(@class,'TYaxT')]]"
    )

    # 위의 경로로 찾지 못했다면
    if not cand:
        spans = driver.find_elements(By.CSS_SELECTOR, "span.TYaxT") # span으로 찾기
        if spans:
            try:
                cand = [spans[0].find_element(By.XPATH, "./ancestor::a[@role='button'][1]")]
            except Exception:
                pass
    if not cand:
        raise RuntimeError("검색 결과에서 클릭 가능한 상호를 찾지 못했어요.")

    # 질의명과 유사한 것 우선
    qn = re.sub(r"\s+","", query_name).lower() # query_name에서 공백 모두 제거 & 소문자
    target = None

    # cand는 클릭 가능한 상호 목록
    # ex) 와우솥뚜껑, 와우펜션, 와우솥삼겹살 ..
    for a in cand:
        nm = ""
        try:
            nm = a.find_element(By.XPATH, ".//span[contains(@class,'TYaxT')][normalize-space()]").text.strip() # 상호명 텍스트
        except Exception:
            # 실패하면 그냥 버튼 전체 텍스트 가져오기
            nm = (a.text or "").strip()
        # 비교용
        # 하나가 다른 하나에 포함되어 있으면 유사한 이름으로 간주
        nm2 = re.sub(r"\s+","", nm).lower()
        if nm2 and (qn in nm2 or nm2 in qn):
            target = a; break
  
    # 일치하는게 없으면 첫 번재로 선택
    if target is None:
        target = cand[0]

    # 선택된 target 클릭 후 안으로 들어가기
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", target)
    driver.execute_script("arguments[0].click();", target)
    time.sleep(0.8)

    # entryIframe으로 전환
    ensure_entry_iframe()

def open_menu_tab():
    # 메뉴 탭 클릭(있으면 True)
    # 텍스트로 찾기
    for xp in ["//a[@role='tab' and contains(.,'메뉴')]", "//button[contains(.,'메뉴')]"]:
        try:
            el = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
            driver.execute_script("arguments[0].click();", el) # 메뉴 탭 클릭
            time.sleep(0.6)
            return True
        except TimeoutException:
            continue
    return False
  
# 메뉴 수집
def collect_menus(max_rounds=5):
    ensure_entry_iframe() # entryIframe으로 전환
    open_menu_tab() # 메뉴 탭 클릭

    # 로딩 유도
    for _ in range(3):
        driver.execute_script("window.scrollBy(0, 700);"); time.sleep(0.2) # 화면을 내리기 (로딩)

    item_xpath = "//section[.//h2[contains(.,'메뉴')]]//li | //li[contains(@class,'E2jtL')]"

    # '더보기' 여러 번
    prev = len(driver.find_elements(By.XPATH, item_xpath)) # 현재 로딩된 <li> 개수 저장

    # 최대 max_rounds번 시도 (무한 루프 방지)
    for _ in range(max_rounds):
        try:
          # 메뉴안에 있는 더보기 클릭
            more_btn = driver.find_element(
                By.XPATH,
                "//section[.//h2[contains(.,'메뉴')]]//button[contains(.,'더보기')]"
                " | //section[.//h2[contains(.,'메뉴')]]//a[contains(.,'더보기')]"
            )
        except Exception:
            more_btn = None
          
        # 버튼 자체가 없을 경우
        # 더이상 없으면 종료
        if not more_btn or not more_btn.is_displayed():
            break

        # 더보기 위치로 스크롤 이동
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", more_btn)
        # 더보기 클릭
        driver.execute_script("arguments[0].click();", more_btn)
        time.sleep(0.5)

        # 버튼은 있지만 개수가 늘어나지 않는 경우
        # <li> 개수 변화 없으면 종료
        cur = len(driver.find_elements(By.XPATH, item_xpath))
        if cur <= prev:
            break
        prev = cur

    # 파싱
    items = driver.find_elements(By.XPATH, item_xpath)
    out = []
    for li in items:
        name = ""
        price_text = ""
        price = None
        signature = False

        name_els = li.find_elements(By.XPATH, ".//span[contains(@class,'lPzHi')][normalize-space()]") or \
                   li.find_elements(By.XPATH, ".//div[contains(@class,'yQlqY')]//span[normalize-space()]")
        if name_els: name = name_els[0].text.strip()

        ems = li.find_elements(By.XPATH, ".//em")
        price_text = ems[0].text.strip() if ems and ems[0].text.strip() else li.text
        m = re.search(r'(\d[\d,]*)', price_text or '')
        price = int(m.group(1).replace(',', '')) if m else None

        if li.find_elements(By.XPATH, ".//*[contains(@class,'place_blind') and contains(.,'대표')]"):
            signature = True

        if name or price is not None:
            out.append({
                "menu_name": name,
                "price_text": price_text,
                "price": price,
                "signature": signature
            })
    return out

def crawl_menus_for_store(store_name: str):
    """가게명으로 검색→상세 진입→메뉴만 수집→CSV 저장"""
    open_entry_by_search(store_name)
    menus = collect_menus(max_rounds=6)

    # 파일 저장
    slug = slugify(store_name)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = BASE_DIR / f"{slug}_menus_{ts}.csv"
    pd.DataFrame(menus).to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"🍽️ {store_name} 메뉴 {len(menus)}개 수집 → {out_path}")
    # 앞에서처럼 프린트 미리보기
    for i, m in enumerate(menus[:8], 1):
        print(f"{i}. {m['menu_name']} | {m['price_text']} | 대표:{'Y' if m['signature'] else ''}")
    return menus

for n in names:
    try:
        crawl_menus_for_store(n)
        time.sleep(0.8)  # 너무 빠르면 실패하니 숨고르기
    except Exception as e:
        print("❌ 실패:", n, e)
