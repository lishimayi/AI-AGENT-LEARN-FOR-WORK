"""混合检索引擎 - Hybrid Retrieval (向量检索 + BM25 关键词检索)"""
import os
import json
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import numpy as np

from sentence_transformers import SentenceTransformer
import faiss
from loguru import logger

from src.core.config import config


class BM25Retriever:
    """BM25 关键词检索器"""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: List[Dict] = []
        self.doc_lengths: List[int] = []
        self.avg_doc_length: float = 0
        self.doc_freqs: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.vocab: Dict[str, int] = {}
        
    def _tokenize(self, text: str) -> List[str]:
        """简单分词"""
        # 简单处理：转小写，按空格/标点分割
        import re
        tokens = re.findall(r'\w+', text.lower())
        return tokens
    
    def _calculate_idf(self):
        """计算 IDF"""
        n = len(self.documents)
        for term, df in self.doc_freqs.items():
            self.idf[term] = np.log((n - df + 0.5) / (df + 0.5) + 1)
    
    def index(self, documents: List[Dict]):
        """构建索引"""
        self.documents = documents
        
        # 统计文档频率
        for doc in documents:
            content = doc.get("content", "")
            tokens = set(self._tokenize(content))
            
            for token in tokens:
                self.doc_freqs[token] = self.doc_freqs.get(token, 0) + 1
            
            self.doc_lengths.append(len(tokens))
        
        # 构建词汇表
        self.vocab = {term: idx for idx, term in enumerate(self.doc_freqs.keys())}
        
        # 计算 IDF
        self._calculate_idf()
        
        # 计算平均文档长度
        self.avg_doc_length = sum(self.doc_lengths) / len(self.doc_lengths) if self.doc_lengths else 1
        
        logger.info(f"BM25 indexed {len(documents)} documents, vocab size: {len(self.vocab)}")
    
    def _score_bm25(self, query: str, doc_idx: int) -> float:
        """计算单个文档的 BM25 分数"""
        query_tokens = self._tokenize(query)
        doc_content = self.documents[doc_idx].get("content", "")
        doc_tokens = self._tokenize(doc_content)
        doc_length = self.doc_lengths[doc_idx]
        
        score = 0.0
        doc_tf = {}
        
        for token in doc_tokens:
            doc_tf[token] = doc_tf.get(token, 0) + 1
        
        for token in query_tokens:
            if token not in self.vocab:
                continue
            
            tf = doc_tf.get(token, 0)
            idf = self.idf.get(token, 0)
            
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_length / self.avg_doc_length)
            
            score += idf * (numerator / denominator)
        
        return score
    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[int, float, Dict]]:
        """搜索"""
        if not self.documents:
            return []
        
        scores = []
        for i in range(len(self.documents)):
            score = self._score_bm25(query, i)
            scores.append((i, score, self.documents[i]))
        
        # 排序并返回 top_k
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


class VectorRetriever:
    """向量检索器"""
    
    def __init__(self, embedding_config: Optional[Dict] = None):
        self.config = embedding_config or {}
        self.model_name = self.config.get("model", "sentence-transformers/all-MiniLM-L6-v2")
        self.dimension = self.config.get("dimension", 384)
        self.device = self.config.get("device", "cpu")
        
        logger.info(f"Loading embedding model: {self.model_name}")
        self.model = SentenceTransformer(self.model_name, device=self.device)
        
        self.index: Optional[faiss.IndexFlatL2] = None
        self.documents: List[Dict] = []
    
    def encode(self, texts: List[str]) -> np.ndarray:
        """编码文本"""
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False
        )
        return embeddings
    
    def encode_single(self, text: str) -> np.ndarray:
        """编码单个文本"""
        return self.encode([text])[0]
    
    def index_documents(self, documents: List[Dict]):
        """索引文档"""
        self.documents = documents
        
        if not documents:
            return
        
        texts = [doc.get("content", "") for doc in documents]
        embeddings = self.encode(texts)
        
        # 创建 FAISS 索引
        self.index = faiss.IndexFlatL2(self.dimension)
        
        # L2 归一化
        faiss.normalize_L2(embeddings)
        self.index.add(embeddings.astype(np.float32))
        
        logger.info(f"Vector index created with {len(documents)} documents")
    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[int, float, Dict]]:
        """搜索"""
        if self.index is None or self.index.ntotal == 0:
            return []
        
        query_vector = self.encode_single(query)
        query_vector = query_vector.reshape(1, -1).astype(np.float32)
        faiss.normalize_L2(query_vector)
        
        distances, indices = self.index.search(query_vector, min(top_k * 2, self.index.ntotal))
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx != -1:
                # 转换为相似度
                similarity = 1 / (1 + dist)
                results.append((int(idx), float(similarity), self.documents[int(idx)]))
        
        return results


