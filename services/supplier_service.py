from dao import SupplierDao
from providers import LLMEmbedding


class SupplierService:

    @staticmethod
    def set_profile_embeddings():
        suppliers = SupplierDao.unembed()
        for supplier in suppliers:
            SupplierService.update_profile_embedding(supplier.id)

    @staticmethod
    def update_profile_embedding(supplier_id: int) -> bool:
        supplier = SupplierDao.get(supplier_id)
        if not supplier:
            return False
        profile = f"公司业务范围：{supplier.business_scope}。具备的资质：{supplier.qualification_summary}"
        vector = LLMEmbedding.embed(profile)
        return SupplierDao.update_embedding(supplier.id, vector)
