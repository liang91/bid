from services.supplier_service import SupplierService


class TestSupplierService:
    def test_update_profile_embedding(self):
        res = SupplierService.update_profile_embedding(1)
        print(res)

    def test_set_profile_embeddings(self):
        SupplierService.set_profile_embeddings()