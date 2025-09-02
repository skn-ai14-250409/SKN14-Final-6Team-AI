"""
pinecone_client.py - PINECONE 벡터 데이터베이스 클라이언트

FAQ 및 정책 문서를 벡터화하여 PINECONE에 저장하고 검색하는 기능을 제공합니다.
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv
import json

# 환경 변수 로드
load_dotenv()

logger = logging.getLogger("PINECONE_CLIENT")

# 설정 로드
try:
    from config import config
    PINECONE_API_KEY = config.PINECONE_API_KEY
    PINECONE_INDEX_NAME = config.PINECONE_INDEX_NAME
    openai_api_key = config.OPENAI_API_KEY
    logger.info("Config loaded successfully for PINECONE")
except ImportError:
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "qook")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    logger.warning("Config not found, using environment variables")

# OpenAI 임베딩 모델 설정
try:
    import openai
    if openai_api_key:
        openai_client = openai.OpenAI(api_key=openai_api_key)
        OPENAI_AVAILABLE = True
        logger.info("OpenAI client initialized for PINECONE embeddings")
    else:
        OPENAI_AVAILABLE = False
        logger.warning("OpenAI API key not found")
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI package not available")

# PINECONE 클라이언트 초기화
try:
    from pinecone import Pinecone, ServerlessSpec
    if PINECONE_API_KEY:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        PINECONE_AVAILABLE = True
    else:
        PINECONE_AVAILABLE = False
        logger.warning("PINECONE API key not found")
except ImportError as e:
    PINECONE_AVAILABLE = False
    logger.warning(f"PINECONE package not available: {e}")
    pc = None

def get_embedding(text: str) -> List[float]:
    """OpenAI를 사용하여 텍스트 임베딩 생성"""
    if not OPENAI_AVAILABLE:
        logger.error("OpenAI 클라이언트를 사용할 수 없습니다.")
        return []
    
    try:
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
            encoding_format="float"
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"임베딩 생성 실패: {e}")
        return []

def init_pinecone_index():
    """PINECONE 인덱스 초기화 및 생성"""
    if not PINECONE_AVAILABLE:
        logger.error("PINECONE을 사용할 수 없습니다.")
        return False
    
    try:
        # 기존 인덱스 확인
        existing_indexes = pc.list_indexes()
        index_names = [index.name for index in existing_indexes]
        
        if PINECONE_INDEX_NAME not in index_names:
            # 인덱스 생성 (dimension=1536은 OpenAI text-embedding-3-small의 차원)
            pc.create_index(
                name=PINECONE_INDEX_NAME,
                dimension=1536,
                metric='cosine',
                spec=ServerlessSpec(
                    cloud='aws',
                    region='us-east-1'
                )
            )
            logger.info(f"PINECONE 인덱스 '{PINECONE_INDEX_NAME}' 생성 완료")
        else:
            logger.info(f"PINECONE 인덱스 '{PINECONE_INDEX_NAME}' 이미 존재")
        
        return True
    except Exception as e:
        logger.error(f"PINECONE 인덱스 초기화 실패: {e}")
        return False

def get_pinecone_index():
    """PINECONE 인덱스 객체 반환"""
    if not PINECONE_AVAILABLE:
        return None
    
    try:
        return pc.Index(PINECONE_INDEX_NAME)
    except Exception as e:
        logger.error(f"PINECONE 인덱스 연결 실패: {e}")
        return None

def upsert_faq_data(faq_data: List[Dict[str, Any]]) -> bool:
    """FAQ 데이터를 PINECONE에 업로드"""
    if not PINECONE_AVAILABLE or not OPENAI_AVAILABLE:
        logger.error("PINECONE 또는 OpenAI를 사용할 수 없습니다.")
        return False
    
    try:
        index = get_pinecone_index()
        if not index:
            return False
        
        vectors = []
        
        for i, faq in enumerate(faq_data):
            # 질문과 답변을 결합하여 임베딩 생성
            text_content = f"질문: {faq['question']} 답변: {faq['answer']}"
            embedding = get_embedding(text_content)
            
            if not embedding:
                logger.warning(f"FAQ {i+1}의 임베딩 생성 실패")
                continue
            
            vector = {
                "id": f"faq_{faq['faq_id']}",
                "values": embedding,
                "metadata": {
                    "question": faq['question'],
                    "answer": faq['answer'],
                    "category": faq.get('faq_category', 'general'),
                    "type": "faq"
                }
            }
            vectors.append(vector)
        
        if vectors:
            # 배치로 업로드 (100개씩)
            batch_size = 100
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i:i + batch_size]
                index.upsert(vectors=batch)
                logger.info(f"FAQ 배치 {i//batch_size + 1} 업로드 완료 ({len(batch)}개)")
            
            logger.info(f"총 {len(vectors)}개의 FAQ가 PINECONE에 업로드되었습니다.")
            return True
        else:
            logger.warning("업로드할 FAQ 벡터가 없습니다.")
            return False
            
    except Exception as e:
        logger.error(f"FAQ 데이터 업로드 실패: {e}")
        return False

def search_faq(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """FAQ에서 관련 내용 검색"""
    if not PINECONE_AVAILABLE or not OPENAI_AVAILABLE:
        logger.error("PINECONE 또는 OpenAI를 사용할 수 없습니다.")
        return []
    
    try:
        index = get_pinecone_index()
        if not index:
            return []
        
        # 쿼리 임베딩 생성
        query_embedding = get_embedding(query)
        if not query_embedding:
            return []
        
        # PINECONE에서 유사한 FAQ 검색
        search_response = index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            filter={"type": {"$eq": "faq"}}
        )
        
        results = []
        for match in search_response.matches:
            result = {
                "id": match.id,
                "score": float(match.score),
                "question": match.metadata.get("question", ""),
                "answer": match.metadata.get("answer", ""),
                "category": match.metadata.get("category", "general")
            }
            results.append(result)
        
        logger.info(f"FAQ 검색 완료: {len(results)}개 결과 반환")
        return results
        
    except Exception as e:
        logger.error(f"FAQ 검색 실패: {e}")
        return []

def get_index_stats() -> Dict[str, Any]:
    """PINECONE 인덱스 통계 정보 반환"""
    if not PINECONE_AVAILABLE:
        return {"error": "PINECONE을 사용할 수 없습니다"}
    
    try:
        index = get_pinecone_index()
        if not index:
            return {"error": "인덱스에 연결할 수 없습니다"}
        
        stats = index.describe_index_stats()
        return {
            "total_vector_count": stats.total_vector_count,
            "namespaces": dict(stats.namespaces) if stats.namespaces else {},
            "dimension": stats.dimension,
            "index_fullness": stats.index_fullness,
        }
    except Exception as e:
        logger.error(f"인덱스 통계 조회 실패: {e}")
        return {"error": str(e)}

def test_pinecone_connection() -> bool:
    """PINECONE 연결 테스트"""
    if not PINECONE_AVAILABLE:
        logger.error("PINECONE을 사용할 수 없습니다.")
        return False
    
    try:
        # 인덱스 목록 조회로 연결 테스트
        indexes = pc.list_indexes()
        logger.info(f"PINECONE 연결 성공. 사용 가능한 인덱스: {[idx.name for idx in indexes]}")
        return True
    except Exception as e:
        logger.error(f"PINECONE 연결 테스트 실패: {e}")
        return False

if __name__ == "__main__":
    # 연결 테스트
    print("PINECONE 연결 테스트 중...")
    if test_pinecone_connection():
        print("✅ PINECONE 연결 성공")
        
        # 인덱스 초기화 테스트
        if init_pinecone_index():
            print("✅ 인덱스 초기화 성공")
            
            # 통계 조회 테스트
            stats = get_index_stats()
            print(f"인덱스 통계: {stats}")
        else:
            print("❌ 인덱스 초기화 실패")
    else:
        print("❌ PINECONE 연결 실패")