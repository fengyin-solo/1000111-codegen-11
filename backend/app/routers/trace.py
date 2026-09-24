"""批次追溯接口：维护追溯记录，覆盖关联上游、发布追溯、撤回追溯等动作。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

from app.schemas import ActionResult, EntryPayload, ImportPayload, PageResult
from app.services.trace import TraceService

router = APIRouter(prefix="/api/trace", tags=["批次追溯"])

service = TraceService()

LIST_FIELDS = ["追溯码", "货物名称", "生产批次", "上游供应商", "入库单号", "全程温度区间", "追溯状态"]
STATUSES = ["待关联", "已关联", "已发布", "已撤回"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按追溯码检索"),
    status: str | None = Query(default=None, description="待关联、已关联、已发布、已撤回"),
    goods: str | None = Query(default=None, description="按货物名称检索"),
    batch: str | None = Query(default=None, description="按生产批次检索"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按追溯码与状态过滤批次追溯列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, goods=goods, batch=batch, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries(
    keyword: str | None = Query(default=None, description="按追溯码检索"),
    status: str | None = Query(default=None, description="待关联、已关联、已发布、已撤回"),
    goods: str | None = Query(default=None, description="按货物名称检索"),
    batch: str | None = Query(default=None, description="按生产批次检索"),
) -> Response:
    """下载追溯码清单：把当前过滤出的记录打包成 CSV，含追溯码、生产批次、上游供应商、全程温度区间。"""
    content, total = service.build_manifest(keyword=keyword, status=status, goods=goods, batch=batch)
    if total == 0:
        raise HTTPException(status_code=404, detail="当前过滤条件下没有追溯记录，未生成追溯码清单")
    return Response(
        content=content.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="trace-code-manifest.csv"'},
    )


@router.post("/import", response_model=ActionResult)
def import_entries(payload: ImportPayload) -> ActionResult:
    """再导入追溯码清单：按追溯码补齐上游供应商，重复追溯码只更新不新增；缺必填列时说明原因并中止。"""
    stats, message = service.import_manifest(payload.content)
    if stats is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=stats)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条追溯记录明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"追溯记录 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条追溯记录，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="追溯记录已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条追溯记录执行关联上游、发布追溯、撤回追溯；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
