import os, re, csv, time, random, hashlib
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 설정
BASE_DIR = r"D:\crawl_result"
os.makedirs(BASE_DIR, exist_ok=True)

# 사람처럼 보이기 위한 랜덤 딜레이
def human_delay(min_sec=0.3, max_sec=0.8):
    time.sleep(random.uniform(min_sec, max_sec))

# 드라이버 설정 및 새 chrome 브라우저 실행
def make_driver():
    opts = webdriver.ChromeOptions() # 크롬 실행 옵션 생성
    opts.add_argument("--disable-gpu") # gpu 비활성화 → 서버 등에서 렌더링 이슈 방지 
    opts.add_argument("--no-sandbox") # 샌드박스 모드 비활성화 → 권한 문제 방지
    opts.add_argument("--start-maximized") # 브라우저 최대화 실행
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36") # User-Agent 설정 → 크롤링 차단 방지용
    
    return webdriver.Chrome(options=opts) # 위 설정으로 새 Chrome 브라우저 실행

# entryIframe로 전환
def ensure_entry_iframe(driver, wait):
    driver.switch_to.default_content()
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe#entryIframe")))

# 가게명 가져오기
def place_title(driver):
    return (driver.execute_script("""
      const og = document.querySelector('meta[property="og:title"]');
      return (og && og.content) ? og.content : document.title;
    """) or "").split(" :")[0].strip()

# 특정 가게 리뷰 사이트 안으로 들어가기
def open_entry_by_search(driver, wait, query_name):
    from urllib.parse import quote

    # 가게명 입력 → 네이버 리뷰 사이트 들어가기
    driver.switch_to.default_content()
    driver.get(f"https://map.naver.com/p/search/{quote(query_name)}")
    human_delay(1.0, 1.5)

    # entryIframe로 전환
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe#searchIframe")))
    human_delay(0.5, 0.9)

    # 페이지 스크롤
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
    human_delay(0.6, 1.0)

    # 가게이름 탐색
    cand = driver.find_elements(
        By.XPATH,
        "//a[@role='button' and contains(@class,'place_bluelink')]"
        " | //a[@role='button'][.//span[contains(@class,'TYaxT')]]"
    )
    if not cand:
        spans = driver.find_elements(By.CSS_SELECTOR, "span.TYaxT")
        if spans:
            try:
                cand = [spans[0].find_element(By.XPATH, "./ancestor::a[@role='button'][1]")]
            except:
                pass
    if not cand:
        raise RuntimeError("검색 결과 없음")

    target = cand[0] # 제일 상단의 가게이름 지정
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", target) # 선택된 가게 버튼이 화면 중앙에 위치
    human_delay(0.3, 0.6)
  
    driver.execute_script("arguments[0].click();", target) # 클릭
    human_delay(0.8, 1.2)

    # entryIframe 전환
    driver.switch_to.default_content()
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe#entryIframe")))

# 리뷰탭 클릭
def go_reviews_tab(driver, wait):
    ensure_entry_iframe(driver, wait)
    for xp in ["//a[@role='tab' and contains(.,'리뷰')]", "//button[contains(.,'리뷰')]"]:
        els = driver.find_elements(By.XPATH, xp)
        if els:
            driver.execute_script("arguments[0].click();", els[0])
            human_delay(0.5, 0.8)
            return

# "펼쳐서 더보기" 탭 클릭 (더보기 탭은 다른 탭!)
# 펼쳐서 더보기 생길때마다 클릭
def click_fold_expand_all(driver, wait, max_clicks=999, sleep_range=(0.12, 0.25)):
    ensure_entry_iframe(driver, wait) # 전환
    clicked = 0 # 몇번 눌렀는지 카운트
  
    for _ in range(8):
        # 펼쳐서 더보기 버튼 수집
        candidates = driver.find_elements(
            By.XPATH,
            "//a[contains(.,'펼쳐서 더보기')] | //button[contains(.,'펼쳐서 더보기')]"
        )
        # 클릭
        candidates = [c for c in candidates if c.is_displayed()]

        # 더이상 존재하지 않는다면 종료
        if not candidates:
            break

        for btn in candidates:
            # 최대 클릭수 제한
            if clicked >= max_clicks:
                return clicked
            try:
                # 펼쳐서 더보기 이중 확인
                t = (btn.text or "").strip()
                if "펼쳐서 더보기" not in t:
                    continue
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn) # 중앙으로
                human_delay(0.1, 0.2)
                driver.execute_script("arguments[0].click();", btn) # 클릭
                clicked += 1
                time.sleep(random.uniform(*sleep_range))
            except:
                continue
        human_delay(0.2, 0.4)
    return clicked

