from providers import LLMEmbedding


class TestEmbeddingService:
    def test_cosine_similarity(self):
        vector1 = LLMEmbedding.embed("我喜欢学英语")
        vector2 = LLMEmbedding.embed("我讨厌学英语")
        res = LLMEmbedding.similarity(vector1, vector2)
        print(res)

    def test_similarity_matrix(self):

        king = LLMEmbedding.embed("国王")
        president = LLMEmbedding.embed("总统")
        leader = LLMEmbedding.embed("领主")
        slave = LLMEmbedding.embed("奴隶")

        candidate_vec = [
            president,
            leader,
            slave
        ]
        print('国王 vs 总统', LLMEmbedding.similarity(king, president))
        print('国王 vs 领主', LLMEmbedding.similarity(king, leader))
        print('国王 vs 奴隶', LLMEmbedding.similarity(king, slave))
        res = LLMEmbedding.similarities(king, candidate_vec)
        print(res)

