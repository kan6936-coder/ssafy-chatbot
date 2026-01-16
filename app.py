import os
import json
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime

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
    keywords = ["기사", "뉴스", "보도", "검색", "뉴스해줄", "기사해줄"]
    return any(k in user_input for k in keywords)

def get_news_summary(user_input):
    """GPT에게 직접 기사 내용 요약 요청"""
    try:
        res = client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {
                    "role": "system",
                    "content": "너는 최근 뉴스를 정리해서 알려주는 AI다. 사용자가 요청한 주제에 대해 최근 뉴스 3개를 각각 3줄씩 요약해서 보여줘. 형식: [1번 뉴스 제목] 3줄 요약 / [2번 뉴스 제목] 3줄 요약 / [3번 뉴스 제목] 3줄 요약"
                },
                {
                    "role": "user",
                    "content": f"'{user_input}'에 대한 최근 뉴스 3개를 각각 3줄로 요약해줄 수 있어?"
                }
            ],
            max_completion_tokens=512,
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        return f"기사 검색 중 오류가 발생했습니다: {str(e)}"

# ===============================
# 기본 챗봇 기능
# ===============================
def chatbot_response(history, user_input):
    """일반 챗봇 응답 생성 (문맥 유지)"""
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

# 이전 대화 출력
for h in st.session_state.history:
    st.chat_message(h["role"]).write(h["content"])

# 입력창
user_input = st.chat_input("메시지를 입력하세요")

if user_input:
    st.chat_message("user").write(user_input)
    st.session_state.history.append({"role": "user", "content": user_input})

    # 기사 검색 의도 판단
    if is_news_request(user_input):
        response = get_news_summary(user_input)
    else:
        response = chatbot_response(st.session_state.history, user_input)

    st.chat_message("assistant").write(response)
    st.session_state.history.append({"role": "assistant", "content": response})

    # 로컬 파일에 대화 저장
    save_conversation(st.session_state.history)
