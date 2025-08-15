import streamlit as st
import openai
import json
from datetime import datetime
import os
from typing import List, Tuple
from dotenv import load_dotenv
import streamlit_authenticator as stauth
from supabase import create_client, Client

# 환경 변수 로드
load_dotenv()

# Page config
st.set_page_config(page_title="KS 시뮬레이터 v2", page_icon="💬", layout="wide")

# Supabase configuration
if 'supabase_url' not in st.session_state:
    st.session_state.supabase_url = os.getenv('SUPABASE_URL', '')
if 'supabase_anon_key' not in st.session_state:
    st.session_state.supabase_anon_key = os.getenv('SUPABASE_ANON_KEY', '')
if 'supabase_client' not in st.session_state:
    st.session_state.supabase_client = None

# 환경변수 기반 자동 연결 시도
def init_supabase_from_env():
    """환경변수에서 Supabase 설정을 읽어 자동 연결"""
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_ANON_KEY')
    
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

# 연결된 경우 사이드바에 상태 표시
# if st.session_state.supabase_client:
#     with st.sidebar:
#         st.success("✅ 데이터베이스 연결됨")
#         if st.button("연결 해제"):
#             st.session_state.supabase_client = None
#             st.rerun()

# Session state 초기화
if 'name' not in st.session_state:
    st.session_state.name = ""
if 'mode' not in st.session_state:
    st.session_state.mode = "본부장 사전 컨펌시뮬레이션"
if 'selected_team_members' not in st.session_state:
    st.session_state.selected_team_members = []
if 'conversation_mode' not in st.session_state:
    st.session_state.conversation_mode = "이전 대화 내용 이어서"
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
if 'report_content' not in st.session_state:
    st.session_state.report_content = ""
if 'is_chat_started' not in st.session_state:
    st.session_state.is_chat_started = False

# Supabase table creation info
def init_database():
    """데이터베이스 초기화 - 연결 확인만"""
    if not st.session_state.supabase_client:
        return

def get_last_subject_seq(name: str) -> int:
    """해당 이름의 마지막 subject_seq 반환"""
    if not st.session_state.supabase_client:
        return 0
    
    try:
        response = st.session_state.supabase_client.table('talk_latest')\
            .select('subject_seq')\
            .eq('name', name)\
            .order('subject_seq', desc=True)\
            .limit(1)\
            .execute()
        
        if response.data:
            return response.data[0]['subject_seq']
        return 0
    except Exception as e:
        st.error(f"subject_seq 조회 중 오류: {str(e)}")
        return 0

def save_conversation(name: str, subject_seq: int, talk_seq: int, from_to: str, content: str):
    """대화 내용을 데이터베이스에 저장"""
    if not st.session_state.supabase_client:
        st.error("데이터베이스가 연결되지 않았습니다.")
        return
    
    try:
        st.session_state.supabase_client.table('talk_latest').insert({
            'name': name,
            'subject_seq': subject_seq,
            'talk_seq': talk_seq,
            'from_to': from_to,
            'talk_history': content
        }).execute()
    except Exception as e:
        st.error(f"대화 저장 중 오류: {str(e)}")

def get_conversation_history(name: str, subject_seq: int, limit: int = 20) -> List[Tuple]:
    """최근 대화 내역 가져오기 (최대 20건)"""
    if not st.session_state.supabase_client:
        return []
    
    try:
        # talk_latest에서 최근 20건
        latest_response = st.session_state.supabase_client.table('talk_latest')\
            .select('from_to, talk_history')\
            .eq('name', name)\
            .eq('subject_seq', subject_seq)\
            .order('talk_seq', desc=True)\
            .limit(limit)\
            .execute()
        
        latest_conversations = [(row['from_to'], row['talk_history']) for row in latest_response.data]
        
        # talk_old에서 요약된 내용 가져오기
        old_response = st.session_state.supabase_client.table('talk_old')\
            .select('talk_history')\
            .eq('name', name)\
            .eq('subject_seq', subject_seq)\
            .order('id', desc=True)\
            .limit(1)\
            .execute()
        
        # 결과 조합 (시간순 정렬)
        history = []
        if old_response.data:
            history.append(('SUMMARY', old_response.data[0]['talk_history']))
        
        # 최신순으로 가져온 것을 시간순으로 뒤집기
        for from_to, content in reversed(latest_conversations):
            history.append((from_to, content))
        
        return history
    except Exception as e:
        st.error(f"대화 이력 조회 중 오류: {str(e)}")
        return []

