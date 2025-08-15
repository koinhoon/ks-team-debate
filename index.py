import streamlit as st
import re
import os
import textwrap
import streamlit_authenticator as stauth
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
load_dotenv()
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.team.team import Team
from agno.tools.reasoning import ReasoningTools
from typing import Iterator
from agno.run.response import RunResponse  # 응답 객체 타입
from agno.tools.googlesearch import GoogleSearchTools
from pdf import create_pdf
from datetime import datetime


# --- Session state defaults ---
st.session_state.setdefault("meeting_result", "")     # 최종 결과(완료 후)
st.session_state.setdefault("stream_buffer", "")      # 스트리밍 중 임시 버퍼
st.session_state.setdefault("is_streaming", False)    # 스트리밍 중 여부
st.session_state.setdefault("confirm_reset", False)   # 초기화 확인창 노출 여부
st.session_state.setdefault("agent_frameworks", {})    # { lead_id: "gi"/"mda"/.../"none" }


def create_html_from_markdown(md_text: str, title: str = "회의 결과") -> bytes:
    """
    마크다운을 HTML로 변환하고, 가독성 높은 CSS를 포함한 standalone HTML을 bytes로 반환
    - markdown 패키지가 있으면 사용, 없으면 최소 변환(줄바꿈/코드블럭)만 적용
    """
    try:
        import markdown  # pip install markdown
        body_html = markdown.markdown(
            md_text,
            extensions=["fenced_code", "tables", "toc", "sane_lists", "codehilite"]
        )
    except Exception:
        # 최소 안전 폴백: 개행 → <br>만
        body_html = "<br>".join(md_text.splitlines())

    css = """
    /* 반응형 기본 설정 */
    * { box-sizing: border-box; }
    body { 
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
        line-height: 1.7; 
        color: #1f2937; 
        background: #ffffff; 
        margin: 0; 
        padding: 0;
        overflow-x: hidden; /* 가로스크롤 방지 */
        word-wrap: break-word; /* 긴 단어 자동 줄바꿈 */
    }
    
    .page { 
        max-width: 900px; 
        margin: 20px auto; 
        padding: 16px; 
        width: 100%;
    }
    
    /* 제목 반응형 */
    h1, h2, h3 { 
        color: #111827; 
        margin-top: 1.6em; 
        word-wrap: break-word;
        hyphens: auto;
    }
    h1 { font-size: clamp(1.5rem, 4vw, 1.8rem); }
    h2 { font-size: clamp(1.3rem, 3.5vw, 1.5rem); }
    h3 { font-size: clamp(1.1rem, 3vw, 1.25rem); }
    
    /* 텍스트 반응형 */
    p, li { 
        font-size: clamp(0.9rem, 2.5vw, 1rem); 
        word-wrap: break-word;
        overflow-wrap: break-word;
    }
    
    /* 코드 블록 반응형 */
    code { 
        font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; 
        background: #f3f4f6; 
        padding: 0.15em 0.4em; 
        border-radius: 4px;
        word-wrap: break-word;
        white-space: pre-wrap;
    }
    
    pre { 
        background: #f9fafb; 
        padding: 14px; 
        border-radius: 8px; 
        overflow-x: auto; 
        max-width: 100%;
        white-space: pre-wrap;
        word-wrap: break-word;
    }
    
    pre code { 
        background: transparent; 
        padding: 0; 
        white-space: pre-wrap;
    }
    
    /* 인용구 반응형 */
    blockquote { 
        margin: 1em 0; 
        padding: 0.6em 1em; 
        background: #f8fafc; 
        border-left: 4px solid #93c5fd; 
        color: #334155;
        word-wrap: break-word;
    }
    
    /* 테이블 반응형 */
    table { 
        border-collapse: collapse; 
        width: 100%; 
        margin: 1em 0;
        table-layout: fixed; /* 고정 레이아웃으로 반응형 구현 */
        word-wrap: break-word;
    }
    
    th, td { 
        border: 1px solid #e5e7eb; 
        padding: 8px 10px; 
        text-align: left;
        word-wrap: break-word;
        overflow-wrap: break-word;
    }
    
    th { background: #f3f4f6; }
    
    hr { 
        border: none; 
        border-top: 1px solid #e5e7eb; 
        margin: 2em 0; 
    }
    
    .meta { 
        color: #6b7280; 
        font-size: clamp(0.8rem, 2vw, 0.9rem); 
        margin-bottom: 1rem; 
    }
    
    /* 모바일 화면 대응 */
    @media (max-width: 768px) {
        .page {
            margin: 10px;
            padding: 12px;
        }
        
        h1, h2, h3 {
            margin-top: 1.2em;
        }
        
        table {
            font-size: 0.85rem;
        }
        
        th, td {
            padding: 6px 8px;
        }
        
        pre {
            padding: 10px;
            font-size: 0.85rem;
        }
        
        blockquote {
            padding: 0.5em 0.8em;
        }
    }
    
    /* 매우 작은 화면 대응 */
    @media (max-width: 480px) {
        .page {
            margin: 5px;
            padding: 8px;
        }
        
        table {
            font-size: 0.8rem;
        }
        
        th, td {
            padding: 4px 6px;
        }
        
        pre {
            padding: 8px;
            font-size: 0.8rem;
        }
    }
    """

    html = f"""<!doctype html>
    <html lang="ko">
    <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;600;700&display=swap" rel="stylesheet">
    <style>{css}</style>
    </head>
    <body>
    <div class="page">
    <h1>{title}</h1>
    <div class="meta">생성 시각: {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
    {body_html}
    </div>
    </body>
    </html>
    """
    return html.encode("utf-8")

