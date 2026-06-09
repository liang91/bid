from services import SupplierService


class TestSupplierService:
    def test_update_profile_embedding(self):
        res = SupplierService.update_profile_embedding(1)
        print(res)

    def test_set_profile_embeddings(self):
        SupplierService.set_profile_embeddings()

    def test_filter_for_one(self):
        res = SupplierService.filter_for_one(6)
        print(res)

    def test_filter_for_all(self):
        res = SupplierService.filter_for_all()
        print(res)

    def test_match_for_one(self):
        SupplierService.match_for_one(18)

    def test_match_for_all(self):
        SupplierService.match_for_all()
