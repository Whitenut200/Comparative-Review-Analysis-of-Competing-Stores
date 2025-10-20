from urllib.parse import quote
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import time, pandas as pd
from pathlib import Path

# '방학역 삼겹살' 검색 결과에서 이름만 중복 제거해 TOP8 추출 + CSV 저장
# 경쟁가게 이름 추출하기

QUERY = "방학역 삼겹살"

# 검색 페이지 열고 searchIframe 진입
# 가게 이름만 크롤링 → 상세 페이지까지 갈 필요 없음
# <iframe id="searchIframe">  ← 가게 목록 (리스트) 표시
# <iframe id="entryIframe">   ← 가게 상세 페이지 표시
driver.switch_to.default_content()
driver.get(f"https://map.naver.com/p/search/{quote(QUERY)}") # 네이버 지도 사이트

# 로딩될 때까지 기다리기 → 바로 전환
# 가게 상세 페이지로 전환한다면
# wait.until(EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe#entryIframe")))
wait.until(EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe#searchIframe")))
print("@ searchIframe 진입")

# 결과 끝까지 스크롤(더 로드될 게 없을 때까지)
stable = 0 # 스크롤을 내려도 페이지 높이가 변하지 않는 횟수
prev_h = 0 # 이전 높이값 저장용
while stable < 3: # 3번 이전에 높이가 변하는 경우
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);") # 스크롤 아래까지 내리기
    time.sleep(0.8)
    # 전체 높이 측정
    h = driver.execute_script("return document.body.scrollHeight;")
    
    # 더이상 스크롤 되지 않는다면
    if h == prev_h: 
        stable += 1 
    # 스크롤 된다면
    else: 
        stable = 0

    # 전체 높이 저장
    prev_h = h
print("@ 스크롤 완료")

# 이름만 수집
# 맨처음엔 HTML 요소(span)들을 찾기
name_els = driver.find_elements(By.CSS_SELECTOR, "span.TYaxT")

# 만약 위에서 찾지 못한다면 XPATH 경로로 찾기
if not name_els:
    # 폴백: /entry/place/가 포함된 링크(가게 상세페이지로 가는 링크), 그 내부의 <span>요소 중 텍스트 가져오기
    name_els = driver.find_elements(By.XPATH, "//a[contains(@href,'/entry/place/')]/span[normalize-space()]") # normalize-space(): 텍스트

# text 형식으로 바꾸고 None이면 "", 양쪽 공백제거(.strip())
raw_names = [(e.text or "").strip() for e in name_els]
raw_names = [n for n in raw_names if n]  # 빈 문자열("") 제거

# 중복 제거(등장 순서 보존) 후 TOP8 
# 광고로 인해 중복되는 것을 방지
seen = set() # 중복 검사용
names = [] 
for n in raw_names:
    # seen 안에 없는 이름이라면 (즉, 중복되지 않았다면)
    if n not in seen: 
        # seen에 저장
        seen.add(n) 
        names.append(n)
    
    # 최대 8개의 이름만 저장 (Top 8)
    if len(names) >= 8:
        break

print("@ 추출된 상호명(Top 8, dedup):")
for i, n in enumerate(names, 1):
    print(f"{i}. {n}")

# CSV 저장
# 현재 작업 디렉토리에 "output"폴더 경로
outdir = Path.cwd() / "output"
outdir.mkdir(exist_ok=True) # 폴더 없다면 생성
outpath = outdir / "competitors_top8_names.csv" # 이름 설정

# 데이터프라임으로 변환 후 csv로 저장
pd.DataFrame({"rank": range(1, len(names)+1), "name": names}).to_csv(outpath, index=False, encoding="utf-8-sig")
print("@ 저장:", outpath)
