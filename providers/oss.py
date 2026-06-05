"""阿里云 OSS 客户端封装（基于 alibabacloud-oss-v2）.

提供上传、下载等常用 OSS 操作，所有状态通过类变量维护，无需实例化。

使用方式：
    from providers.oss import OSS
    OSS.put("local/path.txt", "remote/path.txt")
    OSS.get("remote/path.txt", "local/path.txt")
"""

import os
import alibabacloud_oss_v2 as oss
from loguru import logger

from config import config


class OSS:
    """阿里云 OSS 客户端封装.

    所有状态通过类变量维护，无需实例化：
        OSS.put(local, remote) # 上传文件
        OSS.get(remote, local) # 下载文件
    """
    # OSS 客户端（类加载时自动初始化）
    _cfg = oss.config.load_default()
    _cfg.credentials_provider = oss.credentials.StaticCredentialsProvider(
        access_key_id=config.get("aliyun.access_key_id"),
        access_key_secret=config.get("aliyun.access_key_secret"),
    )
    _cfg.region = config.get("oss.region")
    _cfg.endpoint = config.get("oss.endpoint")
    client: oss.Client = oss.Client(_cfg)
    bucket: str = config.get("oss.bucket")
    logger.info(f"OSS客户端已初始化")

    @classmethod
    def put(cls, local_path: str, remote_key: str) -> bool:
        """上传本地文件到 OSS.
        Args:
            local_path: 本地文件路径
            remote_key: OSS 中的对象 Key（路径）
        Returns:
            上传是否成功
        """
        try:
            result = cls.client.put_object_from_file(
                oss.PutObjectRequest(bucket=cls.bucket, key=remote_key),
                filepath=local_path,
            )
            logger.info(
                f"[OSS] 上传成功: {local_path} -> {remote_key} "
                f"(status={result.status_code}, request_id={result.request_id})"
            )
            return True
        except Exception as e:
            logger.error(f"[OSS] 上传异常: {e}")
            return False

    @classmethod
    def get(cls, remote_key: str, local_path: str) -> bool:
        """从 OSS 下载文件到本地.
        Args:
            remote_key: OSS 中的对象 Key（路径）
            local_path: 本地保存路径
        Returns:
            下载是否成功
        """
        try:
            result = cls.client.get_object(oss.GetObjectRequest(bucket=cls.bucket, key=remote_key))

            # 确保目标目录存在
            dir_name = os.path.dirname(local_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)

            with result.body as body_stream:
                with open(local_path, "wb") as f:
                    f.write(body_stream.read())

            logger.info(
                f"[OSS] 下载成功: {remote_key} -> {local_path} "
                f"(status={result.status_code}, request_id={result.request_id})"
            )
            return True
        except Exception as e:
            logger.error(f"[OSS] 下载异常: {e}")
            return False

    @classmethod
    def object_exists(cls, remote_key: str) -> bool:
        """检查 OSS 对象是否存在.

        Args:
            remote_key: OSS 中的对象 Key（路径）

        Returns:
            对象是否存在
        """
        try:
            result = cls.client.head_object(
                oss.HeadObjectRequest(bucket=cls.bucket, key=remote_key)
            )
            return result.status_code == 200
        except Exception as e:
            logger.error(f"[OSS] 检查对象存在性异常: {e}")
            return False

    @classmethod
    def delete_object(cls, remote_key: str) -> bool:
        """删除 OSS 对象.

        Args:
            remote_key: OSS 中的对象 Key（路径）

        Returns:
            删除是否成功
        """
        try:
            result = cls.client.delete_object(
                oss.DeleteObjectRequest(bucket=cls.bucket, key=remote_key)
            )
            logger.info(
                f"[OSS] 删除成功: {remote_key} "
                f"(status={result.status_code}, request_id={result.request_id})"
            )
            return True
        except Exception as e:
            logger.error(f"[OSS] 删除异常: {e}")
            return False

    @classmethod
    def url(cls, remote_key: str, expires: int = 3600) -> str | None:
        """生成带签名的临时访问 URL.

        Args:
            remote_key: OSS 中的对象 Key（路径）
            expires: URL 有效期（秒），默认 1 小时

        Returns:
            签名 URL，失败时返回 None
        """
        try:
            url = cls.client.presign(
                oss.GetObjectRequest(bucket=cls.bucket, key=remote_key),
                expires=expires,
            )
            return url
        except Exception as e:
            logger.error(f"[OSS] 生成 URL 失败: {e}")
            return None
