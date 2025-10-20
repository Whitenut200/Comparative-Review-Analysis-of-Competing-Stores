import re, time
from urllib.parse import quote
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import pandas as pd
from pathlib import Path
from datetime import datetime

# 문자열 안에서 숫자를 찾아 정수(int)로 변환 → 방문자 리뷰수, 블로그 리뷰수 처리 ex) 방문자 리뷰수 1,490 -> 1490
def _int_from(text: str):
    m = re.search(r'(\d[\d,]*)', text or '') # 빈 문자열 → ""
    return int(m.group(1).replace(',', '')) if m else None # 쉼표 제거

# iframe → entryIframe으로 진입  
# 해당 함수가 없으면 가게 페이지 안에서 클릭이나 크롤링이 먹히지 않음 **꼭 필요**
def _ensure_entry_iframe():
    driver.switch_to.default_content()
    
    # 로딩 기다렸다가 바로 진입
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe#entryIframe"))) 

# 가게명 추출
def _robust_place_name():
    # 자바스크립트 실행
    name = (driver.execute_script("""
      # 메타태그를 찾기
      # ex) <meta property="og:title" content="와우솥뚜껑삼겹살 : 네이버">
      const og = document.querySelector('meta[property="og:title"]'); 

      # 있으면 og.content 반환, 없으면 document.title 반환
      return (og && og.content) ? og.content : document.title;
    """) or "").split(" :")[0].strip()
    if name:
        return name

    # 메타태그를 못찾았을 경우
    for by, loc in [(By.CSS_SELECTOR, "span.Fc1rA"), # 제목에 해당하는 <span>
                    # 위에서 못찾았을 경우를 대비 XPATH 경로로 찾기
                    # h1/span , h2/span
                    (By.XPATH, "//h1//span[normalize-space()] | //h2//span[normalize-space()]")]: # normalize-space(): 텍스트
        try:
            # 화면에 실제로 표시될 때까지 기다리기
            el = wait.until(EC.visibility_of_element_located((by, loc)))
            # 공백 제거
            t = el.text.strip()

            # 텍스트가 나온다면 저장
            if t: 
                return t
        except Exception:
            pass
    return ""


def _open_entry_by_search(query_name: str):
    # 네이버 지도 진입 & 검색
    driver.switch_to.default_content()
    driver.get(f"https://map.naver.com/p/search/{quote(query_name)}")

    # 기다렸다가 searchIframe으로 전환
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe#searchIframe")))
    time.sleep(0.6)

    # 검색 결과 안정화용 한 번 스크롤
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight)"); time.sleep(0.6)

    # 클릭 가능한 상호(버튼) 찾기
    cand = driver.find_elements(
        By.XPATH,
        "//a[@role='button' and contains(@class,'place_bluelink')]"
        " | //a[@role='button'][.//span[contains(@class,'TYaxT')]]"
    )
    if not cand:
        # 폴백: 상호 span에서 조상 a로 상승
        spans = driver.find_elements(By.CSS_SELECTOR, "span.TYaxT")
        if spans:
            try:
                cand = [spans[0].find_element(By.XPATH, "./ancestor::a[@role='button'][1]")]
            except Exception:
                pass
    if not cand:
        raise RuntimeError("검색 결과에서 클릭 가능한 상호를 찾지 못했어요.")

    # 질의명과 유사한 것 우선
    qn = re.sub(r"\s+", "", query_name).lower() # 공백제거 & 소문자
    target = None
    for a in cand:
        nm = ""
        try:
            nm = a.find_element(By.XPATH, ".//span[contains(@class,'TYaxT')][normalize-space()]").text.strip()
        except Exception:
            nm = (a.text or "").strip()
        nm2 = re.sub(r"\s+", "", nm).lower()
        if nm2 and (qn in nm2 or nm2 in qn):
            target = a; break
    if target is None:
        target = cand[0]

    # 클릭 → entryIframe로 전환
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", target)
    driver.execute_script("arguments[0].click();", target)
    time.sleep(0.8)

    driver.switch_to.default_content()
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#entryIframe")))
    _ensure_entry_iframe()

