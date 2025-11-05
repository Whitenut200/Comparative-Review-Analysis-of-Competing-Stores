# 유니온 → 정제 → 중복제거 → 토큰화(불용어 제거)
import os, re, glob, unicodedata, hashlib
import pandas as pd
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(r"D:/reviews")  # 파일 경로
TS = datetime.now().strftime("%Y%m%d_%H%M%S") # 중복 방지를 위한 파일명 뒤에 날짜/시간

# STOP/강조어/부정어 정의
# 감성분석은 제외하지 않고 사용
STOP_BASE = set("""
은 는 이 가 을 를 에 에서 으로 로 와 과 도 만 까지 부터 의 에게 께서 한테 
하고 하다 있다 없다 되다 이다 아니다 같다 다르다 크다 작다 좋다 나쁘다
그리고 그러나 그래서 그런데 하지만 또한 또는 그냥 좀 아주 진짜 정말 매우 너무
요즘 오늘 어제 내일 이번 지난 다음 또 다시 계속 항상 가끔 때때로 자주
것 수 때 곳 점 개 명 원 시간 분 일 월 년 번째 정도 약 
""".split())

# TF-IDF용은 해당 단어 제외
INTENSIFIERS = {
    '너무','정말','진짜','완전','매우','아주','엄청','진심',
    '최고로','극도로','극','되게','엄청나','완전히','정말로'
}
NEGATIONS = {
    '안','못','않','아니','아니다','전혀','절대','별로','그닥','덜','없다',
    '않다','아니야','아닌','아니었','아니에요','아니네요','아닙니다'
}

# 최종 TF-IDF용 STOP (강조/부정 신호는 남기기)
STOP = (STOP_BASE - INTENSIFIERS - NEGATIONS)

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

# 날짜 정규화
raw["visit_date"] = raw["visit_date"].map(norm_date)

# 방문횟수 정규화
raw["visit_count"] = raw["visit_count"].map(norm_count).astype("Int64")

# 중복 제거 (가게+텍스트+방문일+방문횟수) 
raw = (raw
       .drop_duplicates(subset=["place_name", "review_text", "visit_date", "visit_count"])
       .reset_index(drop=True))

# 토큰화 + 불용어 제거
try:
    # kiwipiepy : 한국어 형태소 분석기 라이브러리
    from kiwipiepy import Kiwi
    kiwi = Kiwi()
    def tokenize(text):
        toks=[]
        for t in kiwi.tokenize(text, normalize_coda=True):
            # t.form : 표면형 (ex) 갔다 t.lemma : 기본형 (ex) 가다
            # t.lemma가 있으면 기본형으로 없으면 표면형으로
            lemma = t.form if t.lemma is None else t.lemma

            # 순수 한글/영문/숫자로만 이루어진 단어 필터링
            if re.fullmatch(r"[가-힣A-Za-z0-9]+", lemma):
                toks.append(lemma)
        return toks
    TOKENIZER = "kiwipiepy" # kiwi 사용

# kiwi가 없을때
except Exception:
    def tokenize(text):
        text = re.sub(r"http\S+|www\.\S+", " ", text) # http, www로 시작하는 문자열 제거 → url 처리리
        text = re.sub(r"[^가-힣A-Za-z0-9\s]", " ", text) # 특수문자 제거
        toks = [w for w in re.split(r"\s+", text) if w] # 공백으로 분리 → 빈 문자열 제거
        return toks
    TOKENIZER = "regex" # 정규식 기반

 
# TF_IDF용, 감성분석용 따로 만들기
# TF_IDF용
def clean_tokens_for_tfidf(toks):
    """불용어 제거 O, 조사/어미 일부 정리"""
    out = []
    for w in toks:
        w2 = re.sub(r"(은|는|이|가|을|를|에|에서|으로|로|와|과|도|만|까지|부터|의|께서|한테|에게)$", "", w)
        w2 = re.sub(r"(습니다|세요|어요|아요|해요|지요|네요|예요|이에요)$", "", w2)
        if not w2 or len(w2) < 2:              # 2글자 미만 제거
            continue
        if w2 in STOP:                          # 불용어 제거
            continue
        if re.fullmatch(r"\d+", w2):            # 숫자만 제거
            continue
        out.append(w2)
    return out

# 감성분석용
def clean_tokens_for_sentiment(toks):
    # 불용어 제거 X
    out = []
    for w in toks:
        w2 = re.sub(r"(은|는|이|가|을|를|에|에서|으로|로|와|과|도|만|까지|부터|의|께서|한테|에게)$", "", w)
        if not w2:
            continue
        out.append(w2)
    return out

ssert all(c in raw.columns for c in ["place_name","visit_date","visit_count","review_text"])

# 기본 토큰화
raw = raw.reset_index(drop=True)
raw["review_number"] = raw.index + 1 # 리뷰 번호
raw["tokens_raw"] = raw["review_text"].apply(tokenize) # 토큰화 진행

# TF-IDF용
raw["tokens_tfidf"] = raw["tokens_raw"].apply(clean_tokens_for_tfidf)
tmp_tfidf = raw[["place_name","review_number","visit_date","visit_count","tokens_tfidf"]].copy()
tmp_tfidf["tokens_join"] = tmp_tfidf["tokens_tfidf"].apply(lambda x: " ".join(x))

# 감성분석용
raw["tokens_sent"] = raw["tokens_raw"].apply(clean_tokens_for_sentiment)
tmp_sent = raw[["place_name","review_number","visit_date","visit_count","tokens_sent"]].copy()
tmp_sent["tokens_join"] = tmp_sent["tokens_sent"].apply(lambda x: " ".join(x))

# 저장
out_tfidf = BASE_DIR / f"reviews_tokens_tfidf_{TS}.csv"
out_sent  = BASE_DIR / f"reviews_tokens_sentiment_{TS}.csv"

tmp_tfidf.to_csv(out_tfidf, index=False, encoding="utf-8-sig")
tmp_sent.to_csv(out_sent, index=False, encoding="utf-8-sig")

# 추가 데이터 (도구설명용)
import ast

df_long = raw.copy()

# tokens_tfidf 사용
# 방문일자에 보이는 도구설명으로 감성분석에 씌이는 데이터가 아님
df_long["tokens"] = df_long["tokens_tfidf"]

# 안전하게 문자열→리스트 변환 (혹시 문자열일 경우 대비)
def to_list_safe(x):
    if isinstance(x, list):
        return x
    try:
        return ast.literal_eval(x)
    except Exception:
        return []

df_long["tokens"] = df_long["tokens"].apply(to_list_safe)

# 토큰을 행 단위로 펼치기
long_df = df_long.explode("tokens", ignore_index=True)

# 필요한 컬럼만 정리
long_df = long_df[["place_name","review_number","visit_date","tokens"]].rename(columns={"tokens":"token"})

# 빈 값 제거
long_df = long_df[long_df["token"].notna() & (long_df["token"] != "")]

# 저장
out_long = BASE_DIR / f"reviews_tokens_long_{TS}.csv"
long_df.to_csv(out_long, index=False, encoding="utf-8-sig")

print("저장 완료")
print(f" - TF-IDF dataset:    {out_tfidf}")
print(f" - Sentiment dataset: {out_sent}")
print(f" - Long-format tokens: {out_long}")
print(f"Tokenizer used: {TOKENIZER}")