def small_bounce_scroll(driver, px=600, jitter=120, sleep_range=(0.25, 0.45)):
    # 스크롤을 천천히 움직이면서 하나씩 추출
    j = random.randint(-jitter, jitter)
    driver.execute_script(f"window.scrollBy(0,{px + j});")
    time.sleep(random.uniform(*sleep_range))

DATE_KOR = re.compile(r'(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일') # 날짜 문자열 인식/추출
VISIT_NTH = re.compile(r'(\d{1,3})\s*번째\s*방문') # 방문 횟수 추출

# 날짜형식으로 변경
def _to_iso(y, m, d):
    try:
        return datetime(int(y), int(m), int(d)).strftime("%Y-%m-%d") 
    except:
        return None

# 방문횟수/방문일 추출
def parse_visit_block(block_el):
    # 방문횟수 수집
    visit_info_divs = block_el.find_elements(By.CSS_SELECTOR, "div.pui__QKE5Pr")
    if not visit_info_divs:
        return None, None

    # 제일 처음꺼 가져오기
    visit_div = visit_info_divs[0]

    # 방문일 수집
    visit_date_iso = None
    for el in visit_div.find_elements(By.CSS_SELECTOR, ".pui__blind"):
        try:
            t = (el.get_attribute("textContent") or "").strip()
            m = DATE_KOR.search(t or "")
            if m:
                # 날짜 형식으로 변경
                visit_date_iso = _to_iso(m.group(1), m.group(2), m.group(3))
                if visit_date_iso:
                    break
        except:
            pass
    # 방문 횟수에서 숫자만 가져옴
    # 텍스트 → 없애기
    whole = (visit_div.get_attribute("textContent") or "").strip()
    visit_count = None

    # 숫자만 추출출
    m2 = VISIT_NTH.search(whole)
    if m2:
        try:
            visit_count = int(m2.group(1))
        except:
            pass
    return visit_date_iso, visit_count

# 리뷰 텍스트 수집
def extract_review_text(block_el):
    try:
        # span으로 찾기
        text_divs = block_el.find_elements(By.CSS_SELECTOR, 'div.pui__vn15t2')
        if text_divs:
            anchors = text_divs[0].find_elements(By.CSS_SELECTOR, 'a[data-pui-click-code="rvshowmore"]')
            if anchors:
                text = (anchors[0].get_attribute("textContent") or "").strip()
                if text:
                    text = re.sub(r'\s+', ' ', text)  # 여러 공백을 하나로
                    return text
        
        # data-pui-click-code="rvshowmore" 직접 찾기
        anchors = block_el.find_elements(By.CSS_SELECTOR, 'a[data-pui-click-code="rvshowmore"]')
        if anchors:
            text = (anchors[0].get_attribute("textContent") or "").strip()
            if text:
                text = re.sub(r'\s+', ' ', text)
                return text
        
        # XPath로 찾기
        try:
            xpath_anchors = block_el.find_elements(By.XPATH, ".//a[@data-pui-click-code='rvshowmore']")
            if xpath_anchors:
                text = (xpath_anchors[0].get_attribute("textContent") or "").strip()
                if text:
                    text = re.sub(r'\s+', ' ', text)
                    return text
        except:
            pass
        
        return ""
    except Exception as e:
        print(f"텍스트 추출 오류: {e}")
        return ""

def find_review_blocks(driver):
    # <li> 전체를 블록으로 가져와야 리뷰 텍스트와 방문정보를 모두 찾을 수 있음
    blocks = driver.find_elements(By.CSS_SELECTOR, "li.place_apply_pui, li.EjjAW")
    if blocks:
        return blocks
    
    # 방문일 정보가 있는 div의 부모 li 찾기
    xp = ("//div[contains(@class,'pui__QKE5Pr')]/ancestor::li[1]")
    blocks = driver.find_elements(By.XPATH, xp)
    if blocks:
        return blocks
    
    # 마지막 폴백
    return driver.find_elements(By.CSS_SELECTOR, "div.pui__QKE5Pr")

import re, hashlib, random, time
from selenium.webdriver.common.by import By

# 리뷰 정규화
def _normalize_text(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r'[\u200B-\u200D\uFEFF]', '', s)  # 제로폭 제거
    s = re.sub(r'\s+', ' ', s).strip()           # 공백 정규화
    return s

