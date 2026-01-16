import os
import json
import streamlit as st
from openai import OpenAI

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

def get_news_summary(user_input):
    try:
        res = client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {"role": "system", "content": "너는 최근 뉴스를 정리하는 AI다. 사용자가 요청한 주제의 최근 뉴스 3개를 각각 3줄씩 요약해줘."},
                {"role": "user", "content": f"{user_input}에 대한 최근 뉴스 3개"}
            ],
            max_completion_tokens=1024,
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        return f"기사 검색 오류: {str(e)}"

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

st.set_page_config(page_title="AI 챗봇", layout="centered")
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
