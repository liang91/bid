from decimal import Decimal

from pydantic import TypeAdapter
from dao import SupplierDao
from models import SupplierDto


class TestSupplierDao:

    def test_create(self):
        dto = SupplierDto(
            company_name='北京行者明达科技有限公司',
            company_scale="小微",
            province="北京",
            city="北京",
            district="昌平",
            sme_status=0,
            ca_ready=0,
            business_scopes=["软件开发,网站开发"],
            service_regions=['北京'],
            qualifications=['ICP经营许可证'],
            min_budget=10000,
            max_budget=1000000,
            preferred_methods="公开招标",
        )
        id = SupplierDao.create(dto)
        print(id)

    def test_get_by_id(self):
        res = SupplierDao.get(1)
        if res:
            print(res.model_dump_json())

    def test_unembed(self):
        suppliers = SupplierDao.unembed()
        adapter = TypeAdapter(list[SupplierDto])
        res = adapter.dump_json(suppliers).decode('utf-8')
        print(res)

