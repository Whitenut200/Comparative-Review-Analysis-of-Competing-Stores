# 유니온 → 정제 → 중복제거 → 토큰화(불용어 제거)
import os, re, glob, unicodedata, hashlib
import pandas as pd
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(r"D:/reviews")  # 파일 경로
TS = datetime.now().strftime("%Y%m%d_%H%M%S") # 중복 방지를 위한 파일명 뒤에 날짜/시간

# 리뷰 파일 합치기 (유니온)
# 데이터 불러오기
paths = sorted(glob.glob(str(BASE_DIR / "*_new_reviews*.csv")))
if not paths:
    raise FileNotFoundError("리뷰 CSV가 없습니다 (*_new_reviews*.csv).")

dfs = []
for p in paths:
    df = pd.read_csv(p)
    # 컬럼 설정
    # 파일마다 컬럼 명이 다른게 지정되어있을 수도 있기 때문에 두 개 중 택1
    cols = [c.lower() for c in df.columns]
    df.columns = cols
    if "place_name" not in df.columns:
        df["place_name"] = Path(p).stem.split("_new_reviews_")[0] # 파일명에서 가져오기
    if "review_text" not in df.columns:
        cand = [c for c in df.columns if c in ("본문","review_text")] # 본문 or review_test 가져오기
        if cand: df["text"] = df[cand[0]]
        else: raise ValueError(f"text 컬럼 없음: {p}")
    if "visit_date" not in df.columns:
        cand = [c for c in df.columns if c in ("방문일","visit_date")] # 방문일 or visit_date 가져오기
    if "visit_count" not in df.columns:
        cand = [c for c in df.columns if c in ("방문횟수","visit_count")]  # 방문횟수 or visit_count 가져오기
      
    dfs.append(df[["place_name","visit_date","visit_count","review_text"]])

# 유니온
raw = pd.concat(dfs, ignore_index=True)

# 텍스트 정규화 + 중복 제거
def normalize_text(s: str) -> str:
    s = str(s or "").strip()
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", " ", s)
    return s

# 날짜 정규화
def norm_date(s):
    ts = pd.to_datetime(s, errors="coerce")
    return ts.dt.date if isinstance(ts, pd.Series) else (ts.date() if pd.notna(ts) else pd.NaT)

# 방문횟수 정규화
def norm_count(x):
    if pd.isna(x): 
        return pd.NA
    m = re.search(r"\d+", str(x))
    return int(m.group()) if m else pd.NA

# 텍스트 정규화
raw["review_text"] = raw["review_text"].map(normalize_text)

# 날짜 정규화: datetime으로 파싱 후 '일(date)' 단위만 사용
raw["visit_date"] = raw["visit_date"].map(norm_date)

# 방문횟수 정규화: 숫자만 추출, pandas nullable 정수형(Int64)로 보관
raw["visit_count"] = raw["visit_count"].map(norm_count).astype("Int64")

# ===== 4) 중복 제거 (가게+텍스트+방문일+방문횟수 조합 기준) =====
raw = (raw
       .drop_duplicates(subset=["place_name", "review_text", "visit_date", "visit_count"])
       .reset_index(drop=True))

# 3) 토큰화(kiwipiepy 있으면 사용, 없으면 정규식 폴백) + 불용어 제거
try:
    from kiwipiepy import Kiwi
    kiwi = Kiwi()
    def tokenize(text):
        toks=[]
        for t in kiwi.tokenize(text, normalize_coda=True):
            lemma = t.form if t.lemma is None else t.lemma
            if re.fullmatch(r"[가-힣A-Za-z0-9]+", lemma):
                toks.append(lemma)
        return toks
    TOKENIZER = "kiwipiepy"
except Exception:
    def tokenize(text):
        text = re.sub(r"http\S+|www\.\S+", " ", text)
        text = re.sub(r"[^가-힣A-Za-z0-9\s]", " ", text)
        toks = [w for w in re.split(r"\s+", text) if w]
        return toks
    TOKENIZER = "regex"

