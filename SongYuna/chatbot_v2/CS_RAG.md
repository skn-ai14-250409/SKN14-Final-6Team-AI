# CS & RAG 모듈 구현 문서

**담당자**: E (CS & RAG)  
**작업 일자**: 2025-09-02  
**구현 파일**: `cs_module.py`

---

## 📋 구현 개요

팀 역할 E 담당으로 **CS 접수 및 FAQ & Policy RAG** 기능을 구현했습니다.  
사용자 요구사항에 따라 **멀티모달 환불/교환 처리** 기능을 중심으로 개발했습니다.

### 🎯 주요 기능
1. **cs_intake**: CS 접수, 티켓 생성, 멀티모달 이미지 분석
2. **faq_policy_rag**: FAQ & Policy 통합 RAG 답변 생성  
3. **멀티모달 환불/교환 처리**: 이미지 분석 기반 자동 해결

---

## 🛠️ 구현된 함수들

### 1. cs_intake(state) → Dict[str, Any]

**목적**: CS 접수 (반품/교환/배송/품질 등) + 멀티모달 이미지 분석

**주요 특징**:
- 텍스트 + 이미지 입력 동시 처리
- Vision LLM을 통한 상품 불량 여부 자동 판단
- 신뢰도 기반 자동/수동 처리 분기
- 티켓 생성 및 우선순위 설정

**처리 플로우**:
```
사용자 입력(텍스트+이미지)
↓
cs_intake (환불/교환 분류)
↓
analyze_product_image (멀티모달 분석)
↓
조건 분기:
- 신뢰도 높음 → 챗봇이 자동 환불/교환 처리
- 신뢰도 낮음 → 티켓 생성 → 상담원에게 전달
```

**출력 예시**:
```python
{
    "cs": {
        "ticket": {
            "ticket_id": "T-20250902155242-abc123",
            "category": "상품불량",
            "category_code": "product_defect",
            "summary": "사과에 곰팡이가 발생하여 식용 불가 상태",
            "confidence": 0.92,
            "auto_resolvable": True,
            "requires_human": False,
            "has_image": True,
            "image_analysis": {
                "is_defective": True,
                "detected_issue": "곰팡이 발생",
                "matched_product": "사과 1kg",
                "vision_confidence": 0.92
            }
        },
        "auto_response": {
            "text": "상품 이미지 분석 결과, 곰팡이 발생이 확인되었습니다...",
            "resolution_type": "auto_refund_exchange",
            "options": ["즉시 교환", "전액 환불"]
        },
        "next_action": "auto_resolve"
    }
}
```

### 2. faq_policy_rag(state) → Dict[str, Any]

**목적**: FAQ & Policy 통합 RAG 답변 생성

**주요 특징**:
- 티켓 상황 맞춤형 답변 생성
- 컨텍스트 기반 향상된 검색
- 신뢰도 기반 handoff 분기
- 인용 포함 근거 있는 답변

**답변 타입**:
1. **ticket_based**: 티켓 기반 맞춤형 답변
2. **followup**: 후속 질의 답변  
3. **standard**: 일반 FAQ 답변

**출력 예시**:
```python
{
    "cs": {
        "answer": {
            "text": "배송 관련 문의를 확인했습니다. 배송이 지연되는 경우...",
            "citations": ["FAQ:배송#faq_delivery_001", "Policy:반품#policy_return_001"],
            "confidence": 0.85,
            "response_type": "ticket_based",
            "category": "배송지연"
        },
        "next_action": "complete",
        "context_info": {
            "has_ticket": True,
            "ticket_id": "T-12345",
            "category": "배송지연"
        }
    }
}
```

---

## 🎟️ CS 티켓 시스템

### 티켓 기본 개념
- **티켓** = 고객 문의 기록 카드
- 챗봇이 즉시 답변 가능한 경우 → 티켓 필요 없음
- 챗봇이 바로 처리할 수 없는 경우 → 티켓 생성 (기록하고 추적)

### 티켓 정보 구조
```python
{
    "ticket_id": "T-YYYYMMDDHHMMSS-random",
    "category": "상품불량|배송지연|반품요청|교환요청|환불요청|...",
    "category_code": "product_defect|delivery_delay|...",
    "summary": "문제 요약",
    "confidence": 0.0-1.0,
    "priority": "high|medium|low",
    "auto_resolvable": True/False,
    "requires_human": True/False,
    "has_image": True/False
}
```

### 우선순위 결정
- **High**: 상품불량, 품질문제, 배송오류
- **Medium**: 배송지연, 반품요청, 교환요청, 환불요청
- **Low**: 기타문의

---

## 🖼️ 멀티모달 이미지 분석

### 분석 항목
1. 상품 불량 여부 판단
2. 상품 종류 식별
3. 품질 문제 유형 파악 
4. 환불/교환 가능성 평가

