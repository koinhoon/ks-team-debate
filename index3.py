import streamlit as st
import openai
import json
import re
from datetime import datetime
import os
from typing import List, Tuple, Iterator
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.team.team import Team
from agno.tools.reasoning import ReasoningTools
from agno.run.response import RunResponse
from agno.tools.googlesearch import GoogleSearchTools
import streamlit_authenticator as stauth
from supabase import create_client, Client

# 환경 변수 로드
load_dotenv()

# Page config
st.set_page_config(page_title="팀토론 시뮬레이터", page_icon="💬", layout="wide")

# ======================== 인증 시스템 ========================
# Authentication setup using environment variables for streamlit-authenticator 0.1.5
# Get credentials from environment variables (supports both local .env and Streamlit Cloud secrets)
try:
    # Try Streamlit Cloud secrets first, then fallback to environment variables
    auth_username = st.secrets.get("AUTH_USERNAME", os.getenv("AUTH_USERNAME", "YOUR-ID"))
    auth_password = st.secrets.get("AUTH_PASSWORD", os.getenv("AUTH_PASSWORD", "YOUR-PASSWORD"))
    auth_name = st.secrets.get("AUTH_NAME", os.getenv("AUTH_NAME", "KS"))
except Exception:
    # Fallback to environment variables only (for local development)
    auth_username = os.getenv("AUTH_USERNAME", "YOUR-ID")
    auth_password = os.getenv("AUTH_PASSWORD", "YOUR-PASSWORD")
    auth_name = os.getenv("AUTH_NAME", "YOUR-NAME")

names = [auth_name]
usernames = [auth_username]
passwords = [auth_password]
hashed_passwords = stauth.Hasher(passwords).generate()

# authenticator 생성
authenticator = stauth.Authenticate(
    names,
    usernames,
    hashed_passwords,
    'ks_auth_cookie',
    'ks_auth_key'
)

# 로그인 처리
name, authentication_status, username = authenticator.login('KS 시뮬레이터 로그인', 'main')

if authentication_status == False:
    st.error('사용자명/비밀번호가 올바르지 않습니다.')
    st.stop()
elif authentication_status == None:
    st.warning('사용자명과 비밀번호를 입력해주세요.')
    st.stop()

# 인증 성공 시만 앱 실행
st.success(f'{name}님, 환영합니다!')

# ======================== 환경설정 및 DB 연결 ========================

# Supabase configuration - session state 초기화
if 'supabase_url' not in st.session_state:
    st.session_state.supabase_url = os.getenv('SUPABASE_URL', '')
if 'supabase_anon_key' not in st.session_state:
    st.session_state.supabase_anon_key = os.getenv('SUPABASE_ANON_KEY', '')
if 'supabase_client' not in st.session_state:
    st.session_state.supabase_client = None

def init_supabase_from_env():
    """환경변수에서 Supabase 설정을 읽어 자동 연결"""
    url = os.getenv('SUPABASE_URL') or st.secrets.get('SUPABASE_URL')
    key = os.getenv('SUPABASE_ANON_KEY') or st.secrets.get('SUPABASE_ANON_KEY')
    
    if url and key and not st.session_state.supabase_client:
        try:
            st.session_state.supabase_client = create_client(url, key)
            st.session_state.supabase_url = url
            st.session_state.supabase_anon_key = key
            return True
        except Exception as e:
            st.error(f"환경변수로 데이터베이스 자동 연결 실패: {str(e)}")
            return False
    return False

# 환경변수 기반 자동 연결 시도
auto_connected = init_supabase_from_env()