# 방문일 정규화
def _normalize_date(s: str) -> str:
    return (s or "").strip()

# 방문횟수 정규화
def _normalize_count(v) -> str:
    # None → "", 숫자/문자 모두 문자열로 통일
    return "" if v is None else str(v).strip()

# 정규화 적용
def _make_key(visit_date, visit_count, review_text) -> str:
    vd = _normalize_date(visit_date)
    vc = _normalize_count(visit_count)
    rt = _normalize_text(review_text)
    key_str = f"{vd}|{vc}|{rt}"
    return hashlib.sha1(key_str.encode("utf-8")).hexdigest(), vd, vc, rt


def collect_reviews_full(driver, wait, hard_max=20000):
    ensure_entry_iframe(driver, wait)
    go_reviews_tab(driver, wait)
    
    # 정렬 최신순 → 시도
    try:
        # 정렬 텍스트 찾기 → 클릭
        sort_buttons = driver.find_elements(By.XPATH, "//button[contains(., '정렬')]")
        if sort_buttons:
            driver.execute_script("arguments[0].click();", sort_buttons[0])
            human_delay(0.4, 0.7)
            # 최신순 텍스트 찾기 → 클릭
            latest = driver.find_elements(By.XPATH, "//li[contains(., '최신순')] | //a[contains(., '최신순')]")
            if latest:
                driver.execute_script("arguments[0].click();", latest[0])
                human_delay(0.6, 1.0)
    except:
        pass

    try:
        step = driver.execute_script("return Math.floor(window.innerHeight * 0.7);") or 700
    except:
        step = 700

    pname = place_title(driver)
    seen, rows = set(), []
    last_seen_total, idle_rounds = 0, 0
    scroll_direction = 1  # 1: 아래, -1: 위

    driver.execute_script("window.scrollTo(0,0)")
    human_delay(0.6, 1.0)

    for round_i in range(1, 9999):
        ensure_entry_iframe(driver, wait)
        click_fold_expand_all(driver, wait, max_clicks=999, sleep_range=(0.12, 0.25)) # 펼쳐서 더보기 모두 누르기

        # <li> 블록들 수집
        blocks = find_review_blocks(driver)
      
        for b in blocks:
            try:
                # 방문일/방문횟수 파싱
                visit_date, visit_count = parse_visit_block(b)
                # 본문 텍스트 파싱
                review_text = extract_review_text(b)

                # 날짜/횟수 모두 None이면 스킵
                if (visit_date is None) and (visit_count is None):
                    continue

                # 3개의 변수 정규화 후 중복제거용 key 생성
                key, vd_norm, vc_norm, rt_norm = _make_key(visit_date, visit_count, review_text)
                if key in seen:
                    continue
                seen.add(key)
                rows.append({
                    "place_name": pname,
                    "visit_date": vd_norm,
                    "visit_count": (None if vc_norm == "" else int(vc_norm) if vc_norm.isdigit() else vc_norm),# 정규화된 방문횟수 가능하면 정수로 변환, 빈 문자열 → None
                    "review_text": rt_norm,
                })
            except:
                continue

        if round_i % 5 == 0:
            print(f"  라운드 {round_i}: 현재 {len(rows)}건 수집됨")

        # 최대 수집 한도에 도달시 종료
        if len(rows) >= hard_max:
            break
        # 새로 추가된 key 확인
        if len(seen) == last_seen_total:
            idle_rounds += 1
        else:
            idle_rounds = 0
            last_seen_total = len(seen)

        # idle 보강 시퀀스
        # 15 라운드 연속으로 새 리뷰가 추가되지 않았을 때 
        if idle_rounds >= 15:
            print(f"  추가 확인 중... (idle={idle_rounds})")

            # 스크롤 제일 밑으로 
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            human_delay(0.6, 1.0)
            click_fold_expand_all(driver, wait, max_clicks=999, sleep_range=(0.12, 0.25))
            human_delay(0.4, 0.7)

            # 다시 위로 올라감 (상하단 모두 점검)
            driver.execute_script("window.scrollTo(0, 0)")
            human_delay(0.6, 1.0)
            click_fold_expand_all(driver, wait, max_clicks=999, sleep_range=(0.12, 0.25))

            for scroll_pos in [0.25, 0.5, 0.75]:
                driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {scroll_pos})")
                human_delay(0.4, 0.7)
                click_fold_expand_all(driver, wait, max_clicks=999, sleep_range=(0.12, 0.25))

            # 지금 화면에서 보이는 리뷰들 가져와서 중복 확인
            blocks_check = find_review_blocks(driver)
            new_found = 0

            # 새로운 리뷰가 발생했다면 다시 점검
            # 정규화, key생성, 기존 리뷰들과 비교
            for b in blocks_check:
                try:
                    visit_date, visit_count = parse_visit_block(b)
                    review_text = extract_review_text(b)
                    if (visit_date is None) and (visit_count is None):
                        continue

                    key, vd_norm, vc_norm, rt_norm = _make_key(visit_date, visit_count, review_text)
                    if key not in seen:
                        new_found += 1
                        seen.add(key)
                        rows.append({
                            "place_name": pname,
                            "visit_date": vd_norm,
                            "visit_count": (None if vc_norm == "" else int(vc_norm) if vc_norm.isdigit() else vc_norm),
                            "review_text": rt_norm,
                        })
                except:
                    continue

            if new_found == 0:
                print(f" 최종: {len(rows)}건")
                break
            idle_rounds = 0

        # 왕복/바운스 스크롤
        if round_i % 15 == 0:
            scroll_direction *= -1
            driver.execute_script(f"window.scrollBy(0, {scroll_direction * 800})")
            human_delay(0.3, 0.6)

        small_bounce_scroll(driver, px=step, jitter=100, sleep_range=(0.4, 0.7))

        if round_i % 8 == 0:
            driver.execute_script("window.scrollBy(0, -500)")
            human_delay(0.3, 0.6)
            small_bounce_검
    driver.execute_script("window.scrollTo(0,0)")
    human_delay(0.6, 1.0)
    click_fold_expand_all(driver, wait, max_clicks=999, sleep_range=(0.12, 0.25))
    human_delay(0.4, 0.7)

    for _ in range(3):
        driver.execute_script("window.scrollBy(0, 800)")
        human_delay(0.3, 0.6)
        click_fold_expand_all(driver, wait, max_clicks=999, sleep_range=(0.12, 0.25))

    blocks = find_review_blocks(driver)
    for b in blocks:
        try:
            visit_date, visit_count = parse_visit_block(b)
            review_text = extract_review_text(b)
            if (visit_date is None) and (visit_count is None):
                continue

            key, vd_norm, vc_norm, rt_norm = _make_key(visit_date, visit_count, review_text)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "place_name": pname,
                "visit_date": vd_norm,
                "visit_count": (None if vc_norm == "" else int(vc_norm) if vc_norm.isdigit() else vc_norm),
                "review_text": rt_norm,
            })
        except:
            continue

    print(f"  최종 수집 완료: {len(rows)}건")

    # (선택) 마지막 방어적 중복 제거
    final_seen, deduped = set(), []
    for r in rows:
        k = f"{_normalize_date(r['visit_date'])}|{_normalize_count(r['visit_count'])}|{_normalize_text(r['review_text'])}"
        if k in final_seen:
            continue
        final_seen.add(k)
        deduped.append(r)

    return deduped



