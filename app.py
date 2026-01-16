import os
import json
import streamlit as st
from openai import OpenAI
import feedparser
from datetime import datetime, timedelta

MEMORY_FILE = "conversation.json"
API_KEY = os.environ.get("OPENAI_API_KEY")

if not API_KEY:
    st.error("OPENAI_API_KEY 환경변수 설정 필요")
    st.stop()

client = OpenAI(
    base_url="https://gms.ssafy.io/gmsapi/api.openai.com/v1",
    api_key=API_KEY
)

def load_conversation():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_conversation(history):
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except:
        pass

def is_news_request(user_input: str) -> bool:
    keywords = ["기사", "뉴스", "보도", "검색", "뉴스해줄", "기사해줄"]
    return any(k in user_input for k in keywords)

def search_news(query):
    """Google News RSS에서 기사 검색"""
    try:
        url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(url)
        
        articles = []
        for entry in feed.entries[:5]:
            try:
                title = entry.get("title", "제목 없음")
                link = entry.get("link", "")
                summary = entry.get("summary", "")
                
                # HTML 태그 제거
                summary = summary.replace("<b>", "").replace("</b>", "").replace("<br>", " ")
                summary = summary[:300]
                
                articles.append({
                    "title": title,
                    "summary": summary,
                    "link": link
                })
            except:
                continue
        
        return articles[:3] if articles else []
    except Exception as e:
        return []

def summarize_article(title, content):
    """기사 내용을 GPT로 3줄 요약"""
    try:
        prompt = f"다음 기사를 정확히 읽고 3줄로 요약해줘:\n\n[기사 제목]\n{title}\n\n[기사 본문]\n{content}"
        
        res = client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=300,
        )
        summary = res.choices[0].message.content.strip()
        return prompt, summary
    except Exception as e:
        return f"오류", f"요약 실패: {str(e)}"

def get_news_summary(user_input):
    """기사 검색 및 요약"""
    articles = search_news(user_input)
    
    if not articles:
        return "검색 결과가 없습니다."
    
    output = f"��� '{user_input}' 관련 기사 {len(articles)}개\n\n"
    
    for i, article in enumerate(articles, 1):
        output += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        output += f"[기사 {i}] {article['title']}\n"
        output += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        output += f"��� 본문:\n{article['summary']}\n\n"
        
        prompt, summary = summarize_article(article['title'], article['summary'])
        
        output += f"��� GPT 프롬프트:\n{prompt}\n\n"
        output += f"✅ 3줄 요약:\n{summary}\n\n"
        output += f"��� 링크: {article['link']}\n\n"
    
    return output

def chatbot_response(history, user_input):
    messages = [{"role": "system", "content": "너는 친절한 AI 챗봇이다."}]
    for h in history[-10:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_input})

    try:
        res = client.chat.completions.create(
            model="gpt-5-nano",
            messages=messages,
            max_completion_tokens=1024,
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        return f"응답 오류: {str(e)}"

st.set_page_config(page_title="AI 챗봇", layout="wide")
st.title("AI 챗봇 + 기사 검색")

if "history" not in st.session_state:
    st.session_state.history = load_conversation()

for h in st.session_state.history:
    st.chat_message(h["role"]).write(h["content"])

user_input = st.chat_input("메시지 입력")

if user_input:
    st.chat_message("user").write(user_input)
    st.session_state.history.append({"role": "user", "content": user_input})
    
    with st.spinner("처리 중..."):
        if is_news_request(user_input):
            response = get_news_summary(user_input)
        else:
            response = chatbot_response(st.session_state.history, user_input)
    
    st.chat_message("assistant").write(response)
    st.session_state.history.append({"role": "assistant", "content": response})
    save_conversation(st.session_state.history)
