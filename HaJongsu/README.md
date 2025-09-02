# 🥬 Qook 신선식품 챗봇

> AI 기반 신선식품 쇼핑몰 통합 챗봇 서비스  
> **주문/검색**과 **고객서비스(CS)**를 모두 처리하는 LangGraph 기반 대화형 AI

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![LangGraph](https://img.shields.io/badge/LangGraph-0.0.64-orange.svg)
![License](https://img.shields.io/badge/License-MIT-blue.svg)

## 🌟 주요 기능

### 🛒 스마트 상품 검색 및 주문
- **자연어 검색**: "유기농 사과", "비건 요리 재료" 등 자연스러운 표현으로 상품 검색
- **Text2SQL + RAG**: 구조화된 상품 DB 쿼리와 의미 검색의 하이브리드 방식
- **장바구니 관리**: 대화를 통한 실시간 장바구니 추가/수정/삭제
- **원터치 주문**: 배송지 확인부터 결제까지 대화만으로 완성

### 🍳 레시피 기반 쇼핑
- **레시피 검색**: Tavily API를 통한 실시간 레시피 검색
- **재료 매핑**: 레시피 재료를 자동으로 쇼핑몰 상품과 연결
- **원클릭 담기**: 레시피에 필요한 모든 재료를 한 번에 장바구니에 추가

### 🎧 24/7 고객서비스
- **FAQ 자동 응답**: 배송, 환불, 교환 등 자주 묻는 질문 즉시 처리
- **정책 RAG**: 회사 정책 문서에서 정확한 답변 검색 및 인용
- **상담사 연결**: 복잡한 문의는 실시간으로 상담사에게 연결
- **이미지 지원**: 영수증, 상품 사진 등 이미지 기반 문의 처리

### 🧠 개인화 서비스  
- **알레르기 관리**: 사용자 알레르기 정보 기반 상품 필터링
- **식단 맞춤**: 비건, 글루텐프리 등 특수 식단 요구사항 지원
- **구매 패턴**: 과거 주문 이력 기반 개인 맞춤 추천

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
merge/
├── README.md                 # 이 파일
├── requirements.txt          # Python 패키지 의존성
├── .env.example             # 환경 변수 템플릿
├── app.py                   # FastAPI 메인 애플리케이션
├── graph_interfaces.py      # 공통 인터페이스 정의
├── workflow.py              # LangGraph 워크플로우
├── test_basic.py            # 기본 통합 테스트
├── setup.sql               # 데이터베이스 스키마
├── seed.sql                # 테스트 데이터
├── team_analysis.md        # 팀별 작업 분석
├── nodes/                  # 각 기능별 노드 구현
│   ├── __init__.py
│   ├── router.py           # 의도 라우팅
│   ├── query_enhancement.py # 쿼리 보강  
│   ├── product_search.py   # 상품 검색
│   ├── cart_order.py       # 장바구니/주문
│   ├── recipe.py           # 레시피 검색
│   └── handoff_end.py      # CS 처리 (완전 구현)
├── templates/              # HTML 템플릿
│   ├── landing.html        # 랜딩페이지
│   └── chat.html           # 챗봇 페이지
└── static/                 # 정적 파일
    ├── css/
    │   ├── landing.css     # 랜딩페이지 스타일
    │   └── chat.css        # 챗봇 페이지 스타일
    └── js/
        ├── landing.js      # 랜딩페이지 JavaScript
        └── chat.js         # 챗봇 클라이언트 JavaScript
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

## 🎯 사용 시나리오

### 상품 검색 및 주문

```
👤 사용자: "유기농 사과 2kg 주문하고 싶어요"
🤖 챗봇: "경북 안동산 유기농 사과를 찾았어요! 2kg에 6,000원입니다. 장바구니에 담아드릴까요?"
👤 사용자: "네, 담아주세요"  
🤖 챗봇: "장바구니에 담았습니다. 바로 주문하시겠어요?"
👤 사용자: "네, 주문할게요"
🤖 챗봇: "배송지를 확인해주세요: 서울시 강남구 테헤란로 123. 맞나요?"
```

### 레시피 기반 쇼핑

```
👤 사용자: "김치찌개 만들고 싶어요"
🤖 챗봇: "김치찌개 레시피를 찾았어요! 필요한 재료는 김치, 돼지고기, 두부, 대파입니다. 재료를 모두 장바구니에 담아드릴까요?"
👤 사용자: "네, 담아주세요"
🤖 챗봇: "총 4가지 재료를 장바구니에 담았습니다. 총 15,000원이에요."
```

### 고객서비스

```
👤 사용자: "배송이 늦어지고 있어요"  
🤖 챗봇: "주문번호를 알려주시겠어요?"
👤 사용자: "1001번이요"
🤖 챗봇: "확인해보니 배송이 예상보다 1일 지연되고 있습니다. 죄송합니다. 보상으로 다음 주문 시 무료배송 쿠폰을 드리겠습니다."
```

## 🔧 설정 가이드

### 환경 변수 설명

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 키 (필수) | - |
| `DB_HOST` | MySQL 호스트 | localhost |
| `DB_PORT` | MySQL 포트 | 3306 |
| `DB_NAME` | 데이터베이스 이름 | qook_chatbot |
| `TAVILY_API_KEY` | Tavily API 키 (레시피용) | - |
| `VECTOR_STORE_DIR` | 벡터 스토어 디렉토리 | ./var/index |
| `LOG_LEVEL` | 로그 레벨 | INFO |

### 데이터베이스 스키마

주요 테이블:
- `userinfo_tbl`: 사용자 기본 정보
- `product_tbl`: 상품 정보  
- `cart_tbl`: 장바구니
- `order_tbl`: 주문 이력
- `faq_tbl`: FAQ 데이터
- `chat_sessions`: 채팅 세션 관리
- `chat_state`: 대화 상태 추적

## 🤝 팀 기여

이 프로젝트는 6인 팀의 협력으로 완성되었습니다:

- **A팀 (MoonSangHee)**: 전체 아키텍처 설계, 인터페이스 정의
- **B팀 (SuhEunSeon)**: 쿼리 보강 및 의도 분석  
- **C팀 (Kimseongmin)**: 상품 검색 (Text2SQL + RAG)
- **D팀 (GimGwangRyeong)**: 장바구니 및 주문 처리
- **E팀 (SongYuna)**: 레시피 검색 및 재료 매핑
- **F팀 (HaJongsu)**: CS 처리 및 상담사 연결 (완전 구현)

## 📝 라이선스

이 프로젝트는 MIT 라이선스 하에 제공됩니다.

## 🤝 기여

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 🆘 문제 해결

### 자주 발생하는 문제

**Q: 챗봇이 응답하지 않아요**
A: OpenAI API 키가 올바르게 설정되어 있는지 확인하세요.

**Q: 데이터베이스 연결 오류**  
A: MySQL 서비스가 실행 중인지, 데이터베이스가 생성되어 있는지 확인하세요.

**Q: 벡터 검색이 작동하지 않아요**
A: FAQ 인덱스가 구축되어 있는지 확인하세요.

### 개발 모드 실행 단계

1. MySQL 서버 시작
2. 데이터베이스 및 테이블 생성 (setup.sql 실행)
3. 테스트 데이터 입력 (seed.sql 실행)  
4. .env 파일에 OpenAI API 키 설정
5. `python test_basic.py`로 기본 테스트 실행
6. `uvicorn app:app --reload`로 서버 시작

---

**🥬 신선한 하루의 시작, Qook과 함께하세요!**