### 분석 결과 구조
```python
{
    "category": "상품불량",
    "confidence": 0.92,
    "description": "사과 상품 이미지 - 표면에 곰팡이 발생",
    "issue_summary": "사과에 곰팡이가 발생하여 식용 불가 상태", 
    "is_defective": True,
    "detected_issue": "곰팡이 발생",
    "matched_product": "사과 1kg",
    "auto_resolvable": True
}
```

### 자동 해결 조건
- 이미지 분석 신뢰도 > 0.85
- 상품 불량이 명확히 확인됨 (`is_defective: True`)
- 자동 해결 가능 플래그 (`auto_resolvable: True`)

---

## 📊 자동 해결 응답 타입

### 1. auto_refund_exchange (자동 환불/교환)
```python
{
    "text": "상품 이미지 분석 결과, 곰팡이 발생이 확인되었습니다...",
    "resolution_type": "auto_refund_exchange", 
    "options": ["즉시 교환", "전액 환불"],
    "estimated_resolution": "즉시"
}
```

### 2. delay_compensation (배송 지연 보상)
```python
{
    "text": "배송 지연으로 인해 불편을 드려 죄송합니다...",
    "resolution_type": "delay_compensation",
    "compensation": "할인 쿠폰 제공", 
    "estimated_resolution": "24시간 이내"
}
```

### 3. standard_processing (표준 처리)
```python
{
    "text": "품질문제 관련 문의를 접수했습니다...",
    "resolution_type": "standard_processing",
    "estimated_resolution": "24시간 이내"
}
```

---

## 🔄 다음 액션 분기

### next_action 결정 로직
```python
def _determine_next_action(confidence: float, context_info: Dict) -> str:
    if confidence < 0.3:
        return "handoff"  # 상담사 연결
    elif confidence < 0.6 and context_info.get("priority") == "high":
        return "handoff"  # 높은 우선순위는 낮은 신뢰도에서도 handoff
    elif context_info.get("auto_resolvable", False) and confidence > 0.7:
        return "auto_resolve"  # 자동 해결
    else:
        return "complete"  # 완료
```

### 액션별 의미
- **auto_resolve**: 챗봇이 자동으로 해결 처리
- **manual_review**: 수동 검토 필요 (티켓 생성)
- **handoff**: 상담사 연결 필요
- **complete**: 일반적인 FAQ 답변으로 완료

---

## 🧪 테스트 결과

### 테스트 시나리오
1. ✅ 텍스트 전용 CS 문의 (배송 지연)
2. ✅ 이미지 포함 상품 불량 신고 (자동 해결)
3. ✅ 직접 FAQ 질의
4. ✅ 티켓 기반 FAQ RAG
5. ✅ 멀티모달 자동 해결
6. ✅ 이미지 분석 기능
7. ✅ 티켓 우선순위 결정

### 테스트 결과 요약
- 모든 주요 기능 정상 동작 확인
- 멀티모달 환불/교환 처리 플로우 검증 완료
- 신뢰도 기반 자동/수동 분기 정상 작동
- 티켓 생성 및 관리 시스템 안정적

---

## 📈 성능 및 특징

### 장점
- **멀티모달 처리**: 텍스트+이미지 동시 분석
- **자동화**: 높은 신뢰도에서 자동 해결
- **확장성**: 새로운 카테고리 쉽게 추가 가능
- **추적성**: 티켓 시스템으로 완전한 이력 관리

### 한계점
- OpenAI Vision API 실제 구현 필요 (현재는 모의 구현)
- 벡터 DB 연동 필요 (현재는 모의 FAQ 데이터)
- 실제 CRM 연동 필요

---

## 🔧 향후 개선 사항

### 단기 개선
1. OpenAI Vision API 실제 연동
2. FAISS/Chroma 벡터 DB 연결  
3. FAQ/Policy 문서 인덱싱 구현

### 중기 개선
1. 더 정교한 이미지 분석 모델
2. 실시간 재고 연동
3. 자동 환불/교환 처리 시스템

### 장기 개선  
1. AI 기반 우선순위 동적 조정
2. 고객 만족도 기반 피드백 루프
3. 예측적 CS 서비스

---

## 📝 구현 완료 체크리스트

- ✅ cs_intake 함수 구현 (티켓 생성, 멀티모달 이미지 분석)
- ✅ faq_policy_rag 함수 구현 (FAQ&Policy RAG, 인용 포함 답변)  
- ✅ 멀티모달 환불/교환 처리 플로우 구현
- ✅ 티켓 시스템 구현 (생성, 우선순위, 자동해결 여부)
- ✅ 자동 해결 응답 생성 시스템
- ✅ 컨텍스트 기반 향상된 RAG 답변
- ✅ 신뢰도 기반 handoff 분기 로직
- ✅ 종합 테스트 스위트 작성
- ✅ 상세 문서화 완료

**최종 상태**: 모든 요구사항 구현 완료 ✅

---

**참고**: 본 구현은 `graph_interfaces.py`의 계약을 준수하며, 다른 팀 모듈과의 간섭을 최소화했습니다.