class HybridRetriever:
    """
    混合检索器
    结合向量检索和 BM25 关键词检索
    支持多种向量数据库：FAISS / Chroma / Milvus
    """

    _instance: Optional['HybridRetriever'] = None

    def __init__(self, vector_config: Optional[Dict] = None, retrieval_config: Optional[Dict] = None):
        self.vector_config = vector_config or config.vector_db
        self.retrieval_config = retrieval_config or config.retrieval
        self.embedding_config = config.embedding

        # 根据配置选择向量数据库类型
        self.vector_db_type = self.vector_config.get("type", "faiss")
        logger.info(f"Vector database type: {self.vector_db_type}")

        # 初始化向量检索器
        self.vector_retriever = self._create_vector_retriever()
        self.bm25_retriever = BM25Retriever()

        # 混合检索权重
        hybrid_config = self.retrieval_config.get("hybrid", {})
        self.vector_weight = hybrid_config.get("vector_weight", 0.7)
        self.keyword_weight = hybrid_config.get("keyword_weight", 0.3)

        self.documents: List[Dict] = []

    def _create_vector_retriever(self):
        """根据配置创建对应的向量检索器"""
        db_type = self.vector_db_type

        if db_type == "milvus":
            return MilvusRetriever(self.vector_config.get("milvus", {}))
        elif db_type == "chroma":
            return ChromaRetriever(self.vector_config.get("chroma", {}))
        elif db_type == "pgvector":
            return PGVectorRetriever(self.vector_config.get("pgvector", {}))
        else:
            return VectorRetriever(self.embedding_config)
        
    @classmethod
    def get_instance(cls) -> 'HybridRetriever':
        """获取单例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def index_documents(self, documents: List[Dict]):
        """索引文档"""
        self.documents = documents
        
        # 索引向量
        self.vector_retriever.index_documents(documents)
        
        # 索引 BM25
        self.bm25_retriever.index(documents)
        
        logger.info(f"Hybrid index created with {len(documents)} documents")
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        混合检索
        
        参数:
        - query: 查询字符串
        - top_k: 返回结果数量
        - filters: 过滤条件 (预留)
        
        返回:
        - 检索结果列表
        """
        # 并行执行两种检索
        vector_results = self.vector_retriever.search(query, top_k * 2)
        bm25_results = self.bm25_retriever.search(query, top_k * 2)
        
        # 构建分数映射
        scores: Dict[int, Dict[str, float]] = {}
        
        for idx, score, doc in vector_results:
            if idx not in scores:
                scores[idx] = {"doc": doc, "vector_score": 0, "bm25_score": 0}
            scores[idx]["vector_score"] = score
        
        for idx, score, doc in bm25_results:
            if idx not in scores:
                scores[idx] = {"doc": doc, "vector_score": 0, "bm25_score": 0}
            scores[idx]["bm25_score"] = score
        
        # 计算混合分数
        combined_results = []
        for idx, data in scores.items():
            # 归一化分数
            max_vector = max(s["vector_score"] for s in scores.values()) or 1
            max_bm25 = max(s["bm25_score"] for s in scores.values()) or 1
            
            norm_vector = data["vector_score"] / max_vector
            norm_bm25 = data["bm25_score"] / max_bm25
            
            # 混合分数
            combined_score = (
                self.vector_weight * norm_vector +
                self.keyword_weight * norm_bm25
            )
            
            result = {
                "content": data["doc"].get("content", ""),
                "metadata": data["doc"].get("metadata", {}),
                "score": combined_score,
                "vector_score": data["vector_score"],
                "bm25_score": data["bm25_score"],
                "id": idx
            }
            combined_results.append(result)
        
        # 排序
        combined_results.sort(key=lambda x: x["score"], reverse=True)
        
        # 应用过滤
        if filters:
            # 预留过滤逻辑
            pass
        
        return combined_results[:top_k]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_documents": len(self.documents),
            "vector_weight": self.vector_weight,
            "keyword_weight": self.keyword_weight,
            "embedding_model": self.vector_retriever.model_name,
            "dimension": self.vector_retriever.dimension
        }