def get_next_talk_seq(name: str, subject_seq: int) -> int:
    """다음 talk_seq 값 계산"""
    if not st.session_state.supabase_client:
        return 1
    
    try:
        response = st.session_state.supabase_client.table('talk_latest')\
            .select('talk_seq')\
            .eq('name', name)\
            .eq('subject_seq', subject_seq)\
            .order('talk_seq', desc=True)\
            .limit(1)\
            .execute()
        
        if response.data:
            return response.data[0]['talk_seq'] + 1
        return 1
    except Exception as e:
        st.error(f"talk_seq 계산 중 오류: {str(e)}")
        return 1

def should_summarize_conversations(name: str, subject_seq: int) -> bool:
    """대화가 40개 이상인지 확인"""
    if not st.session_state.supabase_client:
        return False
    
    try:
        response = st.session_state.supabase_client.table('talk_latest')\
            .select('id')\
            .eq('name', name)\
            .eq('subject_seq', subject_seq)\
            .execute()
        
        return len(response.data) >= 40
    except Exception as e:
        st.error(f"대화 개수 확인 중 오류: {str(e)}")
        return False

def summarize_and_archive_conversations(name: str, subject_seq: int):
    """처음 20건의 대화를 요약해서 talk_old에 저장하고 talk_latest에서 삭제"""
    if 'supabase_client' not in st.session_state:
        st.error("데이터베이스에 연결되지 않았습니다.")
        return
    
    try:
        # 처음 20건 가져오기 (talk_seq 오름차순)
        response = st.session_state.supabase_client.table('talk_latest')\
            .select('id, from_to, talk_history')\
            .eq('name', name)\
            .eq('subject_seq', subject_seq)\
            .order('talk_seq', desc=False)\
            .limit(20)\
            .execute()
        
        conversations = response.data
        
        if conversations:
            # GPT를 사용해서 요약
            summary_text = "이전 대화 요약:\n"
            for conv in conversations:
                summary_text += f"{conv['from_to']}: {conv['talk_history']}\n"
            
            # TODO: 실제로는 GPT API를 호출해서 요약해야 함
            # 현재는 단순히 텍스트 연결
            
            # talk_old에 요약 저장
            st.session_state.supabase_client.table('talk_old').insert({
                'name': name,
                'subject_seq': subject_seq,
                'talk_history': summary_text
            }).execute()
            
            # talk_latest에서 처음 20건 삭제
            ids_to_delete = [conv['id'] for conv in conversations]
            for conv_id in ids_to_delete:
                st.session_state.supabase_client.table('talk_latest')\
                    .delete()\
                    .eq('id', conv_id)\
                    .execute()
            
    except Exception as e:
        st.error(f"대화 요약 및 아카이브 중 오류 발생: {str(e)}")
        return