def build_depth_instruction(depth: str) -> str:
    if depth == "low":
        return [
            # "검색,추론 깊이: LOW\n"
            # "- 빠른 결론 도출을 우선합니다. 불필요한 조사와 장황한 설명은 피하세요.\n"
            # "- 웹 검색은 필요 시 최대 1~2회만 수행하고, 최신성만 간단히 확인합니다.\n"
            # "- 결과는 핵심 요점 3개 이내의 불릿으로 요약하고, 출처가 있을 경우 1개만 간단히 첨부합니다.\n"
            # "- 불확실한 내용은 명확히 '추정'으로 표시하고, 추가조사 제안은 1줄로만 적어주세요.\n"
            # "- 모든 출력은 한국어로 간결하게 작성하세요."
            "*** 검색,추론 깊이: LOW ***",
            "1분 이내로 답변할 수 있는 수준의 간단한 조사만 수행합니다.",
            "복잡한 분석이나 다각도 비교는 하지 않습니다.",
            "웹 검색은 최대 1회만 허용하며, 검색 없이 기존 지식으로 답변 가능한 경우 검색을 생략합니다.",
            "결과는 핵심 요점 2개 이내의 불릿으로만 작성하고, 각 불릿은 1줄을 넘지 않습니다.",
            "출처는 반드시 1개만 간단히 제시하며, 없을 경우 '출처 없음'으로 표기합니다.",
            "불확실한 내용은 '추정'으로 표시하고, 추가 조사는 제안하지 않습니다.",
            "모든 출력은 한국어로 간결하게 작성합니다."
        ]
    if depth == "mid":
        return [
            "*** 검색,추론 깊이: MID ***"
            "정확성과 속도의 균형을 유지합니다. 핵심 쟁점을 정리하고 필요 시 3~5개 출처를 탐색합니다."
            "상반된 정보가 있을 때는 간단 비교(2~4줄) 후 합리적 결론을 제시합니다."
            "결과 구조: 요약(3~5줄) → 근거(불릿 3~6개) → 간단한 리스크/대안(불릿 1~3개) → 참고출처(2~3개, 최신순)"
            "수치/날짜 등은 가능한 한 명시적으로 제시합니다."
            "모든 출력은 한국어로 명확하고 읽기 쉽게 작성하세요."
        ]
    # default: high
    return [
        "*** 검색,추론 깊이: HIGH ***"
        "철저한 검증과 포괄적 탐색을 수행합니다. 상이한 관점과 최신 동향을 교차 확인합니다."
        "6~10개 내외의 신뢰도 높은 출처를 검토하고, 핵심/반대 근거를 구분해 제시합니다."
        "결과 구조: 실행요약(5~8줄) → 상세 분석(섹션별로 정리) → 가정/제약 → 리스크/완화전략 → 권고안 → 참고출처(정확한 표기, 최신성 우선)"
        "수치, 방법론, 한계를 명시하고, 데이터 출처의 신뢰성과 업데이트 날짜를 강조합니다."
        "모든 출력은 한국어로 전문적이고 체계적으로 작성하세요."
    ]


