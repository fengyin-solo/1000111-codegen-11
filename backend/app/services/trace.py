"""批次追溯业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

import csv
import io
from typing import Any

from app.store import store

MODULE = "trace"
REQUIRED_FIELDS = ["追溯码", "货物名称", "生产批次"]
STATUS_ORDER = ["待关联", "已关联", "已发布", "已撤回"]
ACTION_RULES = {"关联上游": "已关联", "发布追溯": "已发布", "撤回追溯": "已撤回"}
NEGATIVE_ACTIONS = []

# 追溯码清单（下载/再导入）的列口径：追溯码是匹配键，上游供应商是导入要补齐的目标。
MANIFEST_FIELDS = ["追溯码", "生产批次", "上游供应商", "全程温度区间"]


class TraceService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        goods: str | None = None,
        batch: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("追溯码", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if goods:
            rows = [row for row in rows if goods in str(row.get("货物名称", ""))]
        if batch:
            rows = [row for row in rows if batch in str(row.get("生产批次", ""))]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"追溯记录 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于批次追溯可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"追溯记录已{action}"

    def build_manifest(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        goods: str | None = None,
        batch: str | None = None,
    ) -> tuple[str, int]:
        """把当前过滤出的追溯记录整理成追溯码清单 CSV，列口径固定为 MANIFEST_FIELDS。"""
        rows, total = self.list_entries(keyword=keyword, status=status, goods=goods, batch=batch, page=1, size=10000)
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\r\n")
        writer.writerow(MANIFEST_FIELDS)
        for row in rows:
            writer.writerow([str(row.get(field) or "") for field in MANIFEST_FIELDS])
        return buffer.getvalue(), total

    def import_manifest(self, content: str) -> tuple[dict[str, int] | None, str]:
        """按追溯码把清单里的上游供应商补回系统；只更新已有记录，不新增。

        返回 (统计, 说明)；缺少必填列时统计为 None，说明里写清中止原因。
        """
        text = content.lstrip("\ufeff")
        if not text.strip():
            return None, "导入文件内容为空，已中止导入"
        reader = csv.DictReader(io.StringIO(text))
        headers = [str(name or "").strip() for name in (reader.fieldnames or [])]
        missing = [field for field in MANIFEST_FIELDS if field not in headers]
        if missing:
            return None, f"导入文件缺少必填列：{'、'.join(missing)}，已中止导入，请使用下载的追溯码清单"

        rows = store.rows(MODULE)
        by_code = {str(row.get("追溯码") or "").strip(): row for row in rows}
        stats = {"updated": 0, "unmatched": 0, "invalid": 0}
        for line in reader:
            code = str(line.get("追溯码") or "").strip()
            if not code:
                stats["invalid"] += 1
                continue
            entry = by_code.get(code)
            if entry is None:
                stats["unmatched"] += 1
                continue
            supplier = str(line.get("上游供应商") or "").strip()
            if supplier:
                entry["上游供应商"] = supplier
                stats["updated"] += 1
            else:
                stats["invalid"] += 1

        message = (
            f"导入完成：更新 {stats['updated']} 条记录的上游供应商，"
            f"{stats['unmatched']} 个追溯码未匹配已跳过，"
            f"{stats['invalid']} 行缺少追溯码或供应商已忽略"
        )
        return stats, message
