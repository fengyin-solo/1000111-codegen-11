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

# 清单文件（下载/再导入共用）的列：追溯码、生产批次、上游供应商、全程温度区间
LIST_COLUMNS = ["追溯码", "生产批次", "上游供应商", "全程温度区间"]


class TraceImportError(Exception):
    """清单文件不满足导入前提（缺列、空文件等），需要中止并把原因告诉用户。"""


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
        rows = self._filter_rows(keyword=keyword, status=status, goods=goods, batch=batch)
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

    def export_rows(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        goods: str | None = None,
        batch: str | None = None,
    ) -> list[dict[str, Any]]:
        """按当前过滤条件取全量记录，只保留清单文件需要的几列，列序固定。"""
        return [
            {column: row.get(column, "") for column in LIST_COLUMNS}
            for row in self._filter_rows(keyword=keyword, status=status, goods=goods, batch=batch)
        ]

    def build_csv(self, rows: list[dict[str, Any]]) -> str:
        """把清单记录写成带 BOM 的 CSV，保证 Excel 打开中文不乱码。"""
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=LIST_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in LIST_COLUMNS})
        return "\ufeff" + buffer.getvalue()

    def import_rows(self, content: str) -> dict[str, int]:
        """按追溯码补齐缺失的上游供应商：只更新命中的记录，重复追溯码只更新不新增。

        返回命中、补齐、跳过等计数；文件缺少必填列或无法识别时抛 TraceImportError 中止。
        """
        if not content.strip():
            raise TraceImportError("导入文件为空，请使用包含表头的数据文件")
        try:
            reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
        except csv.Error as exc:
            raise TraceImportError(f"文件解析失败：{exc}") from exc
        fieldnames = reader.fieldnames or []
        missing = [column for column in LIST_COLUMNS if column not in fieldnames]
        if missing:
            raise TraceImportError(
                f"导入文件缺少必填列：{'、'.join(missing)}；"
                f"必填列应为 {'、'.join(LIST_COLUMNS)}，请检查后重新导入"
            )
        rows = store.rows(MODULE)
        index = {str(row.get("追溯码", "")).strip(): row for row in rows if str(row.get("追溯码", "")).strip()}

        matched = updated = unchanged = skipped = unmatched = 0
        for raw in reader:
            code = str(raw.get("追溯码") or "").strip()
            if not code:
                skipped += 1  # 空行/追溯码缺失，无法定位记录
                continue
            entry = index.get(code)
            if entry is None:
                unmatched += 1  # 系统里没有这条追溯码，导入只补齐不新增
                continue
            matched += 1
            supplier = str(raw.get("上游供应商") or "").strip()
            if supplier and not str(entry.get("上游供应商") or "").strip():
                entry["上游供应商"] = supplier
                updated += 1
            else:
                unchanged += 1
        if matched == 0 and skipped == 0 and unmatched == 0:
            raise TraceImportError("导入文件没有可识别的数据行，请检查文件内容")
        return {
            "matched": matched,
            "updated": updated,
            "unchanged": unchanged,
            "unmatched": unmatched,
            "skipped": skipped,
        }

    def _filter_rows(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        goods: str | None = None,
        batch: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("追溯码", ""))]
        if goods:
            rows = [row for row in rows if goods in str(row.get("货物名称", ""))]
        if batch:
            rows = [row for row in rows if batch in str(row.get("生产批次", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        return rows
