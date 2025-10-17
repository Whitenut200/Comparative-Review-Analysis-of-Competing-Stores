<h1 align="center">경쟁가게 리뷰 비교분석 대시보드</h1>

<!-- <p align="center">
  <img src="AB-test-with-Retail-Rocket-data-CTV.jpg" alt="CTV 대시보드" width="30%"/>
  <img src="AB-test-with-Retail-Rocket-data-Funnel.jpg" alt="Path 대시보드" width="30%"/>
  <img src="AB-test-with-Retail-Rocket-data-path.jpg" alt="Path 대시보드" width="30%"/>
</p> -->


## 프로젝트 개요
‘와우솥뚜껑삼겹살(주 가게)’과 인근 경쟁 가게의 리뷰 데이터를 분석하여 **주 가게의 문제점과 강점, 차별화 포인트를 도출**하기 위한 프로젝트입니다.
네이버지도에서 수집한 리뷰 데이터를 기반으로 **다양한 지표를 산출하고**,  이를 **Tableau 대시보드로 시각화**하여 인사이트를 직관적으로 확인할 수 있도록 구현했습니다.

---

## 프로젝트 주제
- **주제:** 주 가게와 경쟁 가게의 네이버 리뷰를 비교하여 문제점과 경쟁력/차별화 포인트를 도출하자
- **기간:** 총 3주  
  - **데이터 수집 및 전처리**: 1.2주  
  - **분석**: 1주  
  - **Tableau 대시보드 제작 및 디자인**: 0.8주  
- **기여도:** 100% (기획 → 데이터 수집 → 전처리 → 분석 → 시각화 전 과정 단독 수행)

---

## 데이터
- 네이버지도에서 ‘와우솥뚜껑삼겹살(주 가게)’과 **가장 가까운 동일 업종 가게 7곳**을 선정하여 Python으로 리뷰 데이터를 크롤링하였습니다.

**수집 데이터 항목**
- 업체명  
- 주소  
- 메뉴명  
- 검색순위  
- 리뷰 수 (방문자 리뷰, 블로그 리뷰)  
- 간단 리뷰 수  
- 텍스트 리뷰 (리뷰 내용, 방문일, 방문 횟수 등)

---

## 프로젝트 진행 과정
1. **데이터 수집** – Python으로 네이버지도 리뷰 데이터 크롤링  
2. **데이터 전처리** – 불필요한 정보 제거 및 텍스트 정제  
3. **분석 단계** – 긍정어/부정어 감정 점수 산출, 특이도 분석, 단어 빈도 분석  
4. **시각화 (Tableau)** – 주요 인사이트를 시각화한 대시보드 제작  

---
## 주요 특징
- 실제 데이터에 **가상의 A/B 테스트 환경**을 구성해 분석 수행  
- **SQL**로 지표 산출, **Python**으로 가설검정, **Tableau**로 시각화 진행  
- **주요 지표**: N일 이내 구매 전환율 (CTV)  
- **보조 지표**:  
  - Path 전환율 (Direct: view→purchase, ViaCart: view→cart→purchase)  
  - Funnel 전환율 (view→cart, cart→purchase)  
- **대시보드 구성**: 총 3개 페이지 (CTV, Path, Funnel)  

---

## 사용 기술 스택
- **언어**: Python  
- **시각화 도구**: Tableau  

---

## 리뷰 데이터를 활용한 이유
- 매출 데이터 등 민감한 상업 정보는 접근이 어려움  
- 리뷰 데이터는 네이버/구글 등 **공개 접근이 용이**  
- 실제 고객의 의견을 반영하므로 **경쟁 분석 지표로 활용 가치 높음**

---

<!-- ## 결과물 확인
- **GitHub 블로그**: [Retail Rocket ABtest 대시보드](https://whitenut200.github.io/prodject/retail%20rocket/RetailRocketABtest-%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8%EA%B0%9C%EC%9A%94/)
- **Tableau Public**: [Tableau 대시보드](https://public.tableau.com/app/profile/yu.siyeon/viz/ABtestwithRetailRocketdata/CVR)
-->


---
**태블로 사진, 결과물 링크, 산출 지표 정보 추가**
