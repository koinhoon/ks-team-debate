# KS 시뮬레이터

패션 아웃도어 브랜드 KS의 다중 에이전트 회의 시뮬레이션 시스템

## 빠른 시작

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정
```bash
cp .env.example .env
# .env 파일을 편집하여 실제 Supabase 값을 입력
```

### 3. 앱 실행
```bash
streamlit run index.py
```

### 4. 로그인
로그인 정보는 환경변수에서 설정됩니다. `.env` 파일에서 다음과 같이 설정하세요:
```bash
AUTH_USERNAME=your_username
AUTH_PASSWORD=your_password
AUTH_NAME=your_display_name
```

## 배포 및 설정

자세한 설정 및 배포 방법은 [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)를 참조하세요.

## 주요 기능

- 🔐 **인증 시스템**: streamlit-authenticator를 사용한 로그인
- 🗄️ **클라우드 데이터베이스**: Supabase PostgreSQL 연동
- 🤖 **다중 에이전트**: OpenAI GPT 기반 팀장 에이전트들
- ⚙️ **환경설정**: 로컬/배포 환경 모두 지원
- 📊 **실시간 토론**: 스트리밍 기반 회의 시뮬레이션

## 아키텍처

- **Frontend**: Streamlit
- **Backend**: Python
- **Database**: Supabase (PostgreSQL)
- **AI**: OpenAI GPT-5
- **Authentication**: streamlit-authenticator
- **Deployment**: Streamlit Cloud