class ChromaRetriever:
    """Chroma 向量数据库检索器 (可选替代方案)"""

    def __init__(self, chroma_config: Optional[Dict] = None):
        try:
            import chromadb

            persist_dir = chroma_config.get("persist_directory", "./data/chroma")
            collection_name = chroma_config.get("collection_name", "enterprise_knowledge")

            self.client = chromadb.PersistentClient(path=persist_dir)
            self.collection = self.client.get_or_create_collection(name=collection_name)
            self._model = None

            logger.info(f"Chroma collection '{collection_name}' initialized")
        except ImportError:
            logger.warning("Chroma not installed")
            self.client = None
            self.collection = None

    def _get_model(self):
        if self._model is None:
            self._model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        return self._model

    def add_documents(self, documents: List[Dict], embeddings: np.ndarray):
        """添加文档"""
        if self.collection is None:
            return

        ids = [f"doc_{i}" for i in range(len(documents))]
        contents = [doc.get("content", "") for doc in documents]
        metadatas = [doc.get("metadata", {}) for doc in documents]

        self.collection.add(
            ids=ids,
            documents=contents,
            embeddings=embeddings.tolist(),
            metadatas=metadatas
        )

    def index_documents(self, documents: List[Dict]):
        """索引文档"""
        if self.collection is None:
            return

        ids = [f"doc_{i}" for i in range(len(documents))]
        contents = [doc.get("content", "") for doc in documents]
        metadatas = [doc.get("metadata", {}) for doc in documents]

        model = self._get_model()
        embeddings = model.encode(contents).tolist()

        self.collection.add(
            ids=ids,
            documents=contents,
            embeddings=embeddings,
            metadatas=metadatas
        )

    def search(self, query: str, top_k: int = 5) -> List[Tuple[int, float, Dict]]:
        """搜索"""
        if self.collection is None:
            return []

        model = self._get_model()
        query_embedding = model.encode([query]).tolist()

        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=top_k
        )

        output = []
        for i in range(len(results["documents"][0])):
            distance = results["distances"][0][i]
            similarity = 1 / (1 + distance)
            output.append((
                i,
                float(similarity),
                {
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i]
                }
            ))

        return output

    def get_stats(self) -> Dict[str, Any]:
        return {"type": "chroma", "num_documents": self.collection.count()}


class PGVectorRetriever:
    """PostgreSQL + pgvector 检索器 (预留)"""

    def __init__(self, pg_config: Optional[Dict] = None):
        self.config = pg_config or {}
        logger.info("PGVector retriever initialized (not fully implemented)")

    def index_documents(self, documents: List[Dict]):
        logger.info("PGVector indexing not implemented - use Milvus instead")

    def search(self, query: str, top_k: int = 5) -> List[Tuple[int, float, Dict]]:
        logger.warning("PGVector search not implemented")
        return []

    def get_stats(self) -> Dict[str, Any]:
        return {"type": "pgvector", "status": "not_implemented"}


