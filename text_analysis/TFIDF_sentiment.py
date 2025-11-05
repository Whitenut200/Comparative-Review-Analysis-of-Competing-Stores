# 통합 분석 파이프라인: TF-IDF → 가게별 특징 → 감정분석
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import Counter
import re

# scikit-learn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from scipy.stats import chi2_contingency

# 설정
BASE_DIR = Path(r"D:/review+date+count")  # 네 경로
TS = datetime.now().strftime("%Y%m%d_%H%M%S")

# KNU 한국어 감성사전 추가
sentiment_dict = {}
sentiment_dict_path = BASE_DIR / 'SentiWord_Dict.txt'

if sentiment_dict_path.exists():
    print(f"감성사전 로드 중: {sentiment_dict_path.name}")
    with open(sentiment_dict_path, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) == 3:
                word = parts[0]
                pos_score = float(parts[1])
                neg_score = float(parts[2])
                sentiment_dict[word] = (pos_score, neg_score)
    print(f"감성사전 로드 완료: {len(sentiment_dict):,}개 단어")
    USE_SENTIMENT_DICT = True
else:
    print("감성사전 파일이 없어서 키워드 방식만 사용")
    USE_SENTIMENT_DICT = False

# 토큰화된 데이터 로드 (token.py에서 생성된 파일)
# tfidf용 데이터 (불용어제거)
token_tfidf_files = sorted(BASE_DIR.glob("reviews_tokens_tfidf_*.csv"))
if not token_tfidf_files:
    raise FileNotFoundError("token_tfidf_files 토큰 파일이 없습니다. 전처리를 먼저 실행하세요.")

# sentiment용 데이터 (불용어제거X)
token_sentiment_files = sorted(BASE_DIR.glob("reviews_tokens_sentiment_*.csv"))
if not token_tfidf_files:
    raise FileNotFoundError("token_sentiment_files 토큰 파일이 없습니다. 전처리를 먼저 실행하세요.")

latest_token_file_tf = token_tfidf_files[-1]
tfidf_df = pd.read_csv(latest_token_file_tf)

latest_token_file_st = token_sentiment_files[-1]
sentiment_df = pd.read_csv(latest_token_file_st)

# NaN → 빈문자
sentiment_df["tokens_join"] = sentiment_df["tokens_join"].fillna("")

# TF-IDF 기반 키워드 추출
print("TF-IDF 키워드 추출 중...")

# 전체 TF-IDF
vectorizer = TfidfVectorizer(
    max_features=1000, # 상위 1000개 단어까지만 사용
    min_df=2, # 2개 이상 문서에서 등장한 단어만 포함
    max_df=0.9, # 전체 문서의 90% 이상에서 등장하는 단어는 제거 (너무 흔함)
    ngram_range=(1, 2) # 단어 1개(uni-gram) + 단어쌍(bi-gram) 모두 고려
)
# NaN(Null) 제거 + 이모티콘도 제외
tf_df = tfidf_df.dropna(subset=['tokens_join']).copy()

# 빈 문자열(공백만 포함) 제거
tf_df = tf_df[tf_df['tokens_join'].str.strip().ne('')]

# 위에 설정한대로 벡터화
tfidf_matrix = vectorizer.fit_transform(tf_df['tokens_join']) 
# 행렬의 열 이름(=단어목록) 가져오기
feature_names = vectorizer.get_feature_names_out()

# 전체 키워드 순위
tfidf_scores = np.array(tfidf_matrix.sum(axis=0)).flatten()

# 단어와 점수 한쌍으로 묶어서 리스트 생성
global_keywords = [(feature_names[i], score) for i, score in enumerate(tfidf_scores)]
# 점수가 높은 단어 순서대로 정렬
global_keywords.sort(key=lambda x: x[1], reverse=True)

# 결과 저장용 DataFrame
# 상위 100개만 추출
global_tfidf_df = pd.DataFrame(global_keywords[:100], columns=['keyword', 'tfidf_score'])
global_tfidf_df['rank'] = range(1, len(global_tfidf_df) + 1)
global_tfidf_df['analysis_type'] = 'global_tfidf'

print(f"전체 상위 키워드: {global_keywords[:10]}")

