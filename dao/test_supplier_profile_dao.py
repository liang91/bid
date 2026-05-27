from decimal import Decimal

from pydantic import TypeAdapter
from dao import SupplierProfileDao
from models import SupplierProfileDto, SupplierQualification


class TestSupplierProfileDao:

    def test_create(self):
        dto = SupplierProfileDto(
            company_name='北京行者明达科技有限公司',
            company_scale="小微",
            province="北京",
            city="北京",
            district="昌平",
            sme_status=0,
            ca_ready=0,
            business_scope="软件开发,网站开发",
            service_regions=['北京'],
            qualifications=[SupplierQualification(name='ICP经营许可证', cert_no='110', valid_until='2100-10-20')],
            qualification_summary="ICP经营许可证+人力资源服务许可证",
            min_budget=Decimal("10000"),
            max_budget=Decimal("1000000"),
            preferred_methods="公开招标",
        )
        id = SupplierProfileDao.create(dto)
        print(id)

    def test_get_by_id(self):
        res = SupplierProfileDao.get_by_id(1)
        if res:
            print(res.model_dump_json())

    def test_list(self):
        all = SupplierProfileDao.list_all()
        adapter = TypeAdapter(list[SupplierProfileDto])
        print(adapter.dump_json(all).decode('utf-8'))