# 간단 불용어(원하면 계속 추가)
# 불용어 리스트 보강
STOP = set("""
은 는 이 가 을 를 에 에서 으로 로 와 과 도 만 까지 부터 의 에게 께서 한테 
하고 하다 있다 없다 되다 이다 아니다 같다 다르다 크다 작다 좋다 나쁘다
그리고 그러나 그래서 그런데 하지만 또한 또는 그냥 좀 아주 진짜 정말 매우 너무
요즘 오늘 어제 내일 이번 지난 다음 또 다시 계속 항상 가끔 때때로 자주
것 수 때 곳 점 개 명 원 시간 분 일 월 년 번째 정도 약 
""".split())

# 토큰 정제 함수 개선
def clean_tokens(toks):
    out = []
    for w in toks:
        # 조사 제거 (더 포괄적으로)
        w2 = re.sub(r"(은|는|이|가|을|를|에|에서|으로|로|와|과|도|만|까지|부터|의|께서|한테|에게)$", "", w)
        
        # 어미 제거 (일부)
        w2 = re.sub(r"(습니다|세요|어요|아요|해요|지요|네요|예요|이에요)$", "", w2)
        
        if not w2 or w2 in STOP or len(w2) < 2:  # 2글자 미만 제거
            continue
            
        # 숫자만 있는 토큰 제거
        if re.fullmatch(r"\d+", w2):
            continue
            
        out.append(w2)
    return out

raw["tokens"] = raw["review_text"].apply(lambda s: clean_tokens(tokenize(s)))

# 인덱스 리셋 후 번호 매기기
raw = raw.reset_index(drop=True)
raw["review_number"] = raw.index + 1

# BASE_DIR = "D:/SY 업무/기타/개인과제/리뷰/raw_data"
# 4) 저장(마스터 원문 + 토큰)
out_master = BASE_DIR / f"reviews_master_{TS}.csv"
raw[["place_name","visit_date","visit_count","review_text","tokens"]].to_csv(out_master, index=False, encoding="utf-8-sig")

out_tokens = BASE_DIR / f"reviews_master_tokens_{TS}.csv"
# 토큰은 공백-조인 문자열도 같이 저장해두면 TF-IDF 바로 가능
tmp = raw.copy()
tmp["tokens_join"] = tmp["tokens"].apply(lambda x: " ".join(x))
tmp[["place_name","review_number","visit_date","visit_count","tokens_join"]].to_csv(out_tokens, index=False, encoding="utf-8-sig")



print("💾 저장:", out_master.name, "|", out_tokens.name)
print("토큰화 방식:", TOKENIZER)
# 데이터 현황 파악
print("=== 데이터 현황 ===")
print(f"총 리뷰 수: {len(raw):,}")
print(f"가게 수: {raw['place_name'].nunique()}")
print(f"가게별 리뷰 수:\n{raw['place_name'].value_counts().head(10)}")

# 토큰 현황
all_tokens = [token for tokens in raw['tokens'] for token in tokens]
print(f"\n총 토큰 수: {len(all_tokens):,}")
print(f"유니크 토큰 수: {len(set(all_tokens)):,}")

# 빈도 높은 토큰 확인 (불용어 추가 제거 필요한지 체크)
from collections import Counter
token_freq = Counter(all_tokens)
print(f"\n상위 토큰 30개:\n{token_freq.most_common(30)}")


# ====== 아래 코드만 추가 ======

import ast
import pandas as pd
df = raw.copy()

# tokens 문자열을 리스트로 변환
def to_list_safe(x):
    if isinstance(x, list):
        return x
    try:
        return ast.literal_eval(x)
    except Exception:
        return []

df['tokens'] = df['tokens'].apply(to_list_safe)

# tokens를 행으로 분리
long_df = df.explode('tokens', ignore_index=True)

# 필요 컬럼만 선택 (place_name, visit_date, tokens)
long_df = long_df[['place_name', 'review_number','visit_date', 'tokens']].rename(columns={'tokens': 'token'})

# 빈 값 제거
long_df = long_df[long_df['token'].notna() & (long_df['token'] != '')]

# CSV 파일로 저장
output_path = BASE_DIR / f"_tokens_long{TS}.csv"
long_df.to_csv(output_path, index=False, encoding='utf-8-sig')

print(f"저장 완료 ✅ → {output_path}")

