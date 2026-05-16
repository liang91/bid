"""数据存储模块."""
import json
from datetime import datetime
from pathlib import Path
from typing import List

from .models import BidNotice


class Storage:
    """招标信息存储器."""

    def __init__(self, output_dir: str = "data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._seen_urls = set()

    def _generate_filename(self, suffix: str) -> str:
        """生成带时间戳的文件名."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"ccgp_bids_{timestamp}.{suffix}"

    def dedup(self, notices: List[BidNotice]) -> List[BidNotice]:
        """基于URL去重."""
        result = []
        for n in notices:
            if n.url not in self._seen_urls:
                self._seen_urls.add(n.url)
                result.append(n)
        return result

    def save_json(self, notices: List[BidNotice], filename: str = None) -> str:
        """保存为JSON文件."""
        if filename is None:
            filename = self._generate_filename("json")
        filepath = self.output_dir / filename

        data = [n.to_dict() for n in notices]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"[Storage] 已保存 {len(notices)} 条记录到 {filepath}")
        return str(filepath)

    def append_jsonl(self, notices: List[BidNotice], filename: str = "ccgp_bids.jsonl") -> str:
        """追加保存为JSON Lines格式（适合增量采集）."""
        filepath = self.output_dir / filename
        with open(filepath, "a", encoding="utf-8") as f:
            for n in notices:
                f.write(json.dumps(n.to_dict(), ensure_ascii=False) + "\n")
        print(f"[Storage] 已追加 {len(notices)} 条记录到 {filepath}")
        return str(filepath)