# 가게별 특징 단어 분석
print("가게별 특징 단어 분석 중...")

place_keywords = []
places = tf_df['place_name'].unique()

# 리뷰텍스트 가져오기
# 가게의 특징을 알아보는 것이기 때문에 (해당가게 vs 다른가게) 둘다 구분하여 추출
for place in places:
    place_reviews = tf_df[tf_df['place_name'] == place]['tokens_join']
    other_reviews = tf_df[tf_df['place_name'] != place]['tokens_join']
    
    if len(place_reviews) < 3:  # 리뷰가 너무 적으면 스킵
        continue
    
    # 해당 가게 TF-IDF
    place_tfidf = vectorizer.transform(place_reviews)
    place_scores = np.array(place_tfidf.sum(axis=0)).flatten()
    
    # 다른 가게들 TF-IDF  
    other_tfidf = vectorizer.transform(other_reviews)
    other_scores = np.array(other_tfidf.sum(axis=0)).flatten()
    
    # 특징도 계산 (해당가게점수 / 전체평균점수)
    total_scores = place_scores + other_scores
    distinctiveness = np.where(total_scores > 0, place_scores / (total_scores / len(places)), 0)
    
    # 상위 키워드 선별
    top_indices = distinctiveness.argsort()[-20:][::-1]
    
    for idx in top_indices:
        if place_scores[idx] > 0:  # 실제 해당 가게에서 사용된 단어만 가져오기
            place_keywords.append({
                'place_name': place,
                'keyword': feature_names[idx],
                'place_tfidf': place_scores[idx],
                'distinctiveness': distinctiveness[idx],
                'analysis_type': 'place_distinctive'
            })

# 데이터프라임 형태로 저장
place_tfidf_df = pd.DataFrame(place_keywords)
place_tfidf_df = place_tfidf_df.sort_values(['place_name', 'distinctiveness'], ascending=[True, False])

print(f"가게별 특징 키워드 생성: {len(place_tfidf_df)} 건")

# 감정 분석
print("감정 분석 중...")

# 감성 단어 사전
# 결과를 참고하여 여러번 보강함
positive_words = set([
    # 기본 긍정어
    '좋', '맛있', '최고', '훌륭', '완벽', '추천', '만족', '깨끗', '친절', '신선',
    '맛나', '맛좋', '맛집', '끝내주', '굿', '좋아', '사랑', '행복', '즐거', '가성비',
    '고소', '담백', '깔끔', '부드럽', '쫄깃', '바삭', '달콤', '향긋', '빨리', '냄새안',
    '환상', '예술', '일품', '감동', '놀랍', '대박', '인생',
    '풍부', '진하', '알맞', '든든', '포만', '정성', '센스',
    '푸짐', '넉넉', '양많', '신속', '빠르', '정갈', '위생', '세심',
    '고급', '프리미엄', '특별', '독특', '유니크', '차별', '새롭',
    '착한가격', '혜자', 

    # 추가 긍정어
    '최애', '재방문','적당','합리', '저렴','가성비','괜찮', '나쁘지않',
  
    # 추가
    '쾌적', '안질기', '짜지도안', '적합','강추','최곱'
])

negative_words = set([
    # 기본 부정어
    '맛없', '별로', '실망', '짜', '싱거', '늦', '불친절', '더럽',
    '비싸', '아쉽', '후회', '최악', '화나', '밍밍', '퍽퍽', '질기',
    '느리', '시끄럽', '불편', '차가', '식', '탔', '혼잡', '냄새나','루즈', '불결', 
    '과하', '심하', '낡', '허름',
    # 추가 부정어
    '그냥그래', '평범', '무난', '그저그', '쏘쏘', '애매',
    '작', '적', '부족', '모자라', '아깝',
    '지저분', '위생안', '오래됐',
    '무성의', '불만', '짜증', '황당', '어이없', '기대이하',
    '허술', '엉망', '개판', '조잡', '글쎄'
])