def build_team_mode_instructions(mode: str, depth: str) -> list[str]:
    # 1) team_mode별 기본 지침
    if mode == "coordinate":
        base_instructions = [
            "리더는 문제를 하위 과업으로 분해하고 각 에이전트의 전문성에 맞게 역할을 배정합니다.",
            "각 에이전트는 배정된 과업을 독립적으로 수행하고, 결과를 간결한 요약(핵심 3~5개 불릿)과 근거/출처와 함께 제출합니다.",
            "에이전트 간 직접 토론은 최소화하고, 필요한 경우 리더의 요청에만 응답해 보완합니다.",
            "리더는 모든 산출물을 통합하여 최종 보고서를 작성합니다: 실행요약 → 세부결과(에이전트별 섹션) → 리스크/대안 → 결론.",
            "수치·날짜·출처는 명시적으로 기재하고, 최신성과 신뢰도를 확인합니다.",
            "모든 사고과정 및 내용은 한국어로 작성합니다.",
        ]
    else:  # collaborate
        base_instructions = [
            "각 에이전트는 자신의 역할 관점에서 1차 입장을 제시합니다(핵심 주장/근거/우려).",
            "상반된 주장이 있을 경우, 최대 3라운드까지 반박·재반박을 수행하되, 매 라운드마다 합의 가능 지점을 식별합니다.",
            "합의가 어려운 항목은 가정/전제 차이를 명시하고, 트레이드오프에 대한 절충안을 제시합니다.",
            "최종 단계에서 팀은 공동 결론을 작성합니다: 실행요약(5~8줄) → 합의사항 → 이견/가정 → 권고안 → 후속 액션.",
            "수치·날짜·출처는 명시적으로 기재하고, 최신성과 신뢰도를 확인합니다.",
            "모든 사고과정 및 내용은 한국어로 작성합니다.",
        ]

    # 2) depth별 추가 지침
    depth_instructions = {
        "low": "간략하고 핵심적인 정보만을 바탕으로 답변합니다. 불필요한 세부사항은 생략하며, 2~3문장 내에서 결론 위주로 작성하세요.",
        "mid": "핵심 정보와 필수적인 배경 설명을 포함하여 답변합니다. 결론은 명확히 하고, 필요 시 간단한 예시나 비교를 덧붙입니다.",
        "high": "가능한 모든 세부 정보와 근거를 포함하여 심층적으로 분석합니다. 다양한 관점과 예시를 포함하고, 관련 통계나 데이터가 있으면 함께 제시하세요.",
    }

    # 3) 결합
    return base_instructions + [depth_instructions.get(depth, "")]

# Create team_leads table in Supabase if it doesn't exist
def check_database_connection():
    """데이터베이스 연결 확인"""
    if not st.session_state.supabase_client:
        return False
    return True

def insert_sample_data():
    """
    샘플 팀장 데이터를 삽입합니다.
    """
    if not st.session_state.supabase_client:
        st.error("데이터베이스가 연결되지 않았습니다.")
        return
    
    sample_leads = [
        {
            'name': '의류기획팀 팀장',
            'role': '의류 기획 파트 리더',
            'personality': '시즌 트렌드와 판매 데이터 기반의 제품을 제안하며, 제품의 생산 가능성과 원가 구조 고려해야함. 기존 제품과의 포지셔닝 충돌 방지등을 고려',
            'strategic_focus': '시장성과 브랜드 정체성을 모두 만족시키는 시즌별 상품 라인업을 구성하고, 판매 예측에 기반한 효율적인 상품 기획을 수행하는 것.'
        },
        {
            'name': '마케팅팀 PL',
            'role': '마케팅 파트 리더',
            'personality': '타겟 고객과의 접점을 중심으로 콘텐츠 기획하며 예산 대비 ROI 높은 캠페인을 제안검토 노출, 전환, 참여율 등 데이터 중심으로 접근',
            'strategic_focus': '각 시즌 캠페인, 디지털 콘텐츠, SNS, 광고 등 마케팅 활동을 통해 브랜드 가치를 강화하고 판매 전환율을 극대화하는 것.'
        },
        {
            'name': '의류디자인 팀장',
            'role': '의류 디자인 파트 리더',
            'personality': '브랜드의 철학과 이미지에 부합하는 디자인 제안. 소재, 컬러, 실루엣 등 트렌드를 분석해 디자인 방향 설정. 시즌별 핵심 제품군(헤리티지, 기능성, 포인트 아이템 등)에 대한 명확한 디자인 의도 설명',
            'strategic_focus': '브랜드 아이덴티티와 시즌 트렌드를 반영한 창의적이고 상업성 있는 디자인을 통해 소비자에게 매력적인 제품을 제공하는 것.'
        }
    ]
    
    try:
        for lead in sample_leads:
            st.session_state.supabase_client.table('team_leads').insert(lead).execute()
        st.success("샘플 데이터가 성공적으로 삽입되었습니다!")
    except Exception as e:
        st.error(f"샘플 데이터 삽입 중 오류가 발생했습니다: {str(e)}")

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

