import os
import json
import feedparser
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv
from urllib.parse import quote
from datetime import datetime, timedelta

# ===============================
# 환경 설정
# ===============================
load_dotenv()

if not os.environ.get("OPENAI_API_KEY"):
    st.error("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
    st.stop()

client = OpenAI(
    base_url="https://gms.ssafy.io/gmsapi/api.openai.com/v1"
)

MEMORY_FILE = "conversation.json"

# ===============================
# 대화 기록 관리
# ===============================
def load_conversation():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_conversation(history):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

# ===============================
# 기사 검색 기능 (의도 판단 포함)
# ===============================
def is_news_request(user_input: str) -> bool:
    keywords = ["기사", "뉴스", "보도", "검색"]
    return any(k in user_input for k in keywords)

def search_news(query, start=0, size=5):
    encoded_query = quote(query)
    all_articles = []
    try:
        feed_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(feed_url)
        all_articles.extend(feed.entries[:15])
    except:
        pass
    
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    filtered_articles = []
    for article in all_articles:
        try:
            if hasattr(article, 'published_parsed') and article.published_parsed:
                article_date = datetime(*article.published_parsed[:6]).date()
                if article_date in [yesterday, today]:
                    filtered_articles.append(article)
        except:
            filtered_articles.append(article)
    
    if len(filtered_articles) < 3:
        filtered_articles = sorted(all_articles, key=lambda x: x.published_parsed if hasattr(x, 'published_parsed') else datetime.now().timetuple(), reverse=True)
    
    seen_titles = set()
    unique_articles = []
    for article in filtered_articles:
        if article.title not in seen_titles:
            seen_titles.add(article.title)
            unique_articles.append(article)
    
    return unique_articles[start:start+size]

def summarize_article(text):
    res = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[
            {"role": "system", "content": "너는 뉴스 기사를 정확하게 3줄로 핵심만 요약하는 AI다. 항상 3줄로만 정리해줘."},
            {"role": "user", "content": f"다음 기사를 3줄로 요약해줘:\n{text}"}
        ],
        max_completion_tokens=256,
    )
    return res.choices[0].message.content.strip()

def handle_news_request(user_input, offset):
    articles = search_news(user_input, offset)

    if not articles:
        return "검색 결과가 없습니다.\n다른 키워드로 검색해보세요."

    articles_with_date = []
    for article in articles:
        try:
            if hasattr(article, 'published_parsed') and article.published_parsed:
                pub_date = datetime(*article.published_parsed[:6])
            else:
                pub_date = datetime.now()
        except:
            pub_date = datetime.now()
        
        articles_with_date.append((pub_date, article))
    
    articles_with_date.sort(key=lambda x: x[0], reverse=True)

    response = ""
    for idx, (pub_date, article) in enumerate(articles_with_date, start=1):
        article_content = article.get("summary", "") or article.get("title", "")
        summary = summarize_article(article_content)
        date_str = pub_date.strftime("%Y.%m.%d %H:%M")
        response += (
            f"{idx}. [{date_str}] {article.title}\n"
            f"{summary}\n"
            f"��� {article.link}\n\n"
        )

    return response

# ===============================
# 기본 챗봇 기능
# ===============================
def chatbot_response(history, user_input):
    messages = [{"role": "system", "content": "너는 일반적인 인공지능 챗봇이다."}]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_input})

    res = client.chat.completions.create(
        model="gpt-5-nano",
        messages=messages,
        max_completion_tokens=512,
    )
    return res.choices[0].message.content.strip()

# ===============================
# Streamlit UI
# ===============================
st.set_page_config(page_title="AI 챗봇 + 기사 검색", layout="centered")
st.title("��� AI 챗봇 + ��� 기사 검색")

if "history" not in st.session_state:
    st.session_state.history = load_conversation()
if "news_offset" not in st.session_state:
    st.session_state.news_offset = 0

for h in st.session_state.history:
    st.chat_message(h["role"]).write(h["content"])

user_input = st.chat_input("메시지를 입력하세요")

if user_input:
    st.chat_message("user").write(user_input)
    st.session_state.history.append({"role": "user", "content": user_input})

    if is_news_request(user_input):
        response = handle_news_request(user_input, st.session_state.news_offset)
        st.session_state.news_offset += 5
    else:
        response = chatbot_response(st.session_state.history, user_input)
        st.session_state.news_offset = 0

    st.chat_message("assistant").write(response)
    st.session_state.history.append({"role": "assistant", "content": response})

    save_conversation(st.session_state.history)
