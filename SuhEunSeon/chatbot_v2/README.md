# 🥬 Qook 신선식품 챗봇

신선식품 플랫폼의 **주문/검색**과 **CS(고객응대)**를 모두 처리하는 프로덕션급 AI 챗봇입니다.

## ✨ 주요 기능

- 🤖 **스마트 라우팅**: LLM 기반으로 사용자 의도를 정확히 파악
- 🔍 **상품 검색**: 자연어로 상품을 검색하고 RAG/Text2SQL 방식으로 결과 제공
- 🍳 **레시피 기반 쇼핑**: 요리명을 말하면 필요한 재료를 모두 추천
- 🛒 **원터치 주문**: 대화만으로 장바구니부터 결제까지 완료
- 🎧 **24/7 고객서비스**: FAQ 기반 자동 응답 및 상담사 연결
- 📱 **반응형 UI**: 밝고 신선한 디자인의 사용자 친화적 인터페이스

## 🏗️ 아키텍처

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   사용자 입력   │───▶│   라우터 노드    │───▶│  의도별 처리     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LangGraph 워크플로우                       │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   검색/주문     │      CS         │         공통               │
│                 │                 │                           │
│ • 쿼리 보강     │ • CS 접수       │ • 명확화 질문              │
│ • 상품 검색     │ • FAQ/정책 RAG  │ • 상담사 연결              │
│ • 레시피 검색   │ • 티켓 생성     │ • 세션 종료                │
│ • 장바구니      │                 │                           │
│ • 주문 처리     │                 │                           │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

## 🚀 빠른 시작

### 1. 저장소 클론 및 의존성 설치

```bash
git clone <repository-url>
cd chatbot_v2

# 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경 설정

```bash
# .env 파일 복사 및 수정
cp .env.example .env
```

`.env` 파일에서 다음 설정을 수정하세요:

```env
# OpenAI API 키 (필수)
OPENAI_API_KEY=your_actual_openai_api_key_here

# 데이터베이스 (선택사항 - SQLite로 대체 가능)
DATABASE_URL=mysql+pymysql://qook_user:qook_pass@localhost:3306/qook_chatbot

# Tavily API (레시피 검색용, 선택사항)
TAVILY_API_KEY=your_tavily_api_key_here
```

### 3. 데이터베이스 설정 (선택사항)

MySQL을 사용하는 경우:

```bash
# MySQL 서버에서 실행
mysql -u root -p < setup.sql
mysql -u root -p qook_chatbot < seed.sql
```

### 4. 시스템 테스트

```bash
python test_basic.py
```

### 5. 서버 시작

```bash
python app.py
```

또는

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### 6. 웹 브라우저에서 접속

- **랜딩페이지**: http://localhost:8000
- **챗봇**: http://localhost:8000/chat
- **API 문서**: http://localhost:8000/docs
- **헬스체크**: http://localhost:8000/api/health

## 📁 프로젝트 구조

```
chatbot_v2/
├── README.md                 # 이 파일
├── requirements.txt          # Python 의존성
├── .env                     # 환경 설정 (생성 필요)
├── .env.example            # 환경 설정 예제
├── config.py               # 설정 관리
├── app.py                  # FastAPI 메인 애플리케이션
├── workflow.py             # LangGraph 워크플로우
├── graph_interfaces.py     # 공통 인터페이스 및 타입
├── test_basic.py           # 기본 테스트 스크립트
├── setup.sql              # 데이터베이스 설정 SQL
├── seed.sql               # 테스트 데이터 SQL
├── ERD.md                 # 데이터베이스 설계 문서
├── CLAUDE.md              # 프로젝트 상세 스펙
├── team_plan.md           # 팀 분업 계획
├── nodes/                 # LangGraph 노드 구현
│   ├── router_clarify.py  # 라우터 & 명확화 (A 역할)
│   ├── query_enhancement.py # 쿼리 보강 (B 역할)
│   ├── product_search.py  # 상품 검색 (C 역할)
│   ├── recipe_search.py   # 레시피 검색
│   ├── cart_order.py      # 카트 & 주문 (D 역할)
│   ├── cs_rag.py          # CS & RAG (E 역할)
│   └── handoff_end.py     # 핸드오프 & 종료 (F 역할)
├── templates/             # HTML 템플릿
│   ├── landing.html       # 랜딩페이지
│   └── chat.html          # 챗봇 페이지
├── static/                # 정적 파일
│   └── css/
│       ├── landing.css    # 랜딩페이지 스타일
│       └── chat.css       # 챗봇 페이지 스타일
├── var/                   # 데이터 저장소 (자동 생성)
│   ├── index/            # 벡터 인덱스
│   └── chroma/           # ChromaDB 저장소
└── data/                  # 학습/참조 데이터 (수동 추가)
    ├── faq/              # FAQ 문서들
    └── policy/           # 정책 문서들