# 라벨 ↔ 키 매핑
FRAMEWORK_LABELS = [
    "기본(없음)", "천재적 통찰 공식(GI)", "다차원 분석(MDA)", "창의적 연결 매트릭스",
    "문제 재정의 알고리즘", "혁신적 솔루션 생성 공식", "인사이트 증폭 공식",
    "사고의 진화 방정식", "복잡성 해결 매트릭스", "직관적 도약 공식", "통합적 지혜 공식"
]
LABEL_TO_KEY = {
    "기본(없음)": "none",
    "천재적 통찰 공식(GI)": "gi",
    "다차원 분석(MDA)": "mda",
    "창의적 연결 매트릭스": "cc",
    "문제 재정의 알고리즘": "pr",
    "혁신적 솔루션 생성 공식": "is",
    "인사이트 증폭 공식": "ia",
    "사고의 진화 방정식": "te",
    "복잡성 해결 매트릭스": "cs",
    "직관적 도약 공식": "il",
    "통합적 지혜 공식": "iw",
}
KEY_TO_INDEX = {v: i for i, v in enumerate(LABEL_TO_KEY.keys())}  # selectbox index 계산용


def create_team_from_leads(team_leads, selected_names, mode: str = "coordinate", depth: str = "mid"):
    """
    선택된 팀장 정보로 GPT 기반 Agno Team 구성
    """
    agents = []

    # 🔽 ID로 조회해 주입
    cfg_fw = (st.session_state.get("run_config", {}).get("agent_frameworks")
        or st.session_state.get("agent_frameworks")
        or {})


    for name in selected_names:
        lead = next(l for l in team_leads if l[1] == name)

        # lead[3] = 행동가이드(Instruction), lead[4] = 목표/Goal (사용자 DB 스키마 기준)
        base_instructions = []
        if lead[3]:
            # 여러 줄이면 splitlines로 나눠도 되고, 통짜로 넣어도 됨
            base_instructions.extend(lead[3].splitlines())

        # 🔽 깊이 지시 추가
        base_instructions.extend(build_depth_instruction(depth))
        #base_instructions.append("모든 사고 및 내용은 한국어로 작성합니다.")
        #base_instructions.append(f"당신은 한국 패션 아웃도어 브랜드의 {lead[2]} 역할로 주어진 주제에 대해 본인의 역할 및 본인의 소속팀 관점에서만 얘기합니다.")

        lead_id = lead[0]
        fw_key = cfg_fw.get(lead_id, "none")
        if fw_key != "none":
            fw_text = FRAMEWORKS_TEXT.get(fw_key, "").strip()
            if fw_text:
                base_instructions.extend(fw_text.splitlines())

        agents.append(Agent(
            name=name,
            role=f"당신은 한국 패션 아웃도어 브랜드의 {lead[2]} 역할입니다.",
            model=OpenAIChat(id="gpt-5"),
            instructions=base_instructions,
            goal=lead[4],
            tools=[GoogleSearchTools()],
        ))

    team_instructions = build_team_mode_instructions(mode, depth)

    team = Team(
        name="KS 회의팀",
        mode=mode,  
        model=OpenAIChat(id="gpt-5"),
        members=agents,
        tools=[ReasoningTools(add_instructions=True)],
        instructions=team_instructions,
        markdown=True,
        add_datetime_to_instructions=True,
        show_members_responses=True,
        debug_mode=True,
    )

    return team

def run_team_debate(team, topic: str) -> str:
    """
    Team 객체를 기반으로 주제에 대해 토론 실행

    :param team: Agno Team 객체
    :param topic: 토론 주제
    :return: 결과 텍스트
    """
    result = team.run(topic, stream=True)  # 여기가 dict 형태로 응답
    if isinstance(result, dict) and "content" in result:
        return result["content"]
    else:
        return str(result)  # fallback

