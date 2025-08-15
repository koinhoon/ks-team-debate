# KS 시뮬레이터 개발 및 배포 가이드

이 가이드는 KS 시뮬레이터를 로컬에서 개발하고 Streamlit Cloud에 배포하는 방법을 설명합니다. 
로컬과 배포 환경 모두에서 동일하게 작동하는 환경설정 시스템을 구현했습니다.

## 1. Supabase 설정

### 1.1 Supabase 프로젝트 생성
1. [Supabase](https://supabase.com)에 가입하고 새 프로젝트를 생성합니다.
2. 프로젝트 대시보드에서 다음 정보를 확인합니다:
   - Project URL (예: `https://your-project.supabase.co`)
   - Anon public key

## 2. 로컬 개발 환경 설정

### 2.1 의존성 설치
```bash
# 가상환경 생성 (권장)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 2.2 환경변수 설정
1. `.env.example` 파일을 `.env`로 복사합니다:
```bash
cp .env.example .env
```

2. `.env` 파일을 편집하여 실제 값을 입력합니다:
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-actual-anon-key-here
OPENAI_API_KEY=your-openai-api-key-here
AUTH_USERNAME=your_username
AUTH_PASSWORD=your_password
AUTH_NAME=your_display_name
```

### 2.3 로컬 실행
```bash
streamlit run index.py
```

환경변수가 설정되어 있으면 자동으로 데이터베이스에 연결됩니다.

## 3. Streamlit Cloud 배포

### 3.1 GitHub 리포지토리 준비
1. 프로젝트를 GitHub 리포지토리에 업로드합니다.
2. `.env` 파일은 `.gitignore`에 의해 제외되므로 업로드되지 않습니다.
3. `requirements.txt` 파일이 포함되어 있는지 확인합니다.

### 3.2 Streamlit Cloud 배포
1. [Streamlit Cloud](https://share.streamlit.io)에 로그인합니다.
2. "New app" 버튼을 클릭합니다.
3. GitHub 리포지토리를 선택하고 `index.py` 파일을 메인 파일로 설정합니다.
4. "Advanced settings"를 클릭하여 환경변수를 설정합니다:
   ```
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_ANON_KEY=your-actual-anon-key-here
   OPENAI_API_KEY=your-openai-api-key-here
   AUTH_USERNAME=your_username
   AUTH_PASSWORD=your_password
   AUTH_NAME=your_display_name
   ```
5. "Deploy!" 버튼을 클릭합니다.

## 4. 애플리케이션 사용

### 4.1 로그인
로그인 정보는 환경변수에서 설정됩니다. 로컬 환경과 Streamlit Cloud 모두에서 다음 환경변수를 설정하세요:
- `AUTH_USERNAME`: 로그인 사용자명
- `AUTH_PASSWORD`: 로그인 비밀번호  
- `AUTH_NAME`: 표시될 이름

### 4.2 데이터베이스 연결
환경변수가 설정되어 있으면 자동으로 연결됩니다. 그렇지 않은 경우:

1. 로그인 후 좌측 사이드바에서 "🔧 데이터베이스 설정" 섹션을 찾습니다.
2. 환경변수 상태를 확인합니다.
3. 필요시 수동으로 Supabase URL과 Anon Key를 입력하고 "수동 연결" 버튼을 클릭합니다.
4. 연결이 성공하면 "샘플 데이터 삽입" 버튼을 클릭하여 기본 팀장 데이터를 추가할 수 있습니다.

### 4.3 회의 시뮬레이션 사용
1. 좌측에서 참석자를 선택합니다.
2. 각 참석자의 설정 버튼(⚙️)을 클릭하여 역할과 성향을 조정할 수 있습니다.
3. 토론 방식과 탐색 깊이를 선택합니다.
4. 회의 주제를 입력하고 "회의 시작" 버튼을 클릭합니다.

## 5. 주요 변경사항

### 5.1 환경설정 시스템
- **통합된 환경설정**: 로컬(.env 파일)과 배포(Streamlit Cloud 환경변수) 모두 지원
- **자동 연결**: 환경변수가 설정되어 있으면 자동으로 데이터베이스 연결
- **수동 연결**: 환경변수가 없어도 UI에서 직접 설정 가능
- **상태 표시**: 환경변수 감지 여부와 연결 상태를 명확히 표시

### 5.2 인증 시스템
- `streamlit-authenticator`를 사용한 로그인 시스템 추가
- 환경변수 기반 사용자 계정 관리 (AUTH_USERNAME/AUTH_PASSWORD/AUTH_NAME)

### 5.3 데이터베이스
- SQLite에서 Supabase PostgreSQL로 마이그레이션
- 환경변수 우선 로딩, 수동 설정 백업
- 클라우드 환경에 적합한 구조

### 5.4 보안
- 환경 변수를 통한 데이터베이스 연결 정보 관리
- `.gitignore`를 통한 `.env` 파일 보호
- 비밀번호 해싱을 통한 안전한 인증

## 6. 환경별 설정 방법

### 6.1 로컬 개발
```bash
# 1. .env 파일 생성
cp .env.example .env

# 2. .env 파일 편집
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-actual-key
OPENAI_API_KEY=your-openai-api-key-here
AUTH_USERNAME=your_username
AUTH_PASSWORD=your_password
AUTH_NAME=your_display_name

# 3. 앱 실행
streamlit run index.py
```

### 6.2 Streamlit Cloud 배포
1. GitHub에 코드 업로드 (`.env` 파일은 자동으로 제외됨)
2. Streamlit Cloud에서 환경변수 설정:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
   - `OPENAI_API_KEY`
   - `AUTH_USERNAME`
   - `AUTH_PASSWORD`
   - `AUTH_NAME`
3. 배포 완료

## 7. 문제 해결

### 7.1 일반적인 문제
- **의존성 설치 실패**: 가상환경을 사용하고 Python 3.8+ 버전인지 확인하세요.
- **streamlit-authenticator 오류**: 0.2.3 버전이 설치되었는지 확인하세요.
- **환경변수 인식 안됨**: `.env` 파일 위치와 형식을 확인하세요.
- **데이터베이스 연결 실패**: Supabase URL과 Anon Key를 다시 확인하세요.
- **테이블이 존재하지 않음**: SQL Editor에서 테이블 생성 쿼리를 실행했는지 확인하세요.
- **로그인 실패**: 환경변수 `AUTH_USERNAME`과 `AUTH_PASSWORD`가 정확하게 설정되었는지 확인하세요.

### 7.2 환경변수 디버깅
앱 실행 시 사이드바에서 환경변수 감지 상태를 확인할 수 있습니다:
- ✅ "환경변수에서 설정을 감지했습니다" → 정상
- ⚠️ "환경변수가 설정되지 않았습니다" → `.env` 파일 확인 필요

### 7.3 디버깅
애플리케이션에서 오류가 발생하면 Streamlit Cloud의 로그를 확인하여 상세한 오류 메시지를 확인할 수 있습니다.