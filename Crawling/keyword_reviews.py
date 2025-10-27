import pandas as pd
from datetime import datetime
from pathlib import Path

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


# 가게명 (있는 경우 그대로, 없으면 og:title로)
place_name = (driver.execute_script("""
  const og = document.querySelector('meta[property="og:title"]');
  return (og && og.content) ? og.content : document.title;
""") or "").split(" :")[0].strip()

df_kw = pd.DataFrame(keywords, columns=["label", "count"])
df_kw.insert(0, "place_name", place_name)

outdir = Path(r"C:\Users\output"); outdir.mkdir(parents=True, exist_ok=True)
outpath = outdir / f"{place_name}_keywords_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
df_kw.to_csv(outpath, index=False, encoding="utf-8-sig")
print("저장:", outpath)
df_kw.head()


def collect_keywords_current_page():
    # 리뷰 탭 → 더보기 → 추출
    # entryIframe로 전환
    ensure_entry_iframe()
  
    # 리뷰 탭
    for xp in ["//a[@role='tab' and contains(.,'리뷰')]", "//button[contains(.,'리뷰')]"]:
        els = driver.find_elements(By.XPATH, xp)
        if els:
            driver.execute_script("arguments[0].click();", els[0]); time.sleep(0.5); break
          
    # 더보기 클릭
    click_more_generic(max_clicks=5, sleep=0.5)
  
    # 수집
    kw_items = driver.find_elements(By.XPATH,"//li[.//span[contains(@class,'t3JSf')] and .//span[contains(@class,'CUoLy')]]") \
               or driver.find_elements(By.XPATH,"//li[.//span[contains(.,'키워드를 선택한 인원')]]")
    out = []
  
    for li in kw_items:
        # 라벨
        label = ""
        els = li.find_elements(By.XPATH, ".//span[contains(@class,'t3JSf')]")
        if els and els[0].text.strip():
            label = els[0].text.strip().replace('"','')
        else:
            spans = [s.text.strip() for s in li.find_elements(By.XPATH, ".//span") if s.text.strip()]
            if spans:
                label = next((s for s in spans if "키워드" not in s), spans[0]).replace('"','')
        # 수치
        cnt = int_from(li.text)
        if label:
            out.append((label, cnt))
    return out

rows = []
for name in names:
    try:
        # searchIframe에서 상호 클릭하여 entryIframe 진입
        open_entry_by_search(name)  

        # 가게 이름 추출
        place_name = (driver.execute_script("""
          const og = document.querySelector('meta[property="og:title"]');
          return (og && og.content) ? og.content : document.title;
        """) or "").split(" :")[0].strip()
      
        kws = collect_keywords_current_page()
        for label, count in kws:
            rows.append({"place_name": place_name or name, "label": label, "count": count})
          
        print(f"{name}: {len(kws)}개")
        time.sleep(0.8)
      
    except Exception as e:
        print(f"{name}: {e}")

df_all = pd.DataFrame(rows)
outdir = Path(r"C:\Users\output"); outdir.mkdir(parents=True, exist_ok=True)
outpath = outdir / f"competitors_keywords_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
df_all.to_csv(outpath, index=False, encoding="utf-8-sig")
print("저장:", outpath)