def run_team_debate_stream(team, topic: str) -> Iterator[str]:
    """
    Team 객체를 기반으로 주제에 대해 스트리밍 토론 실행
    :return: 문자열 content chunk를 순차적으로 yield
    """
    response_stream: Iterator[RunResponse] = team.run(topic, stream=True)
    for chunk in response_stream:
        content = chunk.content

        # 기본 체크
        if not content or not isinstance(content, str):
            continue

        # 디버깅 출력 (터미널이나 로그용)
        #print("🔍 chunk.content:", repr(content))

        # 로그 메시지 감지 (예: transfer_task_to_member(...) completed in ...)
        if re.match(r".*\)\s+completed in \d+\.\d+s.*", content):
            # 로그 메시지는 구분되게 마크다운 포맷으로 반환
            yield f"\n\n`{content.strip()}`\n\n"
        else:
            yield content


# 페이지 제목과 아이콘 설정
st.set_page_config(page_title="KS 시뮬레이터", page_icon="🎮")

# Supabase configuration
# 환경변수에서 우선 로드, 없으면 빈 문자열
if 'supabase_url' not in st.session_state:
    st.session_state.supabase_url = os.getenv('SUPABASE_URL', '')
if 'supabase_anon_key' not in st.session_state:
    st.session_state.supabase_anon_key = os.getenv('SUPABASE_ANON_KEY', '')
if 'supabase_client' not in st.session_state:
    st.session_state.supabase_client = None

# 환경변수가 모두 설정되어 있으면 자동으로 연결 시도
def init_supabase_from_env():
    """환경변수에서 Supabase 설정을 읽어 자동 연결"""
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_ANON_KEY')

    # print(url)
    # print(key)
    
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

# Create authenticator with 0.1.5 API
hashed_passwords = stauth.Hasher(passwords).generate()
authenticator = stauth.Authenticate(names, usernames, hashed_passwords,
    'ks_auth_cookie', 'ks_auth_key')

# Authentication logic - 0.1.5 version
name, authentication_status, username = authenticator.login('KS 시뮬레이터 로그인', 'main')

if authentication_status == False:
    st.error('사용자명 또는 비밀번호가 잘못되었습니다.')
    st.stop()
elif authentication_status == None:
    st.warning('사용자명과 비밀번호를 입력해주세요.')
    st.stop()

# Authentication status handled in main sidebar section

# Supabase connection setup
if not st.session_state.supabase_client:
    with st.sidebar:
        st.subheader("🔧 데이터베이스 설정")
        
        # 환경변수 상태 표시
        env_url = os.getenv('SUPABASE_URL')
        env_key = os.getenv('SUPABASE_ANON_KEY')
        
        if env_url and env_key:
            st.info("💡 환경변수에서 설정을 감지했습니다.")
            st.write(f"🔗 URL: {env_url[:30]}...")
            st.write("🔑 Key: 설정됨")
            if auto_connected:
                st.success("✅ 자동으로 연결되었습니다!")
            else:
                if st.button("환경변수로 재연결 시도"):
                    if init_supabase_from_env():
                        st.success("연결 성공!")
                        st.rerun()
        else:
            st.warning("환경변수가 설정되지 않았습니다. 수동으로 입력해주세요.")
        
        st.markdown("---")
        
        # Input fields for Supabase configuration
        supabase_url = st.text_input(
            "Supabase URL",
            value=st.session_state.supabase_url,
            type="default",
            placeholder="https://your-project.supabase.co",
            help="환경변수 SUPABASE_URL이 설정되어 있으면 자동으로 채워집니다."
        )
        
        supabase_anon_key = st.text_input(
            "Supabase Anon Key",
            value=st.session_state.supabase_anon_key,
            type="password",
            help="환경변수 SUPABASE_ANON_KEY가 설정되어 있으면 자동으로 채워집니다."
        )
        
        if st.button("수동 연결"):
            if supabase_url and supabase_anon_key:
                try:
                    st.session_state.supabase_client = create_client(supabase_url, supabase_anon_key)
                    st.session_state.supabase_url = supabase_url
                    st.session_state.supabase_anon_key = supabase_anon_key
                    
                    st.success("데이터베이스에 성공적으로 연결되었습니다!")
                    st.rerun()
                except Exception as e:
                    
                    st.error(f"데이터베이스 연결 실패: {str(e)}")
            else:
                st.error("URL과 Anon Key를 모두 입력해주세요.")
    
    if not st.session_state.supabase_client:
        st.warning("데이터베이스 설정을 완료해주세요.")
        st.stop()