```

## 🔧 API 엔드포인트

### 주요 엔드포인트

- `GET /`: 랜딩페이지
- `GET /chat`: 챗봇 페이지
- `POST /api/chat`: 챗봇 대화 API
- `GET /api/health`: 헬스체크
- `GET /api/stats`: 시스템 통계

### 대화 API 사용 예시

```bash
curl -X POST "http://localhost:8000/api/chat" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "유기농 사과 주문하고 싶어요",
       "user_id": "user123"
     }'
```

## 🧪 테스트

### 기본 테스트 실행

```bash
python test_basic.py
```

### 수동 테스트 시나리오

1. **상품 검색**: "유기농 사과 찾아줘"
2. **레시피 기반**: "김치찌개 레시피 알려줘"
3. **장바구니**: "장바구니에 담아줘", "주문할게"
4. **고객서비스**: "배송 문의 있어요", "환불하고 싶어요"

## 🔑 주요 설정

### OpenAI API 키 설정 (필수)

```env
OPENAI_API_KEY=sk-proj-your-actual-key-here
```

### 데이터베이스 설정 (선택사항)

기본적으로 메모리 기반으로 동작하지만, MySQL을 사용하려면:

```env
DATABASE_URL=mysql+pymysql://username:password@localhost:3306/database_name
```

### 외부 API 설정 (선택사항)

```env
TAVILY_API_KEY=your_tavily_key_for_recipe_search
```

## 🐛 트러블슈팅

### 1. OpenAI API 오류

```
Error: OpenAI API key not found
```

→ `.env` 파일에 올바른 OpenAI API 키를 설정하세요.

### 2. 포트 충돌

```
Error: Port 8000 already in use
```

→ 다른 포트를 사용하세요: `python app.py --port 8080`

### 3. 의존성 오류

```
ImportError: No module named 'langchain'
```

→ 의존성을 다시 설치하세요: `pip install -r requirements.txt`

## 📊 성능 및 모니터링

- 시스템 통계: `/api/stats`
- 헬스체크: `/api/health` 
- 로그 레벨: 환경 변수 `LOG_LEVEL`로 조정

## 🛠️ 개발 가이드

### 새로운 노드 추가

1. `nodes/` 디렉토리에 새 파일 생성
2. `graph_interfaces.py`에서 함수 시그니처 정의
3. `workflow.py`에서 노드 추가 및 엣지 연결
4. `test_basic.py`에 테스트 추가

### 프론트엔드 커스터마이징

- CSS: `static/css/` 디렉토리
- HTML: `templates/` 디렉토리
- JavaScript: HTML 파일 내 인라인 또는 별도 파일로 분리

## 📝 라이선스

이 프로젝트는 MIT 라이선스 하에 제공됩니다.

## 🤝 기여

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📞 지원

문제가 발생하면 다음을 확인해주세요:

1. `python test_basic.py`로 기본 테스트 실행
2. `.env` 파일 설정 확인
3. `pip install -r requirements.txt`로 의존성 재설치
4. 로그 파일 확인

---

**Happy Coding!** 🥬✨