# 감성 분석에서 제외할 중립 단어들
neutral_exclude_words = set([
    # 음식 관련 중립어
    '식사', '식구', '회식', '후식', '외식', '음식', '폭식', 
    '짜장', '메뉴', '가게', '식당', '식', '음',
    '요리', '반찬', '밥', '국', '찌개', '전', '구이', '볶음',
    
    # 시설 관련 중립어
    '주차가능', '주차', '포장', '배달', '예약', '대기',
    
    # 크기/양 중립어
    '작', '적', '크', '많', '양',
    
    # 기타
    '생각', '느낌', '경우', '정도', '편', '시간', '장소','공짜','진짜'])


# 부정어 리스트
negation_words = {'안', '못', '없', '아니', '전혀', '결코', '비'}

# 강조어 가중치
intensifiers = {
    '너무': 1.5, '정말': 1.5, '진짜': 1.5, '완전': 1.5,
    '매우': 1.3, '아주': 1.3, '엄청': 1.5, '진심': 1.5,
    '최고로': 2.0, '극도로': 2.0, '극': 1.8, '되게': 1.3,
    '엄청나': 1.5, '완전히': 1.5, '정말로': 1.5
}

def analyze_sentiment(tokens_str):
    # 빈 문자열 처리
    try:
        import pandas as pd
    except Exception:
        pd = None

    if tokens_str is None:
        tokens_str = ""
    
    elif not isinstance(tokens_str, str):
        # NaN(float) 처리
        if pd is not None and isinstance(tokens_str, float) and pd.isna(tokens_str):
            tokens_str = ""
        # 리스트면 공백 조인
        elif isinstance(tokens_str, list):
            tokens_str = " ".join(tokens_str)
        else:
            tokens_str = str(tokens_str)

    # 쪼개기
    tokens = tokens_str.split()
    
    pos_score = 0
    neg_score = 0
    matched_pos = []
    matched_neg = []
    
    for i, token in enumerate(tokens):
        # 중립 단어 스킵
        if any(exclude in token for exclude in neutral_exclude_words):
            continue
        
        # 강도 및 부정어 확인
        intensity = 1.0 # 기본 감정 점수 : 1.0
        has_negation = False # 기본은 부정어가 아님
        if i > 0:
            prev_token = tokens[i-1] # 현재 단어 바로 앞 단어를 가져옴
            if prev_token in intensifiers: # 강조어가 있으면
                intensity = intensifiers[prev_token] # 해당 강도로 값을 바꿈
            if prev_token in negation_words: # 부정어가 있으면
                has_negation = True # 부정으로 구분분
        
        # 1순위: 감성사전 사용
        if USE_SENTIMENT_DICT and token in sentiment_dict:
            dict_pos, dict_neg = sentiment_dict[token]
            
            # 부정어 처리 (의미 반전)
            if has_negation:
                dict_pos, dict_neg = dict_neg, dict_pos
            
            # 점수 적용
            if dict_pos > dict_neg:
                pos_score += dict_pos * intensity
                matched_pos.append(token)
            elif dict_neg > dict_pos:
                neg_score += dict_neg * intensity
                matched_neg.append(token)
        
        # 2순위: 키워드 방식 (감성사전에 없을 때)
        else:
            is_positive = any(pw in token for pw in positive_words)
            is_negative = any(nw in token for nw in negative_words)

            # 긍정어 리스트에 있을 때
            if is_positive:
                if has_negation:
                    neg_score += intensity
                    matched_neg.append(f"{tokens[i-1]} {token}")
                else:
                    pos_score += intensity
                    matched_pos.append(token)

            # 부정어 리스트에 있을 때때
            elif is_negative:
                if has_negation:
                    pos_score += intensity
                    matched_pos.append(f"{tokens[i-1]} {token}")
                else:
                    neg_score += intensity
                    matched_neg.append(token)

    # 감정점수 식
    sentiment_score = pos_score - neg_score

    # 긍정어/부정어 구분분
    if sentiment_score > 0.5:
        return 'positive', pos_score, neg_score, matched_pos, matched_neg
    elif sentiment_score < -0.5:
        return 'negative', pos_score, neg_score, matched_pos, matched_neg
    else:
        return 'neutral', pos_score, neg_score, matched_pos, matched_neg