# Database status handled in main sidebar section



# Supabase에서 팀장 정보 가져오기
def get_team_leads():
    if not st.session_state.supabase_client:
        return []
    
    try:
        response = st.session_state.supabase_client.table('team_leads').select('*').execute()
        # Convert to list of tuples to match the original SQLite format
        return [(row['id'], row['name'], row['role'], row['personality'], row['strategic_focus']) for row in response.data]
    except Exception as e:
        st.error(f"데이터 조회 중 오류가 발생했습니다: {str(e)}")
        return []

def update_team_lead(id: int, name: str, role: str, personality: str, strategic_focus: str):
    """
    팀장의 ID에 해당하는 이름, 역할, 성향, 전략 포커스를 업데이트합니다.
    """
    if not st.session_state.supabase_client:
        st.error("데이터베이스가 연결되지 않았습니다.")
        return
    
    try:
        st.session_state.supabase_client.table('team_leads').update({
            'name': name,
            'role': role,
            'personality': personality,
            'strategic_focus': strategic_focus
        }).eq('id', id).execute()
    except Exception as e:
        st.error(f"데이터 업데이트 중 오류가 발생했습니다: {str(e)}")



# 🔁 초기화: 체크 순서 기억할 리스트
if "selection_order" not in st.session_state:
    st.session_state.selection_order = []

# 설정창 열림/닫힘 상태 추적
if "visible_settings_lead" not in st.session_state:
    st.session_state.visible_settings_lead = None  # 현재 열려 있는 팀장 이름 (없으면 None)

if "previous_checked" not in st.session_state:
    st.session_state.previous_checked = {}  # 이전 체크 상태 저장

# 좌측 메뉴바 구성
with st.sidebar:
    st.header("KS시뮬레이터")

    # 사용자 정보 및 로그아웃
    st.write(f'👤 환영합니다, KS!')
    authenticator.logout('로그아웃', 'sidebar')
    st.markdown("---")

    team_leads = get_team_leads()

    # print(team_leads)

    st.subheader("회의 참석자 선택")
    for lead in team_leads:
        name = lead[1]
        default_checked = name in st.session_state.selection_order
        checked = st.checkbox(f"{name} ({lead[2]})", value=default_checked, key=f"check_{name}")
        
        # 이전 상태가 없다면 초기화
        prev = st.session_state.previous_checked.get(name, None)

        # ✅ 체크박스 상태 변경됨 → 설정창 닫기
        if prev is not None and prev != checked:
            st.session_state.visible_settings_lead = None

        # 현재 체크 상태 저장 (다음 렌더링 비교용)
        st.session_state.previous_checked[name] = checked

        # 선택 순서 관리
        if checked and name not in st.session_state.selection_order:
            st.session_state.selection_order.append(name)
        elif not checked and name in st.session_state.selection_order:
            st.session_state.selection_order.remove(name)

    st.markdown("<hr>", unsafe_allow_html=True)

    # 토론 방식 선택
    # st.subheader("토론 방식 선택")
    # debate_style = st.radio("토론의 분위기를 선택해주세요:", ("상호 협력적 논의", "적대적 반대적 논의"))

    # 🔽 탐색 깊이 선택 (low/mid/high)
    depth_label = st.radio(
        "추론의 깊이",
        ["낮음 (low)", "보통 (mid)", "깊게 (high)"],
        index=1,  # 기본값: 보통
        horizontal=True
    )
    DEPTH_MAP = {"낮음 (low)": "low", "보통 (mid)": "mid", "깊게 (high)": "high"}
    search_depth = DEPTH_MAP[depth_label]

    st.subheader("팀 모드 선택")
    mode_label = st.radio(
        "에이전트 팀 모드",
        ["개인의견 취합(coordinate)", "상호토론 (collaborate)"],
        index=1,
        horizontal=False,
    )
    MODE_MAP = {
        "개인의견 취합(coordinate)": "coordinate",
        "상호토론 (collaborate)": "collaborate",
    }
    team_mode = MODE_MAP[mode_label]
    
    # ==================== 하단 섹션 ====================
    st.markdown("---")
    
    # OpenAI API Key 설정
    st.subheader("🔑 OpenAI API Key 설정")
    openai_key = os.getenv('OPENAI_API_KEY') or st.secrets.get('OPENAI_API_KEY', '')
    if openai_key:
        st.success("✅ OpenAI API Key 설정됨 (환경변수)")
    else:
        st.warning("⚠️ OpenAI API Key가 설정되지 않았습니다")
    
    # 데이터베이스 연결 상태
    if st.session_state.supabase_client:
        st.success("✅ 데이터베이스 연결됨")
        if st.button("샘플 데이터 삽입", key="sample_data_main"):
            insert_sample_data()
        if st.button("데이터베이스 연결 해제", key="disconnect_main"):
            st.session_state.supabase_client = None
            st.rerun()
    else:
        st.error("❌ 데이터베이스 연결 안됨")


