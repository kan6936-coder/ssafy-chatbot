import os
import json
import feedparser
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv
from urllib.parse import quote
from datetime import datetime, timedelta
import re
from html.parser import HTMLParser

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
# HTML 태그 제거
# ===============================
class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.fed = []
    
    def handle_data(self, d):
        self.fed.append(d)
    
    def get_data(self):
        return ''.join(self.fed)

def strip_html(html):
    s = HTMLStripper()
    try:
        s.feed(html)
        return s.get_data()
    except:
        return html

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

def extract_article_content(article):
    """RSS에서 기사 본문 추출"""
    content = ""
    
    # 시도할 필드들 (우선순위 순서)
    sources = [
        article.get("content", [{}])[0].get("value", "") if article.get("content") else "",
        article.get("summary", ""),
        article.get("description", ""),
        article.get("summary_detail", {}).get("value", "") if article.get("summary_detail") else "",
    ]
    
    for source in sources:
        if source and len(source.strip()) > 20:
            content = strip_html(source)
            break
    
    # 본문이 여전히 짧으면 제목 포함
    if not content or len(content.strip()) < 30:
        content = f"{article.get('title', '')}. {content}"
    
    return content.strip()

def search_news(query, start=0, size=5):
    encoded_query = quote(query)
    all_articles = []
    
    try:
        feed_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(feed_url)
        if feed.entries:
            all_articles.extend(feed.entries[:20])
    except Exception as e:
        pass
    
    if not all_articles:
        return []
    
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
    
    if len(filtered_articles) < 2:
        filtered_articles = sorted(
            all_articles,
            key=lambda x: x.published_parsed if hasattr(x, 'published_parsed') else datetime.now().timetuple(),
            reverse=True
        )[:15]
    
    seen_titles = set()
    unique_articles = []
    for article in filtered_articles:
        title = article.get("title", "제목 없음")
        if title not in seen_titles:
            seen_titles.add(title)
            unique_articles.append(article)
    
    return unique_articles[start:start+size]

def summarize_article(text):
    """기사 본문을 3줄로 요약"""
    if not text or len(text.strip()) < 20:
        return "기사 본문을 가져올 수 없습니다."
    
    # 텍스트 길이 제한
    text_preview = text[:800]
    
    try:
        res = client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {"role": "system", "content": "너는 뉴스 기사를 정확하게 3줄로 핵심만 요약하는 AI다. 항상 3줄로만 정리해줘."},
                {"role": "user", "content": f"다음 기사를 3줄로 요약해줘:\n{text_preview}"}
            ],
            max_completion_tokens=256,
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        # 요약 실패 시 원본 텍스트의 처음 3줄 반환
        lines = text_preview.split('\n')[:3]
        return '\n'.join([line.strip() for line in lines if line.strip()])

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
        # 기사 본문 추출
        article_content = extract_article_content(article)
        
        # GPT로 3줄 요약
        summary = summarize_article(article_content)
        
        date_str = pub_date.strftime("%Y.%m.%d %H:%M")
        title = article.get("title", "[제목 없음]")
        link = article.get("link", "[링크 없음]")
        
        response += (
            f"{idx}. [{date_str}] {title}\n"
            f"{summary}\n"
            f" {link}\n\n"
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

    try:
        res = client.chat.completions.create(
            model="gpt-5-nano",
            messages=messages,
            max_completion_tokens=512,
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        return f"응답 생성 중 오류가 발생했습니다: {str(e)}"

# ===============================
# Streamlit UI
# ===============================
st.set_page_config(page_title="AI 챗봇 + 기사 검색", layout="centered")
st.title(" AI 챗봇 +  기사 검색")

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