def _extract_home_basic():
    # 이름/리뷰수/주소 추출
    name = _robust_place_name()

    # 방문자/블로그 리뷰 수
    visitor = blog = None
    try:
        # 버튼으로 찾기
        el = driver.find_element(By.CSS_SELECTOR, 'a[role="button"][href*="/review/visitor"]')
        visitor = _int_from(el.text) # 텍스트 → 숫자만 추출
    except Exception:

        # 위에서 만약 못찾았다면, "방문자 리뷰" 텍스트로 찾기
        try:
            el = driver.find_element(By.XPATH, "//*[self::a or self::span or self::button][contains(.,'방문자 리뷰')]")
            visitor = _int_from(el.text) # 텍스트 → 숫자만 추출
        except Exception:
            pass

    # 방문자 리뷰와 같은 방법으로 찾기
    try:
        el = driver.find_element(By.CSS_SELECTOR, 'a[role="button"][href*="/review/ugc"]')
        blog = _int_from(el.text) # 텍스트 → 숫자만 추출
    except Exception:
        try:
            el = driver.find_element(By.XPATH, "//*[self::a or self::span or self::button][contains(.,'블로그 리뷰')]")
            blog = _int_from(el.text) # 텍스트 → 숫자만 추출
        except Exception:
            pass

    # 주소
    address = ""
    try:
        # <span>으로 찾기
        address = driver.find_element(By.CSS_SELECTOR, "span.LDgIH").text.strip() # 텍스트만, 양쪽 공백 없애기
    except Exception:

        # <span>으로 못찾았을 경우, text='주소'를 찾아서 가져오기
        for xp in [
            "//span[normalize-space()='주소']/following-sibling::*[1][normalize-space()]",
            "//div[.//span[normalize-space()='주소']]//span[normalize-space()][last()]",
        ]:
            els = driver.find_elements(By.XPATH, xp)
            if els and els[0].text.strip():
                address = els[0].text.strip(); break
    address = re.sub(r"[ \t]+", " ", address).strip() # 연속된 공백 또는 탭(\t)을 " "으로 변경

    # 전체 리뷰 수 구하기
    total_reviews = None

    # 만약 방문자리뷰 & 블로그리뷰 모두 존재하면 더하기
    if visitor is not None and blog is not None:
        total_reviews = visitor + blog

    # 둘 중 하나라도 null 이면
    else:
        # 방문자 리뷰 = null → 블로그 리뷰
        # 블로그 리뷰 = null → 방문자자 리뷰
        total_reviews = visitor if visitor is not None else blog
    
    # 데이터
    return {
        "name": name,
        "visitor_reviews": visitor,
        "blog_reviews": blog,
        "total_reviews": total_reviews,
        "address": address
    }

def crawl_home_basic_for_store(store_name: str):
    # 가게명으로 검색해서(맨 위 결과 클릭)
    _open_entry_by_search(store_name)

    # 기본정보 수집집
    data = _extract_home_basic()
    print(f"{data['name']} | 리뷰수:{data['total_reviews']} (방문자:{data['visitor_reviews']}, 블로그:{data['blog_reviews']}) | 주소:{data['address']}")
    return data

# 경쟁가게
# comparative_stores.py에서 추출한 가게명
names = [
    "돈미화로 방학동점",
    "목구멍 방학점",
    "고기굽는베베",
    "와우 솥뚜껑삼겹살",
    "방학동고추장삼겹살",
    "싹쓰리솥뚜껑김치삼겹살 방학점",
    "싸전갈비",
    "갈비둥지",
]

rows = []
for n in names:
    try:
        # 데이터 쌓기
        rows.append(crawl_home_basic_for_store(n))
        time.sleep(0.8) 
    except Exception as e:
        print("실패:", n, e)

# 데이터 프라임 형식으로 변환
df = pd.DataFrame(rows, columns=["name","total_reviews","visitor_reviews","blog_reviews","address"])

# 데이터 저장 경로 설정
out = Path(r"C:\Users\output") / f"competitors_home_basic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
out.parent.mkdir(parents=True, exist_ok=True) # 상위 폴더 있다면 넘어가고 없다면 다 만들기
df.to_csv(out, index=False, encoding="utf-8-sig")
print("저장:", out)