# 감정 분석 적용
sentiment_results = []
for idx, row in sentiment_df.iterrows():
    sentiment, pos_score, neg_score, matched_pos, matched_neg = analyze_sentiment(row['tokens_join'])
    sentiment_results.append({
        'place_name': row['place_name'],
        'sentiment': sentiment,
        'positive_score': round(pos_score, 2),  # score로 변경
        'negative_score': round(neg_score, 2),  # score로 변경
        'sentiment_score': round(pos_score - neg_score, 2),
        'matched_positive_words': ', '.join(matched_pos),
        'matched_negative_words': ', '.join(matched_neg)
    })

sent_df = pd.DataFrame(sentiment_results)

# 가게별 감정 요약
place_sentiment = sent_df.groupby('place_name').agg({
    'sentiment_score': ['mean', 'std', 'count'],
    'positive_score': 'sum',
    'negative_score': 'sum',
    'matched_positive_words': lambda x: ', '.join([w for w in x if w]),
    'matched_negative_words': lambda x: ', '.join([w for w in x if w])
}).round(3)

place_sentiment.columns = [
    'avg_sentiment_score', 'sentiment_std', 'review_count',
    'total_positive_score', 'total_negative_score',
    'all_positive_keywords', 'all_negative_keywords'
]

place_sentiment = place_sentiment.reset_index()

print(f"감정 분석 완료: {len(sent_df)} 리뷰")
print(f"긍정: {len(sent_df[sent_df['sentiment']=='positive'])} / "
      f"부정: {len(sent_df[sent_df['sentiment']=='negative'])} / "
      f"중립: {len(sent_df[sent_df['sentiment']=='neutral'])}")


# 결과 저장
print("태블로용 결과 파일 저장 중...")

# 파일명에 타임스탬프 추가
# 데이터 덮어씌여지기 방지
outputs = {
    f'tableau_global_keywords_{TS}.csv': global_tfidf_df,
    f'tableau_place_keywords_{TS}.csv': place_tfidf_df,
    f'tableau_sentiment_by_review_{TS}.csv': sent_df,
    f'tableau_sentiment_by_place_{TS}.csv': place_sentiment,
    # f'tableau_topic_words_{TS}.csv': topic_df,
    # f'tableau_review_topics_{TS}.csv': doc_topic_df,
    # f'tableau_place_topic_summary_{TS}.csv': place_topic_summary
}

saved_files = []
for filename, dataframe in outputs.items():
    filepath = BASE_DIR / filename
    dataframe.to_csv(filepath, index=False, encoding='utf-8-sig')
    saved_files.append(filename)
    print(f"  ✅ {filename}: {len(dataframe)} 행")

print("분석 완료! 태블로용 파일:")
for f in saved_files:
    print(f"  📁 {f}")

# 추가 데이터 생성(도구설명용)
import pandas as pd

# 데이터 고대로 가져오기
tmp = sent_df.copy()

# 문자열 -> 단어 리스트로 안전 변환
def split_words(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return []
    if isinstance(x, (list, set, tuple)):
        parts = list(x)
    else:
        parts = str(x).split(',')  # 콤마 기준 분리
    # 공백/빈값 제거
    parts = [p.strip() for p in parts if p and p.strip()]
    return parts

# place_name, word_info(positive/negative), words 형태로 변환
tmp = tmp.reset_index(drop=True)
tmp["review_number"] = tmp.index + 1
tmp = tmp[['place_name', 'review_number', 'matched_positive_words', 'matched_negative_words']]

rows = []
for _, r in tmp.iterrows():
    # 긍정 단어
    for w in split_words(r['matched_positive_words']):
        rows.append({
            'place_name': r['place_name'],
            'review_number': r['review_number'],
            'word_info': 'positive',
            'words': w
        })
    # 부정 단어
    for w in split_words(r['matched_negative_words']):
        rows.append({
            'place_name': r['place_name'],
            'review_number': r['review_number'],
            'word_info': 'negative',
            'words': w
        })

place_word_long = pd.DataFrame(rows)

# 중복 제거(원하면 유지해도 됨)
place_word_long = place_word_long.drop_duplicates()

# 저장
filename= 'place_word_long.csv'
filepath = BASE_DIR / filename
place_word_long.to_csv(filepath, index=False, encoding='utf-8-sig')
print(f'저장 완료 → {filepath}')