# 데이터 csv로 저장
def save_visits_csv(rows, base_dir, place_name):
    if not rows:
        return None
      
    # 파일 이름/경로 지정
    safe = re.sub(r'[\\/:*?"<>|]+', '_', place_name).strip()
    out_path = os.path.join(base_dir, f"{safe}_new_reviews.csv") 
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["place_name", "visit_date", "visit_count", "review_text"])
        for r in rows:
            w.writerow([r["place_name"], r["visit_date"], r["visit_count"], r["review_text"]])
    print(f"✔ 저장: {out_path}")
    return out_path

# 실행 & 디버깅
names = [
    "돈미화로 방학동점",
    "목구멍 방학점",
    "고기굽는베베",
    "와우 솥뚜껑삼겹살",
    "방학동고추장삼겹살",
    "싹쓰리솥뚜껑김치삼겹살 방학점",
    "싸전갈비",
    "갈비둥지"
]

for nm in names:
    print(f"\n {nm} 수집 시작 ")
    driver = None
    try:
        driver = make_driver()
        wait = WebDriverWait(driver, 10)
        open_entry_by_search(driver, wait, nm)
        rows = collect_reviews_full(driver, wait, hard_max=20000)
        if rows:
            save_visits_csv(rows, BASE_DIR, rows[0]["place_name"])
            print(f"총 {len(rows)}건 수집 완료")
        else:
            print("수집 결과 0건")
    except Exception as e:
        print(f" 실패: {nm} → {e}")
    finally:
        if driver:
            driver.quit()