def init_supabase():
    """Supabase 클라이언트 초기화 UI (필요시)"""
    # 환경변수에서 Supabase 설정 가져오기
    supabase_url = os.getenv('SUPABASE_URL') or st.secrets.get('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_ANON_KEY') or st.secrets.get('SUPABASE_ANON_KEY')
    
    env_detected = bool(supabase_url and supabase_key)
    
    with st.sidebar:
        st.subheader("🔧 데이터베이스 설정")
        
        if env_detected:
            st.info("💡 환경변수에서 설정을 감지했습니다.")
            if auto_connected:
                st.success("✅ 자동으로 연결되었습니다!")
            else:
                if st.button("환경변수로 재연결 시도"):
                    if init_supabase_from_env():
                        st.success("연결 성공!")
                        st.rerun()
        else:
            st.warning("⚠️ 환경변수가 설정되지 않았습니다")
            
            # 수동 설정
            manual_url = st.text_input("Supabase URL", placeholder="https://your-project.supabase.co")
            manual_key = st.text_input("Supabase Anon Key", type="password")
            
            if st.button("수동 연결"):
                if manual_url and manual_key:
                    try:
                        client = create_client(manual_url, manual_key)
                        st.session_state.supabase_client = client
                        st.success("✅ Supabase에 연결되었습니다!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"연결 실패: {str(e)}")
                else:
                    st.error("URL과 Key를 모두 입력해주세요")

# Supabase 초기화 (자동 연결이 실패한 경우에만 UI 표시)
if 'supabase_client' not in st.session_state or not st.session_state.supabase_client:
    if not auto_connected:
        init_supabase()
    if 'supabase_client' not in st.session_state or not st.session_state.supabase_client:
        st.warning("데이터베이스에 연결해주세요")
        st.stop()

# Session state 초기화
if 'selected_participants' not in st.session_state:
    st.session_state.selected_participants = []
if 'participant_order' not in st.session_state:
    st.session_state.participant_order = []
if 'reasoning_depth' not in st.session_state:
    st.session_state.reasoning_depth = "보통"
if 'team_mode' not in st.session_state:
    st.session_state.team_mode = "개인의견 취합"
if 'subject_seq' not in st.session_state:
    st.session_state.subject_seq = 1
if 'subject_seq_initialized' not in st.session_state:
    st.session_state.subject_seq_initialized = False
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'preliminary_info' not in st.session_state:
    st.session_state.preliminary_info = ""
if 'topic' not in st.session_state:
    st.session_state.topic = ""
if 'discussion_content' not in st.session_state:
    st.session_state.discussion_content = ""
if 'is_chat_started' not in st.session_state:
    st.session_state.is_chat_started = False
if 'editing_participant' not in st.session_state:
    st.session_state.editing_participant = None
if 'agent_frameworks' not in st.session_state:
    st.session_state.agent_frameworks = {}

# Database initialization
def init_database():
    """데이터베이스 테이블 확인 (Supabase에서는 이미 생성됨)"""
    if 'supabase_client' not in st.session_state:
        st.error("데이터베이스에 연결되지 않았습니다.")
        return False
    
    try:
        # team_leads 테이블 존재 확인
        response = st.session_state.supabase_client.table('team_leads').select('*').limit(1).execute()
        return True
    except Exception as e:
        st.error(f"데이터베이스 테이블 확인 실패: {str(e)}")
        return False

def add_team_lead(name: str, role: str, personality: str, strategic_focus: str):
    """team_leads 테이블에 데이터 추가"""
    if 'supabase_client' not in st.session_state:
        st.error("데이터베이스에 연결되지 않았습니다.")
        return False
    
    try:
        response = st.session_state.supabase_client.table('team_leads').insert({
            'name': name,
            'role': role,
            'personality': personality,
            'strategic_focus': strategic_focus
        }).execute()
        return True
    except Exception as e:
        st.error(f"팀장 데이터 추가 실패: {str(e)}")
        return False

def clear_team_leads():
    """team_leads 테이블 데이터 초기화"""
    if 'supabase_client' not in st.session_state:
        st.error("데이터베이스에 연결되지 않았습니다.")
        return False
    
    try:
        # 모든 team_leads 데이터 삭제
        response = st.session_state.supabase_client.table('team_leads').delete().neq('id', 0).execute()
        return True
    except Exception as e:
        st.error(f"팀장 데이터 초기화 실패: {str(e)}")
        return False

# 샘플 데이터 삽입 함수는 index3.py에서 제거됨 (사용자 요청에 따라)
# index.py의 team_leads 테이블을 공유하여 사용

def get_team_leads():
    """team_leads 테이블에서 모든 데이터 가져오기"""
    if 'supabase_client' not in st.session_state:
        st.error("데이터베이스에 연결되지 않았습니다.")
        return []
    
    try:
        response = st.session_state.supabase_client.table('team_leads')\
            .select('id, name, role, personality, strategic_focus')\
            .order('id')\
            .execute()
        
        # 튜플 형태로 반환 (기존 SQLite 형식과 동일)
        return [(row['id'], row['name'], row['role'], row['personality'], row['strategic_focus']) 
                for row in response.data]
    except Exception as e:
        st.error(f"팀장 데이터 조회 실패: {str(e)}")
        return []

def get_team_lead_by_name(name: str):
    """이름으로 특정 team_lead 정보 가져오기"""
    if 'supabase_client' not in st.session_state:
        st.error("데이터베이스에 연결되지 않았습니다.")
        return None
    
    try:
        response = st.session_state.supabase_client.table('team_leads')\
            .select('id, name, role, personality, strategic_focus')\
            .eq('name', name)\
            .execute()
        
        if response.data:
            row = response.data[0]
            return (row['id'], row['name'], row['role'], row['personality'], row['strategic_focus'])
        return None
    except Exception as e:
        st.error(f"팀장 정보 조회 실패: {str(e)}")
        return None

def update_team_lead(lead_id: int, name: str, role: str, personality: str, strategic_focus: str):
    """team_leads 테이블 정보 업데이트"""
    if 'supabase_client' not in st.session_state:
        st.error("데이터베이스에 연결되지 않았습니다.")
        return False
    
    try:
        response = st.session_state.supabase_client.table('team_leads')\
            .update({
                'name': name,
                'role': role,
                'personality': personality,
                'strategic_focus': strategic_focus
            })\
            .eq('id', lead_id)\
            .execute()
        return True
    except Exception as e:
        st.error(f"팀장 정보 업데이트 실패: {str(e)}")
        return False

def get_last_subject_seq() -> int:
    """마지막 subject_seq 반환"""
    if 'supabase_client' not in st.session_state:
        st.error("데이터베이스에 연결되지 않았습니다.")
        return 0
    
    try:
        # subject_talk 테이블이 존재하지 않을 수 있으므로 생성 필요
        # 우선 간단히 0을 반환하고 필요시 테이블 생성 로직 추가
        response = st.session_state.supabase_client.table('subject_talk')\
            .select('subject_seq')\
            .order('subject_seq', desc=True)\
            .limit(1)\
            .execute()
        
        if response.data:
            return response.data[0]['subject_seq']
        return 0
    except Exception as e:
        # 테이블이 없을 경우 0 반환
        return 0

def save_conversation(subject_title: str, subject_seq: int, talk_seq: int, from_to: str, content: str):
    """대화 내용을 데이터베이스에 저장"""
    if 'supabase_client' not in st.session_state:
        st.error("데이터베이스에 연결되지 않았습니다.")
        return False
    
    try:
        response = st.session_state.supabase_client.table('subject_talk').insert({
            'subject_title': subject_title,
            'subject_seq': subject_seq,
            'talk_seq': talk_seq,
            'from_to': from_to,
            'talk_history': content
        }).execute()
        return True
    except Exception as e:
        st.error(f"대화 저장 실패: {str(e)}")
        return False

def get_conversation_history(subject_seq: int) -> List[Tuple]:
    """대화 내역 가져오기"""
    if 'supabase_client' not in st.session_state:
        st.error("데이터베이스에 연결되지 않았습니다.")
        return []
    
    try:
        response = st.session_state.supabase_client.table('subject_talk')\
            .select('from_to, talk_history')\
            .eq('subject_seq', subject_seq)\
            .order('talk_seq')\
            .execute()
        
        # 튜플 형태로 반환 (기존 SQLite 형식과 동일)
        return [(row['from_to'], row['talk_history']) for row in response.data]
    except Exception as e:
        st.error(f"대화 내역 조회 실패: {str(e)}")
        return []

def get_next_talk_seq(subject_seq: int) -> int:
    """다음 talk_seq 값 계산"""
    if 'supabase_client' not in st.session_state:
        st.error("데이터베이스에 연결되지 않았습니다.")
        return 1
    
    try:
        response = st.session_state.supabase_client.table('subject_talk')\
            .select('talk_seq')\
            .eq('subject_seq', subject_seq)\
            .order('talk_seq', desc=True)\
            .limit(1)\
            .execute()
        
        if response.data:
            return response.data[0]['talk_seq'] + 1
        return 1
    except Exception as e:
        # 테이블이 없거나 오류가 발생한 경우 1 반환
        return 1

# Agno Framework 관련 함수들

def build_depth_instruction(depth: str) -> List[str]:
    """추론 깊이에 따른 지시사항 생성"""
    if depth == "낮음":
        return [
            "*** 검색,추론 깊이: LOW ***",
            "1분 이내로 답변할 수 있는 수준의 간단한 조사만 수행합니다.",
            "복잡한 분석이나 다각도 비교는 하지 않습니다.",
            "웹 검색은 최대 1회만 허용하며, 검색 없이 기존 지식으로 답변 가능한 경우 검색을 생략합니다.",
            "결과는 핵심 요점 2개 이내의 불릿으로만 작성하고, 각 불릿은 1줄을 넘지 않습니다.",
            "출처는 반드시 1개만 간단히 제시하며, 없을 경우 '출처 없음'으로 표기합니다.",
            "불확실한 내용은 '추정'으로 표시하고, 추가 조사는 제안하지 않습니다.",
            "모든 출력은 한국어로 간결하게 작성합니다."
        ]
    elif depth == "보통":
        return [
            "*** 검색,추론 깊이: MID ***",
            "정확성과 속도의 균형을 유지합니다. 핵심 쟁점을 정리하고 필요 시 3~5개 출처를 탐색합니다.",
            "상반된 정보가 있을 때는 간단 비교(2~4줄) 후 합리적 결론을 제시합니다.",
            "결과 구조: 요약(3~5줄) → 근거(불릿 3~6개) → 간단한 리스크/대안(불릿 1~3개) → 참고출처(2~3개, 최신순)",
            "수치/날짜 등은 가능한 한 명시적으로 제시합니다.",
            "모든 출력은 한국어로 명확하고 읽기 쉽게 작성하세요."
        ]
    # default: 깊게
    return [
        "*** 검색,추론 깊이: HIGH ***",
        "철저한 검증과 포괄적 탐색을 수행합니다. 상이한 관점과 최신 동향을 교차 확인합니다.",
        "6~10개 내외의 신뢰도 높은 출처를 검토하고, 핵심/반대 근거를 구분해 제시합니다.",
        "결과 구조: 실행요약(5~8줄) → 상세 분석(섹션별로 정리) → 가정/제약 → 리스크/완화전략 → 권고안 → 참고출처(정확한 표기, 최신성 우선)",
        "수치, 방법론, 한계를 명시하고, 데이터 출처의 신뢰성과 업데이트 날짜를 강조합니다.",
        "모든 출력은 한국어로 전문적이고 체계적으로 작성하세요."
    ]

def build_team_mode_instructions(mode: str, depth: str) -> List[str]:
    """팀 모드에 따른 지시사항 생성"""
    if mode == "개인의견 취합":
        base_instructions = [
            "리더는 문제를 하위 과업으로 분해하고 각 에이전트의 전문성에 맞게 역할을 배정합니다.",
            "각 에이전트는 배정된 과업을 독립적으로 수행하고, 결과를 간결한 요약(핵심 3~5개 불릿)과 근거/출처와 함께 제출합니다.",
            "에이전트 간 직접 토론은 최소화하고, 필요한 경우 리더의 요청에만 응답해 보완합니다.",
            "리더는 모든 산출물을 통합하여 최종 보고서를 작성합니다: 실행요약 → 세부결과(에이전트별 섹션) → 리스크/대안 → 결론.",
            "수치·날짜·출처는 명시적으로 기재하고, 최신성과 신뢰도를 확인합니다.",
            "모든 사고과정 및 내용은 한국어로 작성합니다.",
        ]
    else:  # 상호토론
        base_instructions = [
            "각 에이전트는 자신의 역할 관점에서 1차 입장을 제시합니다(핵심 주장/근거/우려).",
            "상반된 주장이 있을 경우, 최대 3라운드까지 반박·재반박을 수행하되, 매 라운드마다 합의 가능 지점을 식별합니다.",
            "합의가 어려운 항목은 가정/전제 차이를 명시하고, 트레이드오프에 대한 절충안을 제시합니다.",
            "최종 단계에서 팀은 공동 결론을 작성합니다: 실행요약(5~8줄) → 합의사항 → 이견/가정 → 권고안 → 후속 액션.",
            "수치·날짜·출처는 명시적으로 기재하고, 최신성과 신뢰도를 확인합니다.",
            "모든 사고과정 및 내용은 한국어로 작성합니다.",
        ]

    # depth별 추가 지침
    depth_instructions = {
        "낮음": "간략하고 핵심적인 정보만을 바탕으로 답변합니다. 불필요한 세부사항은 생략하며, 2~3문장 내에서 결론 위주로 작성하세요.",
        "보통": "핵심 정보와 필수적인 배경 설명을 포함하여 답변합니다. 결론은 명확히 하고, 필요 시 간단한 예시나 비교를 덧붙입니다.",
        "깊게": "가능한 모든 세부 정보와 근거를 포함하여 심층적으로 분석합니다. 다양한 관점과 예시를 포함하고, 관련 통계나 데이터가 있으면 함께 제시하세요.",
    }

    return base_instructions + [depth_instructions.get(depth, "")]

# Agent 사고 프레임 텍스트
# --- Agent 사고 프레임 텍스트 ---
FRAMEWORKS_TEXT = {
    "none": "",
    "gi": """
## 1. 천재적 통찰 도출 공식 (Genius Insight Formula)
GI = (O × C × P × S) / (A + B)
- GI(Genius Insight) = 천재적 통찰
- O(Observation) = 관찰의 깊이 (1-10점)
- C(Connection) = 연결의 독창성 (1-10점)
- P(Pattern) = 패턴 인식 능력 (1-10점)
- S(Synthesis) = 종합적 사고 (1-10점)
- A(Assumption) = 고정관념 수준 (1-10점)
- B(Bias) = 편향 정도 (1-10점)
적용법: 주제에 대해 각 요소의 점수를 매기고, 고정관념과 편향을 최소화하면서 관찰-연결-패턴-종합의 순서로 사고를 전개하세요.
""",
    "mda": """
## 2. 다차원적 분석 프레임워크
MDA = Σ[Di × Wi × Ii] (i=1 to n)
- MDA(Multi-Dimensional Analysis) = 다차원 분석 결과
- Di(Dimension i) = i번째 차원에서의 통찰
- Wi(Weight i) = i번째 차원의 가중치
- Ii(Impact i) = i번째 차원의 영향력
분석 차원 설정:
- D1 = 시간적 차원 (과거-현재-미래)
- D2 = 공간적 차원 (로컬-글로벌-우주적)
- D3 = 추상적 차원 (구체-중간-추상)
- D4 = 인과적 차원 (원인-과정-결과)
- D5 = 계층적 차원 (미시-중간-거시)
""",
    "cc": """
## 3. 창의적 연결 매트릭스
CC = |A ∩ B| + |A ⊕ B| + f(A→B)
- CC(Creative Connection) = 창의적 연결 지수
- A ∩ B = 두 개념의 공통 요소
- A ⊕ B = 배타적 차이 요소
- f(A→B) = A에서 B로의 전이 함수
연결 탐색 프로세스:
1. 직접적 연결 찾기
2. 간접적 연결 탐색
3. 역설적 연결 발견
4. 메타포적 연결 구성
5. 시스템적 연결 분석
""",
    "pr": """
## 4. 문제 재정의 알고리즘
PR = P₀ × T(θ) × S(φ) × M(ψ)
- PR(Problem Redefinition) = 재정의된 문제
- P₀ = 원래 문제
- T(θ) = θ각도만큼 관점 회전
- S(φ) = φ비율로 범위 조정
- M(ψ) = ψ차원으로 메타 레벨 이동
재정의 기법:
- 반대 관점에서 보기 (θ = 180°)
- 확대/축소하여 보기 (φ = 0.1x ~ 10x)
- 상위/하위 개념으로 이동 (ψ = ±1,±2,±3)
- 다른 도메인으로 전환
- 시간 축 변경
""",
    "is": """
## 5. 혁신적 솔루션 생성 공식
IS = Σ[Ci × Ni × Fi × Vi] / Ri
- IS(Innovative Solution) = 혁신적 솔루션
- Ci(Combination i) = i번째 조합 방식
- Ni(Novelty i) = 참신성 지수
- Fi(Feasibility i) = 실현 가능성
- Vi(Value i) = 가치 창출 정도
- Ri(Risk i) = 위험 요소
솔루션 생성 방법:
- 기존 요소들의 새로운 조합
- 전혀 다른 분야의 솔루션 차용
- 제약 조건을 오히려 활용
- 역방향 사고로 접근
- 시스템 전체 재설계
""",
    "ia": """
## 6. 인사이트 증폭 공식
IA = I₀ × (1 + r)ⁿ × C × Q
- IA(Insight Amplification) = 증폭된 인사이트
- I₀ = 초기 인사이트
- r = 반복 개선율
- n = 반복 횟수
- C = 협력 효과 (1-3배수)
- Q = 질문의 질 (1-5배수)
증폭 전략:
- 'Why'를 5번 이상 반복
- 'What if' 시나리오 구성
- 'How might we' 질문 생성
- 다양한 관점자와 토론
- 아날로그 사례 탐구
""",
    "te": """
## 7. 사고의 진화 방정식
TE = T₀ + ∫[L(t) + E(t) + R(t)]dt
- TE(Thinking Evolution) = 진화된 사고
- T₀ = 초기 사고 상태
- L(t) = 시간 t에서의 학습 함수
- E(t) = 경험 축적 함수
- R(t) = 반성적 사고 함수
진화 촉진 요인:
- 지속적 학습과 정보 습득
- 다양한 경험과 실험
- 깊은 반성과 메타인지
- 타인과의 지적 교류
- 실패로부터의 학습
""",
    "cs": """
## 8. 복잡성 해결 매트릭스
CS = det|M| × Σ[Si/Ci] × ∏[Ii]
- CS(Complexity Solution) = 복잡성 해결책
- det|M| = 시스템 매트릭스의 행렬식
- Si = i번째 하위 시스템 해결책
- Ci = i번째 하위 시스템 복잡도
- Ii = 상호작용 계수
복잡성 분해 전략:
- 시스템을 하위 구성요소로 분해
- 각 구성요소 간 관계 매핑
- 핵심 레버리지 포인트 식별
- 순차적/병렬적 해결 순서 결정
- 전체 시스템 최적화
""",
    "il": """
## 9. 직관적 도약 공식
IL = (S × E × T) / (L × R)
- IL(Intuitive Leap) = 직관적 도약
- S(Silence) = 정적 사고 시간
- E(Experience) = 관련 경험 축적
- T(Trust) = 직관에 대한 신뢰
- L(Logic) = 논리적 제약
- R(Rationalization) = 과도한 합리화
직관 활성화 방법:
- 의식적 사고 중단
- 몸과 마음의 이완
- 무의식적 연결 허용
- 첫 번째 떠오르는 아이디어 포착
- 판단 없이 수용
""",
    "iw": """
## 10. 통합적 지혜 공식
IW = (K + U + W + C + A) × H × E
- IW(Integrated Wisdom) = 통합적 지혜
- K(Knowledge) = 지식의 폭과 깊이
- U(Understanding) = 이해의 수준
- W(Wisdom) = 지혜의 깊이
- C(Compassion) = 공감과 연민
- A(Action) = 실행 능력
- H(Humility) = 겸손함
- E(Ethics) = 윤리적 기준
"""
}

def create_team_from_leads(team_leads, selected_names, mode: str = "개인의견 취합", depth: str = "보통"):
    """선택된 팀장 정보로 Agno Team 구성"""
    agents = []

    # 에이전트 프레임워크 설정 가져오기
    cfg_fw = st.session_state.get("agent_frameworks", {})

    for name in selected_names:
        # 이름으로 팀장 정보 찾기
        lead = get_team_lead_by_name(name)
        if not lead:
            continue
            
        lead_id, lead_name, lead_role, personality, strategic_focus = lead

        # 기본 지시사항 구성
        base_instructions = []
        if personality:
            base_instructions.extend(personality.splitlines())

        # 깊이 지시 추가
        base_instructions.extend(build_depth_instruction(depth))
        
        # 프레임워크 텍스트 추가
        fw_key = cfg_fw.get(lead_id, "none")
        if fw_key != "none":
            fw_text = FRAMEWORKS_TEXT.get(fw_key, "").strip()
            if fw_text:
                base_instructions.extend(fw_text.splitlines())

        agents.append(Agent(
            name=lead_name,
            role=f"당신은 한국 패션 아웃도어 브랜드의 {lead_role} 역할입니다.",
            model=OpenAIChat(id="gpt-4o"),
            instructions=base_instructions,
            goal=strategic_focus,
            tools=[GoogleSearchTools()],
        ))

    # 팀 모드 설정
    agno_mode = "coordinate" if mode == "개인의견 취합" else "collaborate"
    team_instructions = build_team_mode_instructions(mode, depth)

    team = Team(
        name="토론팀",
        mode=agno_mode,
        model=OpenAIChat(id="gpt-4o"),
        members=agents,
        tools=[ReasoningTools(add_instructions=True)],
        instructions=team_instructions,
        markdown=True,
        add_datetime_to_instructions=True,
        show_members_responses=True,
        debug_mode=True,
    )

    return team

def run_team_debate_stream(team, topic: str) -> Iterator[str]:
    """Team 객체를 기반으로 주제에 대해 스트리밍 토론 실행"""
    response_stream: Iterator[RunResponse] = team.run(topic, stream=True)
    for chunk in response_stream:
        content = chunk.content

        # 기본 체크
        if not content or not isinstance(content, str):
            continue

        # 로그 메시지 감지
        if re.match(r".*\)\s+completed in \d+\.\d+s.*", content):
            # 로그 메시지는 구분되게 마크다운 포맷으로 반환
            yield f"\n\n`{content.strip()}`\n\n"
        else:
            yield content




def stream_gpt_response(prompt: str):
    """GPT API를 통한 스트리밍 응답"""
    try:
        # 디버깅: 함수 시작 시 프롬프트 길이 정보 출력
        print(f"\n[DEBUG] stream_gpt_response 함수 호출됨")
        print(f"[DEBUG] 프롬프트 길이: {len(prompt)} 문자")
        print(f"[DEBUG] 프롬프트 첫 100자: {prompt[:100]}...")
        
        # OpenAI API 키 확인 (환경변수 또는 Streamlit secrets)
        api_key = os.getenv('OPENAI_API_KEY') or st.secrets.get('OPENAI_API_KEY')
        if not api_key:
            return "❌ OpenAI API 키가 설정되지 않았습니다. 환경변수 OPENAI_API_KEY를 설정해주세요."
        
        client = openai.OpenAI(api_key=api_key)
        
        # response = client.chat.completions.create(
        #     model="gpt-4o",  # 또는 사용 가능한 모델
        #     messages=[{"role": "user", "content": prompt}],
        #     stream=True,
        #     max_tokens=2000,
        #     temperature=0.7
        # )

        # 디버깅: API 호출 정보 출력
        print(f"[DEBUG] OpenAI API 호출 시작 - 모델: gpt-4o")
        print(f"[DEBUG] API 요청 파라미터:")
        print(f"  - model: gpt-4o")
        print(f"  - stream: True")
        print(f"  - max_tokens: 2000")
        print(f"  - temperature: 0.7")
        
        response = client.chat.completions.create(
            model="gpt-4o",  # GPT-5 대신 사용 가능한 모델로 변경
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            max_tokens=2000,  # max_completion_tokens 대신 max_tokens 사용
            temperature=0.7   # temperature 파라미터 추가
        )
        
        print(f"[DEBUG] API 응답 스트리밍 시작")
        
        full_response = ""
        chunk_count = 0
        for chunk in response:
            chunk_count += 1
            
            # 일부 청크에는 content가 없을 수 있으니 방어 코딩
            if hasattr(chunk, "choices") and chunk.choices:
                delta = getattr(chunk.choices[0], "delta", None)
                if delta and getattr(delta, "content", None):
                    piece = delta.content
                    full_response += piece
        
        # print(f"[DEBUG] API 응답 완료")
        # print(f"[DEBUG] 총 청크 수: {chunk_count}")
        # print(f"[DEBUG] 응답 길이: {len(full_response)} 문자")
        # print(f"[DEBUG] 응답 첫 200자: {full_response[:200]}...")
        
        return full_response
                
    except Exception as e:
        return f"❌ 오류가 발생했습니다: {str(e)}"

# 데이터베이스 초기화
init_database()

# 좌측 사이드바 구성
with st.sidebar:
    st.header("🎯 팀토론 시뮬레이터")

    # 사용자 정보 및 로그아웃
    st.write(f'👤 환영합니다, KS!')
    authenticator.logout('로그아웃', 'sidebar')
    st.markdown("---")
    
    # 1. 회의 참석자 선택 (토글 방식)
    st.markdown("### 👥 회의 참석자")
    
    # 데이터베이스에서 팀장 목록 가져오기
    team_leads = get_team_leads()
    
    if not team_leads:
        st.warning("⚠️ 팀장 정보가 없습니다. 'DB초기화' 버튼을 눌러주세요.")
    else:
        for team_lead in team_leads:
            member_id, member_name, member_role, _, _ = team_lead
            display_name = f"{member_name} ({member_role})"
            
            # 현재 선택된 상태 확인
            is_selected = member_name in st.session_state.participant_order
            
            # 토글 버튼 (체크박스 대신 버튼 사용)
            if st.button(
                f"{'✅' if is_selected else '▫️'} {display_name}", 
                key=f"toggle_{member_id}",
                use_container_width=True
            ):
                if is_selected:
                    # 선택 해제 - 순서 목록에서 제거
                    st.session_state.participant_order.remove(member_name)
                else:
                    # 선택 - 순서 목록에 추가
                    st.session_state.participant_order.append(member_name)
                st.rerun()
    
    st.markdown("---")
    
    # 2. 추론의 깊이
    st.markdown("### 🧠 추론의 깊이")
    reasoning_depth = st.radio(
        "추론 깊이를 선택하세요:",
        ["낮음", "보통", "깊게"],
        index=1,  # 기본값: 보통
        key="reasoning_depth_radio"
    )
    if reasoning_depth != st.session_state.reasoning_depth:
        st.session_state.reasoning_depth = reasoning_depth
    
    st.markdown("---")
    
    # 3. 팀 모드 선택
    st.markdown("### 🤝 팀 모드 선택")
    team_mode = st.radio(
        "토론 방식을 선택하세요:",
        ["개인의견 취합", "상호토론"],
        key="team_mode_radio"
    )
    if team_mode != st.session_state.team_mode:
        st.session_state.team_mode = team_mode
    
    st.markdown("---")
    
    # 4. 현재 상태
    st.markdown("### ℹ️ 현재 상태")
    st.write(f"**선택된 참석자:** {len(st.session_state.participant_order)}명")
    st.write(f"**추론 깊이:** {st.session_state.reasoning_depth}")
    st.write(f"**팀 모드:** {st.session_state.team_mode}")
    st.write(f"**대화번호:** {st.session_state.subject_seq}")
    
    st.markdown("---")
    
    # 5. 관리 도구
    st.markdown("### 🔧 관리 도구")
    
    # 샘플 데이터 삽입 기능은 index3.py에서 제거됨 (index.py와 테이블 공유)
    st.info("💡 팀장 정보는 index.py의 '샘플 데이터 삽입' 기능을 사용해주세요")
    
    # ==================== 하단 섹션 ====================
    st.markdown("---")
    
    # OpenAI API Key 설정
    st.markdown("### 🔑 OpenAI API Key 설정")
    openai_key = os.getenv('OPENAI_API_KEY') or st.secrets.get('OPENAI_API_KEY', '')
    if openai_key:
        st.success("✅ OpenAI API Key 설정됨 (환경변수)")
    else:
        st.warning("⚠️ OpenAI API Key가 설정되지 않았습니다")
    
    # 데이터베이스 연결 상태
    if 'supabase_client' in st.session_state and st.session_state.supabase_client:
        st.success("✅ 데이터베이스 연결됨")
        if st.button("데이터베이스 연결 해제", key="disconnect_index3"):
            st.session_state.supabase_client = None
            st.rerun()
    else:
        st.error("❌ 데이터베이스 연결 안됨")
    
    

# 메인 영역 구성
st.markdown("### 📋 사전정보")
preliminary_info = st.text_area(
    "사전정보를 입력하세요:",
    height=120,
    value=st.session_state.preliminary_info,
    key="prelim_info"
)
if preliminary_info != st.session_state.preliminary_info:
    st.session_state.preliminary_info = preliminary_info

st.markdown("---")

# 선택된 참석자들 표시 (클릭 순서대로)
if st.session_state.participant_order:
    st.markdown("### 👥 토론 참석자")
    cols = st.columns(len(st.session_state.participant_order))
    for i, member in enumerate(st.session_state.participant_order):
        with cols[i]:
            # 편집 모드인지 확인
            is_editing = st.session_state.editing_participant == member
            button_text = f"{'🔧' if is_editing else '🟢'} {member}"
            
            if st.button(button_text, key=f"edit_{member}", use_container_width=True):
                # 토글 방식: 이미 편집 중이면 닫고, 아니면 편집 모드로 전환
                if is_editing:
                    st.session_state.editing_participant = None
                else:
                    st.session_state.editing_participant = member
                st.rerun()
    
    # 편집 폼 표시
    if st.session_state.editing_participant:
        st.markdown("---")
        st.markdown(f"### ⚙️ {st.session_state.editing_participant} 정보 편집")
        
        # 데이터베이스에서 현재 정보 가져오기
        current_lead = get_team_lead_by_name(st.session_state.editing_participant)
        
        if current_lead:
            lead_id, current_name, current_role, current_personality, current_strategic_focus = current_lead
            
            # 편집 폼
            with st.form(key=f"edit_form_{lead_id}"):
                updated_name = st.text_input("이름", value=current_name)
                updated_role = st.text_input("역할", value=current_role)
                updated_personality = st.text_area("성향", value=current_personality, height=100)
                updated_strategic_focus = st.text_area("전략 포커스", value=current_strategic_focus, height=100)
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("💾 저장", use_container_width=True):
                        try:
                            # 데이터베이스 업데이트
                            update_team_lead(lead_id, updated_name, updated_role, updated_personality, updated_strategic_focus)
                            
                            # participant_order에서 이름이 변경된 경우 업데이트
                            if current_name != updated_name:
                                # 기존 이름을 새 이름으로 교체
                                idx = st.session_state.participant_order.index(current_name)
                                st.session_state.participant_order[idx] = updated_name
                                st.session_state.editing_participant = updated_name
                            
                            st.success(f"✅ {updated_name} 정보가 성공적으로 업데이트되었습니다!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ 업데이트 중 오류가 발생했습니다: {str(e)}")
                
                with col2:
                    if st.form_submit_button("❌ 취소", use_container_width=True):
                        st.session_state.editing_participant = None
                        st.rerun()
        else:
            st.error("❌ 참석자 정보를 찾을 수 없습니다.")
    
    st.markdown("---")

# 토론 주제 입력
st.markdown("### 🎯 토론 주제")
topic = st.text_input(
    "토론 주제를 입력하세요:",
    value=st.session_state.topic,
    key="topic_input"
)
if topic != st.session_state.topic:
    st.session_state.topic = topic

# 토론의 관점과 포인트 입력
st.markdown("### 📄 토론의 관점과 포인트")
discussion_content = st.text_area(
    "토론의 관점과 포인트를 입력하세요:",
    height=120,
    value=st.session_state.discussion_content,
    key="discussion_content_input"
)
if discussion_content != st.session_state.discussion_content:
    st.session_state.discussion_content = discussion_content

st.markdown("---")

# subject_seq 초기화 로직 (토론 시작 시에만)
if not st.session_state.subject_seq_initialized:
    last_seq = get_last_subject_seq()
    new_seq = last_seq + 1
    st.session_state.subject_seq = new_seq
    st.session_state.subject_seq_initialized = True
    print(f"[DEBUG] 새 토론 세션 - subject_seq = {new_seq}")

# 토론 시작 버튼
if st.button("🚀 토론 시작", type="primary", use_container_width=True):
    if not topic:
        st.error("토론 주제를 입력해주세요!")
    elif not st.session_state.participant_order:
        st.error("최소 1명의 참석자를 선택해주세요!")
    else:
        st.session_state.is_chat_started = True
        
        # 기존 대화 이력 불러오기
        conversation_history = get_conversation_history(st.session_state.subject_seq)
        st.session_state.messages = []
        
        # 이력이 있으면 세션 상태에 추가
        for from_to, content in conversation_history:
            role = "user" if from_to == "Q" else "assistant"
            st.session_state.messages.append({"role": role, "content": content})
        
        st.success("토론이 시작되었습니다! 아래 채팅창을 이용해주세요.")

# 채팅 인터페이스 (토론 시작 후에만 표시)
if st.session_state.is_chat_started:
    st.markdown("---")
    st.markdown("### 💬 채팅")
    
    # 채팅 메시지 표시 (최신 메시지가 아래로 오도록 정렬)
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
            if message["role"] == "user":
                st.markdown(f"**👤 사용자:** {message['content']}")
            else:
                st.markdown(f"**🤖 AI 팀:** {message['content']}")
    
    # 사용자 입력 (st.chat_input 사용으로 무한루프 방지)
    user_input = st.chat_input("메시지를 입력하세요...")
    
    if user_input:
        # 사용자 메시지 추가
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # talk_seq 계산
        talk_seq = get_next_talk_seq(st.session_state.subject_seq)
        print(f"[DEBUG] 사용자 입력 - talk_seq: {talk_seq}")
        
        # 사용자 입력 DB 저장
        save_conversation(
            st.session_state.topic,
            st.session_state.subject_seq,
            talk_seq,
            'Q',
            user_input
        )
        
        # 토론 컨텍스트 구성
        context_parts = []
        if st.session_state.preliminary_info.strip():
            context_parts.append(f"사전 정보: {st.session_state.preliminary_info}")
        if st.session_state.topic.strip():
            context_parts.append(f"토론 주제: {st.session_state.topic}")
        if st.session_state.discussion_content.strip():
            context_parts.append(f"토론의 관점과 포인트: {st.session_state.discussion_content}")
        
        # 대화 이력 추가
        conversation_history = get_conversation_history(st.session_state.subject_seq)
        if conversation_history:
            history_text = "\n이전 대화 이력:\n"
            for from_to, content in conversation_history:
                speaker = "사용자" if from_to == "Q" else "AI 팀"
                history_text += f"{speaker}: {content}\n"
            context_parts.append(history_text)
        
        # 현재 질문 추가
        context_parts.append(f"현재 질문: {user_input}")
        
        # 전체 컨텍스트 구성
        full_context = "\n\n".join(context_parts)
        
        # Agno 팀 생성 및 실행
        if not st.session_state.participant_order:
            st.error("❌ 토론 참석자를 선택해주세요!")
        else:
            try:
                # 팀장 정보 가져오기
                team_leads = get_team_leads()
                if not team_leads:
                    st.error("❌ 팀장 정보가 없습니다. 'DB초기화' 버튼을 눌러주세요!")
                else:
                    with st.spinner("AI 팀이 토론 중입니다..."):
                        # Agno 팀 생성
                        team = create_team_from_leads(
                            team_leads,
                            st.session_state.participant_order,
                            st.session_state.team_mode,
                            st.session_state.reasoning_depth
                        )
                        
                        if not team.members:
                            st.error("❌ 유효한 팀 멤버가 없습니다. 참석자 정보를 확인해주세요!")
                        else:
                            # 스트리밍 응답 처리
                            ai_response = ""
                            
                            # 실시간 스트리밍 없이 전체 응답 받기
                            for chunk in run_team_debate_stream(team, full_context):
                                ai_response += chunk
                            
                            # AI 응답 추가
                            st.session_state.messages.append({"role": "assistant", "content": ai_response})
                            
                            # AI 응답 DB 저장 (새로운 talk_seq 계산)
                            ai_talk_seq = get_next_talk_seq(st.session_state.subject_seq)
                            print(f"[DEBUG] AI 응답 - talk_seq: {ai_talk_seq}")
                            save_conversation(
                                st.session_state.topic,
                                st.session_state.subject_seq,
                                ai_talk_seq,
                                'A',
                                ai_response
                            )
            
            except Exception as e:
                st.error(f"❌ 토론 실행 중 오류가 발생했습니다: {str(e)}")
                print(f"[ERROR] Agno team execution failed: {e}")
        
        # 페이지 새로고침 (st.chat_input은 자동으로 초기화되므로 무한루프 없음)
        st.rerun()

