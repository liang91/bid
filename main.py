"""FastAPI 应用入口.

启动方式（开发，单进程）:
    python main.py

启动方式（生产，多进程，推荐）:
    gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
"""

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.schemas import Res
from api.feed_controller import FeedController
from api.notice_controller import NoticeController
from api.user_controller import UserController
from api.supplier_controller import SupplierController

app = FastAPI(
    title="公装招标推荐 API",
    description="公装招标信息推荐小程序后端接口",
    version="1.0.0",
)

# CORS（开发阶段允许所有来源，生产环境需收紧）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────
# 全局异常处理：统一返回 {code, msg, data} 结构
# ─────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """捕获所有未处理异常，返回统一格式."""
    return JSONResponse(
        status_code=500,
        content=Res(code=500, msg=str(exc), data=None).model_dump(),
    )


# ─────────────────────────────────────────
# 实例化 Controller 并注册路由，统一前缀 /api
# ─────────────────────────────────────────
app.include_router(FeedController().router, prefix="/api")
app.include_router(NoticeController().router, prefix="/api")
app.include_router(UserController().router, prefix="/api")
app.include_router(SupplierController().router, prefix="/api")


@app.post("/")
def root():
    return Res(data={"message": "公装招标推荐 API", "docs": "/docs"})


@app.post("/health")
def health():
    return Res(data={"status": "ok"})


if __name__ == "__main__":
    # workers: 进程数，建议等于 CPU 核心数
    # 多进程模式下第一个参数必须用字符串 "main:app"，不能传 app 对象
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        workers=4,
        limit_concurrency=100,
    )
    print("Hello World!")
