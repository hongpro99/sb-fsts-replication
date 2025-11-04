# streamlit_app.py
# AI 뉴스분석용 -> 매수 전 실행, 종목 추천
import streamlit as st
import feedparser
import openai
import re
from datetime import datetime, date
from collections import Counter
from bs4 import BeautifulSoup
import requests
# ✅ OpenAI 설정
from openai import OpenAI
# 🔑 OpenAI API 키 설정
client = OpenAI(api_key = "OPENAI_API_KEY")

# ✅ 뉴스 수집 함수
def get_stock_news(query, max_results=10, only_today=False):
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(rss_url)
    news_items = []

    for entry in feed.entries:
        summary_cleaned = re.sub('<[^<]+?>', '', entry.summary)

        try:
            published_dt = datetime(*entry.published_parsed[:6])
            published_str = published_dt.strftime("%Y-%m-%d %H:%M")
        except:
            published_dt = None
            published_str = "날짜 정보 없음"

        news_items.append({
            "title": entry.title,
            "link": entry.link,
            "summary": summary_cleaned,
            "published": published_str,
            "published_dt": published_dt
        })

    # ✅ 오늘 뉴스만 필터링
    if only_today:
        today = date.today()
        news_items = [item for item in news_items
                    if item["published_dt"] and item["published_dt"].date() == today]

    # ✅ 최신순 정렬
    news_items.sort(key=lambda x: x["published_dt"] or datetime.min, reverse=True)

    return news_items[:max_results]

# ✅ 감성 추출 함수
def extract_sentiment(text):
    match = re.search(r"\[감성\]\s*(긍정|부정|중립)", text)
    return match.group(1) if match else "분류 실패"

# ✅ GPT 요약 및 감성 분석 함수
def summarize_news_with_gpt(title, content):
    prompt = f"""
다음은 주식 관련 뉴스입니다:

제목: {title}
내용: {content}

1.이 뉴스를 한 문단으로 요약해 주세요.
2.또한 이 뉴스가 투자자 입장에서 긍정적인지, 부정적인지, 중립적인지 판단해 주세요. (긍정/부정/중립 중 하나만 선택)
3.그렇게 판단한 이유를 간단히 설명해 주세요.

결과는 아래 형식으로 반환해 주세요:

[요약]
...

[감성]
긍정 / 부정 / 중립

[이유]
(감성 판단 이유 요약)
"""
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "당신은 주식 분석 전문가입니다."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )
    return response.choices[0].message.content

# ✅ 투자 의견 요약 함수
def generate_investment_opinion(news_summaries, stock_name):
    prompt = f"""
당신은 투자 전문가입니다. 아래는 '{stock_name}'에 대한 최근 뉴스 요약입니다:

{news_summaries}

이 종목의 최근의 뉴스 흐름과 감성을 기반으로 투자자에게 조언을 해 주세요.
'매수 고려 / 관망 / 리스크 주의' 중 하나로 판단하고, 그 이유를 간단히 설명해 주세요.

[투자 의견]
매수 고려 / 관망 / 리스크 주의 중 택 1

[이유]
(간단한 설명)
"""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "당신은 주식 분석 전문가입니다."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4
    )
    return response.choices[0].message.content

# ✅ Streamlit UI
st.title("📈 종목 뉴스 요약 & 감성 분석")
query = st.text_input("종목명을 입력하세요 (예: 삼성전자)")
only_today = st.checkbox("📅 오늘 뉴스만 보기")

if query:
    st.info(f'"{query}" 관련 뉴스를 수집하고 요약 중입니다...')
    news_list = get_stock_news(query, only_today=only_today)

    if not news_list:
        st.warning("오늘 날짜의 뉴스가 없습니다.")
    else:
        sentiment_counter = Counter()
        summarized_texts = []
        results = []

        for i, news in enumerate(news_list):
            with st.spinner("요약 및 분석 중..."):
                result = summarize_news_with_gpt(news["title"], news["summary"])
            sentiment = extract_sentiment(result)
            sentiment_counter[sentiment] += 1
            summarized_texts.append(f"- {news['title']}: {result}")
            results.append((news, result))

        # ✅ 감성 요약 표시
        st.markdown("## 📊 감성 분석 요약")
        st.write(f"👍 긍정: {sentiment_counter['긍정']}건")
        st.write(f"😐 중립: {sentiment_counter['중립']}건")
        st.write(f"👎 부정: {sentiment_counter['부정']}건")
        st.markdown("---")

        # ✅ GPT 투자 의견 표시
        with st.spinner("GPT가 투자 의견을 분석 중..."):
            opinion_result = generate_investment_opinion("\n".join(summarized_texts), query)

        st.markdown("## 🧠 GPT 투자 의견")
        st.success(opinion_result)
        st.markdown("---")

        # ✅ 뉴스 출력
        for i, (news, result) in enumerate(results):
            st.subheader(f"📰 뉴스 {i+1}: {news['title']}")
            st.caption(f"🗓 날짜: {news['published']}")
            st.write(f"[원문 링크]({news['link']})")
            st.write(result)
            
            
