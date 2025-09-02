# 통합 프로젝트 구조 설계

## 최종 프로젝트 구조

```
chatbot_v2/
├── README.md                 # 통합 README
├── requirements.txt          # 통합 의존성 
├── .env.example              # 환경 설정 예제
├── config.py                 # 설정 관리
├── app.py                    # FastAPI 메인 애플리케이션
├── workflow.py               # LangGraph 워크플로우 정의
├── graph_interfaces.py       # 공통 인터페이스 (A팀 기준)
├── test_basic.py             # 기본 테스트 스크립트
├── setup.sql                 # 데이터베이스 설정 (A팀 기준)
├── seed.sql                  # 테스트 데이터 (A팀 기준)
├── ERD.md                    # 데이터베이스 설계 문서
├── FUNCTIONS.md              # 노드별 계약 문서 
├── team_plan.md              # 팀 분업 계획
├── team_analysis.md          # 팀 작업 분석 결과
├── integration_log.md        # 통합 작업 로그
├── nodes/                    # LangGraph 노드 구현체들
│   ├── __init__.py
│   ├── router_clarify.py     # A팀: 라우터 & 명확화
│   ├── query_enhancement.py  # B팀: 쿼리 보강
│   ├── product_search.py     # C팀: 상품 검색 (완성도 높음)
│   ├── recipe_search.py      # 레시피 검색 모듈
│   ├── cart_order.py         # D팀: 카트 & 주문
│   ├── cs_rag.py            # E팀: CS & RAG  
│   └── handoff_end.py       # F팀: 핸드오프 & 종료 (완성)
├── templates/                # HTML 템플릿
│   ├── landing.html          # 랜딩페이지
│   └── chat.html             # 챗봇 페이지
├── static/                   # 정적 파일
│   └── css/
│       ├── landing.css       # 랜딩페이지 스타일
│       └── chat.css          # 챗봇 페이지 스타일
├── utils/                    # 유틸리티 모듈
│   ├── __init__.py
│   ├── database.py          # 데이터베이스 연결 관리
│   ├── llm_client.py        # OpenAI LLM 클라이언트
│   ├── vector_store.py      # 벡터 저장소 관리
│   └── logging_config.py    # 로깅 설정
├── var/                     # 런타임 데이터 (자동 생성)
│   ├── index/              # 벡터 인덱스
│   └── chroma/             # ChromaDB 저장소
├── data/                    # 학습/참조 데이터
│   ├── faq/                # FAQ 문서들
│   └── policy/             # 정책 문서들
└── tests/                   # 테스트 파일들
    ├── __init__.py
    ├── test_nodes.py        # 노드별 테스트
    ├── test_workflow.py     # 워크플로우 테스트
    └── test_integration.py  # 통합 테스트
```

## 핵심 설계 원칙

### 1. FastAPI + LangGraph 기반
- **FastAPI**: 웹 API 및 UI 서빙
- **LangGraph**: 대화 플로우 및 상태 관리
- **A팀 graph_interfaces.py**: 모든 노드의 공통 계약

### 2. 모듈별 독립성 보장
- 각 팀의 구현체를 `nodes/` 폴더에 독립 모듈로 배치
- 공통 인터페이스를 통한 상호 작용
- 팀별 완성도 차이를 고려한 점진적 통합

### 3. 설정 및 환경 통합
- 모든 환경 변수를 `.env`로 중앙화
- `config.py`를 통한 설정 관리
- 개발/운영 환경 분리

### 4. 데이터베이스 통합
- A팀의 `setup.sql` 기준으로 스키마 통합
- 각 팀의 요구사항을 반영한 ERD 업데이트
- 테스트 데이터는 `seed.sql`로 관리

## 기술 스택 통합

### 백엔드 프레임워크
```
기존: Django (A,B,C,D,E팀) 
통합: FastAPI (LangGraph 호환성)
```

### 데이터베이스
```
- MySQL: 주 데이터베이스 (상품, 사용자, 주문)
- ChromaDB: 벡터 검색 (RAG)
- SQLite: 개발용 폴백
```

### AI/ML 스택
```
- OpenAI GPT: 라우팅, 재작성, 응답 생성
- LangGraph: 워크플로우 오케스트레이션  
- LangChain: RAG 및 도구 통합
- Tavily: 레시피 검색 API
```

### 웹 프론트엔드
```
- HTML/CSS/JavaScript: 간단한 웹 UI
- 반응형 디자인: 모바일 친화적
- WebSocket: 실시간 대화 (선택사항)
```

## 통합 작업 순서

### 1단계: 핵심 인프라
- [x] 프로젝트 구조 생성
- [ ] `graph_interfaces.py` 통합 및 정제
- [ ] `workflow.py` LangGraph 플로우 설계
- [ ] 기본 FastAPI 앱 구조

### 2단계: 데이터 계층
- [ ] `setup.sql` 통합 및 스키마 정제
- [ ] `seed.sql` 테스트 데이터 정리
- [ ] 데이터베이스 연결 및 ORM 설정

### 3단계: 노드 구현체 통합
- [ ] F팀 `handoff_end.py` 직접 복사 (완성)
- [ ] C팀 상품 검색 모듈 적응 및 통합
- [ ] A,B,D,E팀 기본 구현체 생성 및 보완

### 4단계: 웹 인터페이스
- [ ] 랜딩페이지 및 챗봇 UI 통합
- [ ] API 엔드포인트 구현
- [ ] 정적 파일 관리

### 5단계: 설정 및 환경
- [ ] 통합 `requirements.txt` 작성
- [ ] 환경 변수 및 설정 통합
- [ ] 로깅 및 모니터링 설정

### 6단계: 테스트 및 검증
- [ ] 기본 통합 테스트
- [ ] 각 노드별 단위 테스트
- [ ] 전체 워크플로우 테스트

## 완성도별 통합 전략

### 즉시 통합 가능 (완성)
- **F팀**: `handoff_end.py` 그대로 복사
- **A팀**: `graph_interfaces.py`, `setup.sql` 활용

### 부분 적응 필요 (높은 완성도)
- **C팀**: Django → FastAPI 어댑터 레이어 추가

### 기본 구현 필요 (구조만 완성)
- **B,D,E팀**: 인터페이스 준수하는 기본 구현체 생성

## 예상 통합 이슈 및 해결 방안

### 1. Django → FastAPI 전환
**이슈**: 기존 Django 앱들의 FastAPI 호환성
**해결**: 어댑터 패턴으로 기존 로직 래핑

### 2. 데이터베이스 스키마 차이 
**이슈**: 팀별로 다른 ERD 해석
**해결**: A팀 스키마 기준으로 통일, 필요시 확장

### 3. 의존성 충돌
**이슈**: 팀별 다른 패키지 버전
**해결**: 통합 `requirements.txt`로 버전 고정

### 4. 완성도 차이
**이슈**: 팀별 구현 완성도 편차
**해결**: 최소 동작 가능한 스텁으로 시작, 점진적 보완

## 다음 단계

1. **공통 인터페이스 정제**: `graph_interfaces.py` 최종 검토
2. **LangGraph 워크플로우 설계**: 노드 간 연결 정의  
3. **FastAPI 앱 골격 생성**: 기본 API 구조 구축
4. **완성된 노드부터 순차 통합**: F팀 → C팀 → 나머지 순서