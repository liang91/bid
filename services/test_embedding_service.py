from services.embedding_service import EmbeddingService
import json


class TestEmbeddingService:
    def test_embedding(self):
        embedding = EmbeddingService.embed("hello world")
        print(json.dumps(embedding))
