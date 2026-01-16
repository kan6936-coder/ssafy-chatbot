import os
import json
import streamlit as st
from openai import OpenAI
import feedparser
from urllib.parse import quote

MEMORY_FILE = "conversation.json"
API_KEY = os.environ.get("OPENAI_API_KEY")

if not API_KEY:
    st.error("OPENAI_API_KEY 필요")
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
    keywords = ["기사", "뉴스", "보도", "검색"]
    return any(k in user_input for k in keywords)

def search_news(query):
    try:
        encoded_query = quote(query)
        url = "https://news.google.com/rss/search?q=" + encoded_query + "&hl=ko&gl=KR&ceid=KR:ko"
        st.write("[DEBUG] 검색 URL: " + url)
        
        feed = feedparser.parse(url)
        st.write("[DEBUG] 피드 상태: " + str(feed.status))
        
        if not feed.entries:
            return None
        
        articles = []
        for entry in feed.entries[:3]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            summary = entry.get("summary", "")
            summary = summary.replace("<b>", "").replace("</b>", "").replace("<br>", " ")[:250]
            articles.append({"title": title, "link": link, "summary": summary})
        return articles
    except Exception as e:
        return None

def get_summary(title, text):
    try:
        prompt = "제목: " + title + "\n\n본문: " + text + "\n\n위 기사를 3줄로 요약해줘"
        res = client.chat.completions.create(
            model="gpt-5-nano",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=200,
        )
        return prompt, res.choices[0].message.content.strip()
    except Exception as e:
        return "", "오류: " + str(e)

def get_news_summary(user_input):
    articles = search_news(user_input)
    
    if articles is None:
        return "검색 중 오류 발생. 다시 시도해주세요."
    
    if not articles:
        return "검색 결과가 없습니다. 다른 키워드로 시도해주세요."
    
    result = ""
    for i, article in enumerate(articles, 1):
        result += "\n기사 " + str(i) + ": " + article['title'] + "\n"
        result += "본문: " + article['summary'] + "\n"
        prompt, summary = get_summary(article['title'], article['summary'])
        result += "\n프롬프트:\n" + prompt + "\n"
        result += "\n요약:\n" + summary + "\n"
        result += "\n링크: " + article['link'] + "\n"
        result += "===============\n"
    return result

def chatbot_response(history, user_input):
    messages = [{"role": "system", "content": "너는 친절한 AI다."}]
    for h in history[-5:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_input})
    try:
        res = client.chat.completions.create(
            model="gpt-5-nano",
            messages=messages,
            max_completion_tokens=500,
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        return "오류: " + str(e)

st.set_page_config(page_title="AI 챗봇", layout="wide")
st.title("AI 챗봇 + 기사 검색")

if "history" not in st.session_state:
    st.session_state.history = load_conversation()

for h in st.session_state.history:
    st.chat_message(h["role"]).write(h["content"])

user_input = st.chat_input("입력")

if user_input:
    st.chat_message("user").write(user_input)
    st.session_state.history.append({"role": "user", "content": user_input})
    
    with st.spinner("처리중..."):
        if is_news_request(user_input):
            response = get_news_summary(user_input)
        else:
            response = chatbot_response(st.session_state.history, user_input)
    
    st.chat_message("assistant").write(response)
    st.session_state.history.append({"role": "assistant", "content": response})
    save_conversation(st.session_state.history)
