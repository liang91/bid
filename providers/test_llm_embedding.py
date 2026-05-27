from providers import LLMEmbedding
import json


class TestEmbeddingService:
    def test_embedding(self):
        embedding = LLMEmbedding.embed("hello world")
        print(json.dumps(embedding))