# 우측 채팅 인터페이스 구성
st.title("KS 시뮬레이터")

selected_team_leads = st.session_state.selection_order.copy()

if selected_team_leads:
    st.subheader("회의 참석자")
    is_streaming = st.session_state.get("is_streaming", False)

    cols = st.columns(len(selected_team_leads))
    for i, name in enumerate(selected_team_leads):
        with cols[i]:
            # 버튼은 한 번만 만들고 disabled만 적용
            clicked = st.button(
                f"⚙️ {name}",
                key=f"setting_{name}",
                disabled=is_streaming  # 회의 중엔 설정 진입 차단
            )

            # 회의 중이 아니고, 버튼이 눌린 경우만 처리
            if clicked and not is_streaming:
                if st.session_state.visible_settings_lead == name:
                    st.session_state.visible_settings_lead = None
                else:
                    lead = next(l for l in team_leads if l[1] == name)
                    st.session_state.selected_lead = {
                        "id": lead[0],
                        "name": name,
                        "role": lead[2],
                        "personality": lead[3],
                        "strategic_focus": lead[4],
                    }
                    st.session_state.visible_settings_lead = name

    # ⚙️ 설정 폼은 회의 중엔 아예 렌더하지 않음
    if (
        not is_streaming
        and "selected_lead" in st.session_state
        and st.session_state.visible_settings_lead == st.session_state.selected_lead["name"]
    ):
        sel = st.session_state.selected_lead
        st.subheader(f"{sel['name']} 설정")

        updated_name = st.text_input("이름", value=sel["name"], key="name_input")
        updated_role = st.text_input("역할", value=sel["role"], key="role_input")
        updated_focus = st.text_area("목표 및 Goal", value=sel["strategic_focus"], key="focus_input")
        updated_personality = st.text_area("행동가이드", value=sel["personality"], key="personality_input")

        # 현재 저장된 키(없으면 "none") — ID 기준으로 읽기
        current_key = st.session_state["agent_frameworks"].get(sel["id"], "none")

        # 라벨/키 매핑 맞춤 인덱스
        KEY_TO_LABEL = {v: k for k, v in LABEL_TO_KEY.items()}
        current_label = KEY_TO_LABEL.get(current_key, "기본(없음)")

        framework_label = st.selectbox(
            "사고 프레임 선택",
            FRAMEWORK_LABELS,
            index=FRAMEWORK_LABELS.index(current_label),
            key=f"fw_{sel['id']}",    # ← 위젯 키도 ID 기반(이름 변경 영향 X)
        )
        selected_key = LABEL_TO_KEY[framework_label]

        if st.button("저장"):
            update_team_lead(sel["id"], updated_name, updated_role, updated_personality, updated_focus)
            st.session_state.selected_lead["name"] = updated_name

            # ✅ ID 기준으로 프레임 저장
            st.session_state["agent_frameworks"][sel["id"]] = selected_key

            st.success(f"{updated_name} 정보가 저장되었습니다.")
else:
    st.write("회의 참석 인원을 선택해주세요.")


st.markdown("<hr>", unsafe_allow_html=True)

# ✅ 회의 주제 입력은 한 번만
topic = st.text_input("회의 주제를 입력해주세요:")


# --- trigger: start button ---
start_disabled = st.session_state.get("is_streaming", False)