# ✅ 종목명 → 종목코드 매핑 (네이버 검색)
def get_stock_code(stock_name):
    url = f"https://search.naver.com/search.naver?query={stock_name}+주가"
    res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(res.text, "html.parser")
    try:
        href = soup.select_one("a[href*='finance.naver.com/item/main.naver?code=']")["href"]
        code = re.search(r'code=(\d+)', href).group(1)
        return code
    except:
        return None

def get_company_info(stock_code):
    url = f"https://finance.naver.com/item/main.nhn?code={stock_code}"
    res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(res.text, "html.parser")

    try:
        # ✅ 업종 정보
        industry_tag = soup.select_one("div.description span.category")
        industry = industry_tag.text.strip().replace(">", "›") if industry_tag else "정보 없음"

        # ✅ 재무 요약 테이블
        table = soup.select_one("table.tb_type1.tb_num.tb_type1_ifrs")
        rows = table.select("tr") if table else []

        finance_data = {}
        for row in rows:
            th = row.select_one("th")
            tds = row.select("td")
            if th and tds and len(tds) > 1:
                label = th.text.strip()
                value = tds[1].text.strip().replace('\xa0', '')
                finance_data[label] = value

        return {
            "industry": industry,
            "finance": finance_data
        }

    except Exception as e:
        print(f"에러: {e}")
        return None

def get_financial_data(stock_code):
    url = f"https://finance.naver.com/item/main.nhn?code={stock_code}"
    res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(res.text, "html.parser")

    table = soup.select_one("table.tb_type1.tb_num.tb_type1_ifrs")
    rows = table.select("tr") if table else []

    annual_data = {}
    quarterly_data = {}

    for row in rows:
        th = row.select_one("th")
        tds = row.select("td")
        if th and len(tds) >= 6:
            label = th.text.strip()
            annual_data[label] = tds[0].text.strip()
            quarterly_data[label] = tds[3].text.strip()

    return annual_data, quarterly_data

def analyze_financials_with_gpt(fin_data, stock_name, period_label):
    summary = "\n".join([f"{k}: {v}" for k, v in fin_data.items()])

    prompt = f"""
다음은 {stock_name}의 {period_label} 재무 정보입니다.

{summary}

이 재무정보를 바탕으로 투자자의 시각에서 요약 분석해 주세요.
- 수익성, 성장성, 안정성 관점에서 간단히 평가
- 전문용어는 줄이고 쉽게 설명
- 길이는 5~6줄 이내
"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "당신은 주식 재무 분석 전문가입니다."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )
    return response.choices[0].message.content


# ✅ Streamlit UI
st.title("📊 종목 리서치 리포트 (업종, 재무, GPT 분석)")
stock_name = st.text_input("분석할 종목명을 입력하세요 (예: 삼성전자)")

if stock_name:
    st.info("종목 정보를 불러오는 중입니다...")
    code = get_stock_code(stock_name)
    if not code:
        st.error("종목 코드를 찾을 수 없습니다.")
    else:
        info = get_company_info(code)
        if not info:
            st.error("네이버 금융에서 정보를 불러오지 못했습니다.")
        else:
            st.success("✅ 종목 분석 결과")

            st.subheader(f"🔍 [요약 보고서: {stock_name}]")
            # st.write(f"**📂 업종:** {info['industry']}")
            #st.write(f"**📌 테마:** {info['theme']}")

            st.markdown("### 💰 [재무 요약]")
            for k, v in info["finance"].items():
                st.write(f"- {k}: {v}")

            # with st.spinner("GPT가 재무 분석 중..."):
            #     gpt_opinion = analyze_financials_with_gpt(info["finance"], stock_name)

            # st.markdown("### 🧠 [GPT 재무 분석]")
            # st.success(gpt_opinion)
            
    annual, quarterly = get_financial_data(code)
    
        # 연간 실적
    st.subheader("📅 최근 연간 실적")
    for k, v in annual.items():
        st.write(f"- {k}: {v}")

    with st.spinner("GPT가 연간 실적을 분석 중입니다..."):
        gpt_annual = analyze_financials_with_gpt(annual, stock_name, "연간")
    st.markdown("🧠 GPT 연간 실적 분석")
    st.success(gpt_annual)

    # 분기 실적
    st.subheader("📅 최근 분기 실적")
    for k, v in quarterly.items():
        st.write(f"- {k}: {v}")

    with st.spinner("GPT가 분기 실적을 분석 중입니다..."):
        gpt_quarter = analyze_financials_with_gpt(quarterly, stock_name, "분기")
    st.markdown("🧠 GPT 분기 실적 분석")
    st.success(gpt_quarter)
            
