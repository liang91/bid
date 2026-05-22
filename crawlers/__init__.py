"""政府采购网或公共资源交易平台爬虫包."""
from config import config
from volcenginesdkarkruntime import Ark

# llm模型客户端
llm_client = Ark(
    base_url=config.get("llm.base_url"),
    api_key=config.get("llm.api_key")
)
# llm所用模型名称
llm_model = config.get("llm.model")