if st.button("회의 시작", disabled=start_disabled):
    # 입력 검증 (버튼 클릭 시 한 번만)
    if not selected_team_leads:
        st.warning("참석자를 선택하세요."); st.stop()
    if not topic:
        st.warning("회의 주제를 입력해주세요."); st.stop()

    if st.session_state.get("meeting_result") or st.session_state.get("stream_buffer"):
        st.session_state["confirm_reset"] = True
    else:
        st.session_state.setdefault("stream_id", 0)
        st.session_state["stream_id"] += 1
        st.session_state["topic"] = topic
        st.session_state["run_config"] = {
            "team_mode": team_mode,
            "search_depth": search_depth,
            "selected_team_leads": selected_team_leads[:],
             "agent_frameworks": st.session_state["agent_frameworks"].copy(),  # ← 스냅샷
        }
        st.session_state["meeting_result"] = ""
        st.session_state["stream_buffer"] = ""
        st.session_state["is_streaming"] = True
        st.session_state["confirm_reset"] = False
        st.rerun()

if st.session_state.get("confirm_reset", False):
    st.warning("기존 회의 내용이 사라집니다. 계속 진행하시겠습니까?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("계속 진행"):
            st.session_state.setdefault("stream_id", 0)
            st.session_state["stream_id"] += 1
            st.session_state["topic"] = topic
            st.session_state["run_config"] = {
                "team_mode": team_mode,
                "search_depth": search_depth,
                "selected_team_leads": selected_team_leads[:],
                "agent_frameworks": st.session_state["agent_frameworks"].copy(), 
            }
            st.session_state["meeting_result"] = ""
            st.session_state["stream_buffer"] = ""
            st.session_state["is_streaming"] = True
            st.session_state["confirm_reset"] = False
            st.rerun()
    with c2:
        if st.button("취소"):
            st.session_state["confirm_reset"] = False
            st.rerun()


# --- 토론 출력 영역(배너/결과) 전용 컨테이너 ---
debate_container = st.container()
with debate_container:
    banner_placeholder = st.empty()   # ↑ 먼저: 배너 자리 (화면 위)
    result_placeholder = st.empty()   # ↓ 다음: 결과 자리 (배너 아래)


if not st.session_state.get("is_streaming", False):
    if st.session_state.get("meeting_result"):
        result_placeholder.markdown(st.session_state["meeting_result"])

# --- streaming run (single place) ---
if st.session_state.get("is_streaming", False):
    cfg = st.session_state["run_config"]; 
    _topic = st.session_state["topic"]
    
    # 1) 배너는 '회의 시작' 버튼 바로 아래 자리(banner_placeholder)에만 한 번 출력
    banner_placeholder.markdown(
        f"팀 모드: **{cfg['team_mode']}**, 탐색 깊이: **{cfg['search_depth']}**  🧠 팀 토론을 시작합니다..."
    )

    team = create_team_from_leads(
        team_leads,
        cfg["selected_team_leads"],
        mode=cfg["team_mode"],
        depth=cfg["search_depth"],
    )

    current_id = st.session_state["stream_id"]
    full = ""
    try:
        for chunk in run_team_debate_stream(team, _topic):
            if current_id != st.session_state.get("stream_id"):
                break  # 다른 시작 감지 → 오래된 루프 중단
            full += chunk
            st.session_state["stream_buffer"] = full
            result_placeholder.markdown(full + "▌")

        if current_id == st.session_state.get("stream_id"):
            st.session_state["meeting_result"] = full
            st.session_state["stream_buffer"] = ""
            st.session_state["is_streaming"] = False
            result_placeholder.markdown(full)
            st.success("회의가 종료되었습니다.")
    except Exception as e:
        st.session_state["is_streaming"] = False
        st.error(f"오류 발생: {e}")


if st.session_state["meeting_result"]:
    md_text = st.session_state["meeting_result"]

    # 🔎 HTML 미리보기 (선택)
    with st.expander("HTML 미리보기 열기", expanded=False):
        try:
            import markdown
            preview_html = markdown.markdown(md_text, extensions=["fenced_code","tables"])
        except Exception:
            preview_html = "<pre>" + md_text + "</pre>"
        st.markdown(preview_html, unsafe_allow_html=True)

    # 💾 HTML 다운로드
    html_bytes = create_html_from_markdown(md_text, title="KS 회의 결과")
    st.download_button(
        "💾 HTML로 다운로드",
        data=html_bytes,
        file_name=f"meeting_result_{datetime.now().strftime('%Y%m%d_%H%M')}.html",
        mime="text/html",
    )

    # 📝 MD 원문 다운로드(원본 유지)
    st.download_button(
        "📝 Markdown(.md)로 다운로드",
        data=md_text.encode("utf-8"),
        file_name=f"meeting_result_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
        mime="text/markdown",
    )