def create_gpt_prompt(
    user_name: str,
    subject_seq: int,
    preliminary_info: str,
    report_topic: str,
    report_content: str,
    user_input: str
) -> str:
    """GPT용 프롬프트 생성 (XML 태그 구조 + 페르소나/가이드 분리 + STAGE 추론 지시)"""

    # 1) 페르소나(정체성/톤) - '무엇처럼 말할지'만 기술
    persona_context = f"""
<persona>
  <identity>
    <role>한국 대기업 의류기획 본부장</role>
    <language>한국어(존칭, 간결·명료)</language>
  </identity>
  <tone_and_manners>
    <call_by_name>모든 팀원을 "{user_name}님"으로 호명</call_by_name>
    <no_praise>칭찬 금지(좋다/훌륭/탁월 등 금지)</no_praise>
    <teacher_mode>지식을 전수하는 스승의 태도(우월감은 은연중, 노골적 표현 금지)</teacher_mode>
    <indirect_pointing>직접 지적 금지, "예를들어" 사례/반문으로 자가점검 유도</indirect_pointing>
    <future_oriented>과거 회고보다 '해야 하는 이유/실행 효용/전망' 중심</future_oriented>
    <style>장황한 수식어·사과·군더더기 금지</style>
  </tone_and_manners>
</persona>
""".strip()

    # 2) 대화 가이드(프로토콜/출력 형식/단계 추론 규칙) - '어떻게 대화할지'
    dialogue_guide = f"""
<dialogue_guide>
  <stages>1,2,3,4</stages>
  <entry>첫 턴이면 STAGE=1로 시작</entry>

  <protocol>
    <one_stage_per_turn>한 번에 한 단계만 수행</one_stage_per_turn>
    <advance_rule>
      이전 대화(<history>)와 현재 입력(<current_input>)을 함께 검토하여
      현재 단계의 질문에 대한 사용자의 충족 정도를 판단:
      - 충분: 다음 단계로 진행
      - 불충분: 동일 단계에서 1회 보강 질문 후 대기
    </advance_rule>
    <stage_inference>
      마지막 assistant 발화의 질문 의도, 직전 user 답변의 충실도,
      누락/불명확 항목의 유무를 근거로 현재 STAGE를 스스로 추론.
      추론 결과(숫자)는 출력하지 말고, 해당 단계의 질문만 수행.
    </stage_inference>
    <no_meta_output>STAGE 번호/내부 규칙/태그를 절대 출력하지 말 것</no_meta_output>
    <end_marker>각 응답 말미에 정확히 "--- 응답 대기 ---" 한 줄만 출력</end_marker>
  </protocol>

  <stage_0_preamble>
    첫 턴인 경우 1문장만:
    "{user_name}님, 오늘 안건은 OOO죠. 예를들어, 우리가 지금 선택하면 다음 분기에 어떤 변화가 발생할지부터 가정해 보겠습니다."
    그 후 즉시 STAGE 1로.
  </stage_0_preamble>

  <stage_1_explore>
    목적: "어디까지 준비했는지" 확인하면서, 찾은 근거 자료에 대해 다른 레퍼런스 자료등이 있는데 찾았는지 확인
    출력: 2~3문 선별(아래 예시는 참조용이고 실제 보고 context_subject 내용에 맞는 추가 질문을 해야되는데 처음에는 일반적으로, 구체적 자료 기반에 관련한 질문으로 시작), 
    만약 보고 내용이 더 내용을 파악하기에 부족한 경우, 어떤 부분을 조금 더 설명해줘야될지 구체적으로 문의.
    예시:
      - "{user_name}님, 이거는 어떤 자료를 참고하고 만드신건가요?"
      - "현재 작성된 내용은 다른팀과 협의 후 작성된 내용이 맞으실까요?"
      - "이 내용의 OOO부분은 어떻게 생각하신걸까요?"
  </stage_1_explore>

  <stage_2_concretize>
    목적: 비용/공수/수치/구현 등 해당 주제를 실제 실무에서 시행한다고 가정했을때 실현 방안 및 Risk등 보고 주제와 입력된 채팅을 베이스로 보완해야될 부분을 찾아서 내용을 스스로 생각하고 내용을 보완할 수 있게 하려는 목적.
    용어를 직접 언급하지 말고 간접 질문으로 해야됨.
    
    매핑가이드:
    - 비용/공수·리스크·가치 균형: IS(혁신적 솔루션), CS(복잡성 해결)
    - 타당성·문제 재정의: GI(천재적 통찰), PR(문제 재정의)
    - 다차원 영향(시장/채널/조직): MDA(다차원 분석)
    - 대안 조합/차별성: CC(창의적 연결)
    - 일정·조직 변화/러닝커브: TE(사고 진화), IA(인사이트 증폭)
    - 직관의 점프 필요: IL(직관적 도약)
    - 윤리/브랜드 톤·행동 일치: IW(통합적 지혜)
    출력: 본문 1~2문 + 자원 질문 1문.
    자원 질문(예): "예를들어, 이번 분기 내 구현 또는 시행 시 자체인력 운영 방안이나 외주 방안이 있을텐데 어떻게 추진을 생각중이실가요?"
  </stage_2_concretize>

  <stage_3_future_value>
    목적: 효용(재무/브랜드/조직), 목적성, 비실행 비용, 차별 조건 등을 한번 더 생각하고 자료를 보완할 수 있도록 생각하게 만드는 목적
    출력: 2~3문으로 하되, 질문형으로 답변
    예:
      - "이것을 한다고 가정했을때, 우리 브랜드에서 어떻게 협업이 될 수 있을까요?"
      - "경쟁사가 동일 전략을 택할 때 우리는 무엇이 차별화 되는걸까요?"
      - "지금 해야 하는 이유 한 줄, 하지 않을 때의 차이는 무엇이라고 생각하나요?"
  </stage_3_future_value>

  <stage_4_closure>
    목적: 최소 지시만 전달하고 종료.
    출력: 1~2문.
    예:
      - "다음 미팅 전까지 위에 문의한 내용을 보완해주심 좋을거 같습니다."
  </stage_4_closure>
</dialogue_guide>
""".strip()

    # 3) 이전 대화 내역을 AI가 파싱하기 쉬운 XML로 구성
    history = get_conversation_history(user_name, subject_seq)
    history_items = []
    # talk_old 요약이 있으면 먼저
    if history and history[0][0] == 'SUMMARY':
        history_items.append(f"<summary>{history[0][1]}</summary>")

    # 그 외 턴들(시간순)
    for from_to, content in history:
        if from_to == 'SUMMARY':
            continue
        role = "user" if from_to == 'Q' else "assistant"
        # XML 안전을 위해 기본적인 치환(필요시 더 강화 가능)
        safe = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        history_items.append(f'<turn role="{role}">{safe}</turn>')

    history_xml = "<history>\n  " + "\n  ".join(history_items) + "\n</history>"

    # 4) 컨텍스트(사전정보/주제/보고내용)와 현재 입력
    contexts = []
    if preliminary_info.strip():
        contexts.append(f"<preliminary_info>{preliminary_info}</preliminary_info>")
    if report_topic.strip():
        contexts.append(f"<context_subject>{report_topic}</context_subject>")
    if report_content.strip():
        contexts.append(f"<context_report>{report_content}</context_report>")
    contexts_xml = "<contexts>\n  " + "\n  ".join(contexts) + "\n</contexts>" if contexts else "<contexts/>"

    current_input_xml = f"<current_input>{user_input}</current_input>"

    # 5) 최종 지시(출력 형식 고정)
    final_instructions = """
<instructions>
  - 위 <history>와 <current_input>를 근거로 현재 STAGE를 스스로 추론하고, 해당 단계의 질문만 출력하세요.
  - 한 번에 한 단계만 진행하십시오. 충분하면 다음 단계로, 불충분하면 같은 단계에서 1회 보강 질문 후 대기하십시오.
  - 페르소나를 준수하여 본부장 어투로만 말하고, 어떤 XML 태그도 그대로 반복 출력하지 마십시오.
  - 각 응답의 마지막 줄에는 정확히 "--- 응답 대기 ---"만 출력하십시오, 단 stage_4_closure 로 도달한 경우는 출력하지 않습니다.
  - stage_4_closure 이후 추가 질문이 들어오면 "보완 완료되면 윤기님에게 미팅 잡아달라고 하세요" 만 출력합니다.
</instructions>
""".strip()

    # 6) 전체 프롬프트 조립
    full_prompt = "\n".join([
        persona_context,
        dialogue_guide,
        history_xml,
        contexts_xml,
        current_input_xml,
        final_instructions
    ])

    # 디버깅: 생성된 전체 프롬프트 출력
    print("\n" + "="*80)
    print("[DEBUG] AI로 전송되는 전체 프롬프트(XML)]")
    print("="*80)
    print(full_prompt)
    print("="*80 + "\n")

    return full_prompt


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
    st.header("🎯 KS 시뮬레이터 v2")
    
    # 1. 내 정보
    st.markdown("### 👤 내 정보")
    name = st.text_input("내 이름", value="홍길동", key="name_input")
    if name != st.session_state.name:
        st.session_state.name = name
    
    st.markdown("---")
    
    # 2. 모드 선택
    st.markdown("### 🎮 모드 선택")
    mode = st.radio(
        "모드를 선택하세요:",
        ["본부장 사전 컨펌시뮬레이션"],
        key="mode_radio"
    )
    
    if mode != st.session_state.mode:
        st.session_state.mode = mode
        st.session_state.selected_team_members = []  # 모드 변경시 팀원 선택 초기화
    
    # 팀 토론 모드일 때 팀원 선택
    if mode == "팀 토론 (공격모드)":
        st.markdown("**팀원 선택:**")
        team_options = ["의류기획팀 리더", "마케팅팀 리더", "디자인팀 리더"]
        
        selected_members = []
        for member in team_options:
            if st.button(f"➕ {member}", key=f"add_{member}"):
                if member not in st.session_state.selected_team_members:
                    st.session_state.selected_team_members.append(member)
            
            if member in st.session_state.selected_team_members:
                if st.button(f"➖ {member}", key=f"remove_{member}"):
                    st.session_state.selected_team_members.remove(member)
    
    st.markdown("---")
    
    # 3. 대화 설정
    st.markdown("### 💬 대화 설정")
    conversation_mode = st.selectbox(
        "대화 방식:",
        ["새롭게 대화 시작", "이전 대화 내용 이어서"],
        key="conv_mode"
    )
    
    # subject_seq 설정 (대화 모드가 변경되었을 때만 업데이트)
    if name:
        # 대화 모드가 변경되었거나 처음 초기화될 때만 subject_seq 업데이트
        if (conversation_mode != st.session_state.conversation_mode) or not st.session_state.subject_seq_initialized:
            if conversation_mode == "새롭게 대화 시작":
                last_seq = get_last_subject_seq(name)
                new_seq = last_seq + 1
                st.session_state.subject_seq = new_seq
                print(f"[DEBUG] 새 대화 시작 - subject_seq = {new_seq}")
            else:  # "이전 대화 내용 이어서"
                last_seq = get_last_subject_seq(name)
                current_seq = last_seq if last_seq > 0 else 1
                st.session_state.subject_seq = current_seq
                print(f"[DEBUG] 이전 대화 이어서 - subject_seq = {current_seq}")
            
            # 대화 모드 업데이트 및 초기화 플래그 설정
            st.session_state.conversation_mode = conversation_mode
            st.session_state.subject_seq_initialized = True
        
        st.caption(f"현재 대화 번호: {st.session_state.subject_seq}")
    
    st.markdown("---")
    
    # 4. 현재 상태
    st.markdown("### ℹ️ 현재 상태")
    st.write(f"**이름:** {st.session_state.name}")
    st.write(f"**모드:** {st.session_state.mode}")
    st.write(f"**대화번호:** {st.session_state.subject_seq}")
    
    if st.session_state.mode == "팀 토론 (공격모드)":
        st.write(f"**선택된 팀원:** {len(st.session_state.selected_team_members)}명")
        for member in st.session_state.selected_team_members:
            st.write(f"  - {member}")
    
    st.markdown("---")
    
    # 5. 관리
    st.markdown("### 🔧 관리")
    
    if st.button("🗑️ 채팅 초기화"):
        st.session_state.messages = []
        st.session_state.is_chat_started = False
        st.rerun()
    
    if st.button("📊 DB 상태 확인"):
        conn = sqlite3.connect('talk.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM talk_latest")
        latest_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM talk_old")
        old_count = cursor.fetchone()[0]
        
        conn.close()
        
        st.write(f"talk_latest: {latest_count}건")
        st.write(f"talk_old: {old_count}건")
    
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
        if st.button("데이터베이스 연결 해제", key="disconnect_index2"):
            st.session_state.supabase_client = None
            st.rerun()
    else:
        st.error("❌ 데이터베이스 연결 안됨")
    
    # 사용자 정보 및 로그아웃
    st.markdown("---")
    authenticator.logout('로그아웃', 'sidebar')

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

# 팀 토론 모드일 때 참여자 표시
if mode == "팀 토론 (공격모드)" and st.session_state.selected_team_members:
    st.markdown("### 👥 토론 참석자")
    cols = st.columns(len(st.session_state.selected_team_members))
    for i, member in enumerate(st.session_state.selected_team_members):
        with cols[i]:
            st.button(f"🟢 {member}", disabled=True, key=f"display_{member}")
    st.markdown("---")

# 보고 주제 입력
st.markdown("### 🎯 보고 주제")
topic = st.text_input(
    "보고 주제를 입력하세요:",
    value=st.session_state.topic,
    key="topic_input"
)
if topic != st.session_state.topic:
    st.session_state.topic = topic

# 보고 내용 입력
st.markdown("### 📄 보고 내용")
report_content = st.text_area(
    "보고 내용을 입력하세요:",
    height=120,
    value=st.session_state.report_content,
    key="report_content_input"
)
if report_content != st.session_state.report_content:
    st.session_state.report_content = report_content

st.markdown("---")

# 보고 시작 버튼
if st.button("🚀 보고 시작", type="primary", use_container_width=True):
    if not name:
        st.error("이름을 입력해주세요!")
    elif not topic:
        st.error("보고 주제를 입력해주세요!")
    elif mode == "팀 토론 (공격모드)" and not st.session_state.selected_team_members:
        st.error("팀 토론 모드에서는 최소 1명의 팀원을 선택해주세요!")
    else:
        st.session_state.is_chat_started = True
        st.session_state.messages = []
        st.success("보고가 시작되었습니다! 아래 채팅창을 이용해주세요.")

# 채팅 인터페이스 (보고 시작 후에만 표시)
if st.session_state.is_chat_started:
    st.markdown("---")
    st.markdown("### 💬 채팅")
    
    # 채팅 메시지 표시 (최신 메시지가 아래로 오도록 정렬)
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
            if message["role"] == "user":
                st.markdown(f"**👤 {st.session_state.name}:** {message['content']}")
            else:
                st.markdown(f"**🤖 본부장님:** {message['content']}")
    
    # 처음 채팅 시작 시 기본 질문 버튼 표시
    if not st.session_state.messages:
        st.markdown("#### 💡 빠른 시작")
        st.caption("아래 버튼을 클릭하여 바로 보고를 시작하세요:")
        
        if st.button("🗣️ 본부장님, 위 보고 내용에 대해 어떻게 생각하시나요?", use_container_width=True):
            # 기본 메시지를 user_input으로 설정하여 처리
            default_message = "본부장님, 위 보고 내용에 대해 어떻게 생각하시나요?"
            st.session_state.messages.append({"role": "user", "content": default_message})
            
            # talk_seq 계산
            talk_seq = get_next_talk_seq(st.session_state.name, st.session_state.subject_seq)
            print(f"[DEBUG] 빠른 시작 - 사용자 talk_seq: {talk_seq}")
            
            # 사용자 입력 DB 저장
            save_conversation(
                st.session_state.name,
                st.session_state.subject_seq,
                talk_seq,
                'Q',
                default_message
            )
            
            # GPT 프롬프트 생성 및 응답
            if st.session_state.mode == "본부장 사전 컨펌시뮬레이션":
                prompt = create_gpt_prompt(
                    st.session_state.name,
                    st.session_state.subject_seq,
                    st.session_state.preliminary_info,
                    st.session_state.topic,
                    st.session_state.report_content,
                    default_message
                )
                
                with st.spinner("AI가 응답을 생성중입니다..."):
                    ai_response = stream_gpt_response(prompt)
                    st.session_state.messages.append({"role": "assistant", "content": ai_response})
                    
                    # AI 응답 DB 저장 (새로운 talk_seq 계산)
                    ai_talk_seq = get_next_talk_seq(st.session_state.name, st.session_state.subject_seq)
                    print(f"[DEBUG] 빠른 시작 - AI talk_seq: {ai_talk_seq}")
                    save_conversation(
                        st.session_state.name,
                        st.session_state.subject_seq,
                        ai_talk_seq,
                        'A',
                        ai_response
                    )
                    
                    # 40개 이상이면 요약
                    if should_summarize_conversations(st.session_state.name, st.session_state.subject_seq):
                        summarize_and_archive_conversations(st.session_state.name, st.session_state.subject_seq)
            
            else:  # 팀 토론 모드
                ai_response = f"[팀 토론] {', '.join(st.session_state.selected_team_members)}와 함께 '{default_message}'에 대해 토론합니다. (Agno 시스템 연동 예정)"
                st.session_state.messages.append({"role": "assistant", "content": ai_response})
            
            st.rerun()
        
        st.markdown("---")
    
    # 사용자 입력 (st.chat_input 사용으로 무한루프 방지)
    user_input = st.chat_input("메시지를 입력하세요...")
    
    if user_input:
        # 사용자 메시지 추가
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # talk_seq 계산
        talk_seq = get_next_talk_seq(st.session_state.name, st.session_state.subject_seq)
        print(f"[DEBUG] 일반 채팅 - 사용자 talk_seq: {talk_seq}")
        
        # 사용자 입력 DB 저장
        save_conversation(
            st.session_state.name,
            st.session_state.subject_seq,
            talk_seq,
            'Q',
            user_input
        )
        
        # GPT 프롬프트 생성
        if st.session_state.mode == "본부장 사전 컨펌시뮬레이션":
            prompt = create_gpt_prompt(
                st.session_state.name,
                st.session_state.subject_seq,
                st.session_state.preliminary_info,
                st.session_state.topic,
                st.session_state.report_content,
                user_input
            )
            
            # AI 응답 생성
            with st.spinner("AI가 응답을 생성중입니다..."):
                ai_response = stream_gpt_response(prompt)
                
                # AI 응답 추가
                st.session_state.messages.append({"role": "assistant", "content": ai_response})
                
                # AI 응답 DB 저장 (새로운 talk_seq 계산)
                ai_talk_seq = get_next_talk_seq(st.session_state.name, st.session_state.subject_seq)
                print(f"[DEBUG] 일반 채팅 - AI talk_seq: {ai_talk_seq}")
                save_conversation(
                    st.session_state.name,
                    st.session_state.subject_seq,
                    ai_talk_seq,
                    'A',
                    ai_response
                )
                
                # 40개 이상이면 요약
                if should_summarize_conversations(st.session_state.name, st.session_state.subject_seq):
                    summarize_and_archive_conversations(st.session_state.name, st.session_state.subject_seq)
        
        else:  # 팀 토론 모드
            ai_response = f"[팀 토론] {', '.join(st.session_state.selected_team_members)}와 함께 '{user_input}'에 대해 토론합니다. (Agno 시스템 연동 예정)"
            st.session_state.messages.append({"role": "assistant", "content": ai_response})
        
        # 페이지 새로고침 (st.chat_input은 자동으로 초기화되므로 무한루프 없음)
        st.rerun()