class MilvusRetriever:
    """Milvus 向量数据库检索器"""

    def __init__(self, milvus_config: Optional[Dict] = None):
        from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility

        self.milvus_config = milvus_config or {}
        self.embedding_config = config.embedding

        self.host = self.milvus_config.get("host", "localhost")
        self.port = str(self.milvus_config.get("port", "19530"))
        self.collection_name = self.milvus_config.get("collection_name", "enterprise_knowledge")
        self.dimension = self.milvus_config.get("dimension", self.embedding_config.get("dimension", 384))
        self.index_type = self.milvus_config.get("index_type", "HNSW")
        self.metric_type = self.milvus_config.get("metric_type", "IP")
        self.index_params = self.milvus_config.get("index_params", {"M": 16, "efConstruction": 128})

        self.collection: Optional[Collection] = None
        self._connected = False
        self._model = None

        logger.info(f"Milvus retriever initialized: {self.host}:{self.port}")

    def _get_embedding_model(self):
        if self._model is None:
            model_name = self.embedding_config.get("model", "sentence-transformers/all-MiniLM-L6-v2")
            device = self.embedding_config.get("device", "cpu")
            logger.info(f"Loading embedding model: {model_name}")
            self._model = SentenceTransformer(model_name, device=device)
        return self._model

    def connect(self) -> None:
        if self._connected:
            return

        try:
            from pymilvus import connections
            connections.connect(alias="default", host=self.host, port=self.port, timeout=30)
            self._connected = True
            logger.info(f"Connected to Milvus at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise

    def disconnect(self) -> None:
        if self._connected:
            from pymilvus import connections
            connections.disconnect("default")
            self._connected = False

    def encode_texts(self, texts: List[str]) -> np.ndarray:
        model = self._get_embedding_model()
        embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return embeddings.astype(np.float32)

    def encode_single(self, text: str) -> np.ndarray:
        return self.encode_texts([text])[0]

    def create_collection(self, drop_existing: bool = False):
        from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, utility

        self.connect()

        if utility.has_collection(self.collection_name):
            if drop_existing:
                utility.drop_collection(self.collection_name)
                logger.info(f"Dropped existing collection: {self.collection_name}")
            else:
                self.collection = Collection(self.collection_name)
                return self.collection

        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="metadata", dtype=DataType.JSON),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
        ]
        schema = CollectionSchema(fields=fields, description="Enterprise knowledge base")
        self.collection = Collection(name=self.collection_name, schema=schema)
        logger.info(f"Created collection: {self.collection_name}")
        return self.collection

    def build_index(self) -> None:
        if self.collection is None:
            raise ValueError("Collection not created")

        if self.index_type == "HNSW":
            index_params = {
                "metric_type": self.metric_type,
                "index_type": "HNSW",
                "params": {
                    "M": self.index_params.get("M", 16),
                    "efConstruction": self.index_params.get("efConstruction", 128)
                }
            }
        else:
            index_params = {
                "metric_type": self.metric_type,
                "index_type": "FLAT",
                "params": {}
            }

        self.collection.create_index(field_name="vector", index_params=index_params)
        self.collection.load()
        logger.info(f"Index built: {self.index_type}")

    def index_documents(self, documents: List[Dict], rebuild_index: bool = False) -> None:
        if not documents:
            return

        self.create_collection(drop_existing=rebuild_index)

        texts = [doc.get("content", "") for doc in documents]
        metadatas = [doc.get("metadata", {}) for doc in documents]

        logger.info(f"Encoding {len(documents)} documents...")
        embeddings = self.encode_texts(texts)

        entities = [texts, metadatas, embeddings.tolist()]
        self.collection.insert(entities)
        self.collection.flush()

        if rebuild_index or not self._has_index():
            self.build_index()

        logger.info(f"Indexed {len(documents)} documents to Milvus")

    def _has_index(self) -> bool:
        if self.collection is None:
            return False
        try:
            return len(self.collection.indexes) > 0
        except:
            return False

    def search(self, query: str, top_k: int = 5) -> List[Tuple[int, float, Dict]]:
        if self.collection is None:
            self.create_collection()

        query_vector = self.encode_single(query).reshape(1, -1).tolist()

        if self.index_type == "HNSW":
            search_params = {"metric_type": self.metric_type, "params": {"ef": 64}}
        else:
            search_params = {"metric_type": self.metric_type, "params": {}}

        try:
            results = self.collection.search(
                data=query_vector,
                anns_field="vector",
                param=search_params,
                limit=top_k,
                output_fields=["content", "metadata", "id"]
            )
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

        output = []
        for hits in results:
            for hit in hits:
                distance = hit.distance
                similarity = distance if self.metric_type == "IP" else 1 / (1 + distance)
                output.append((
                    int(hit.id),
                    float(similarity),
                    {
                        "content": hit.entity.get("content", ""),
                        "metadata": hit.entity.get("metadata", {})
                    }
                ))

        return output

    def get_stats(self) -> Dict[str, Any]:
        if self.collection is None:
            return {"status": "not_connected"}
        try:
            return {
                "collection_name": self.collection_name,
                "dimension": self.dimension,
                "index_type": self.index_type,
                "num_entities": self.collection.num_entities,
                "status": "connected"
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
