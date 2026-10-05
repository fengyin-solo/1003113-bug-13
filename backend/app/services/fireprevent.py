"""防灭火业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "fireprevent"
REQUIRED_FIELDS = ["监测编号", "所在区域", "束管监测"]
OPTIONAL_FIELDS = ["标志气体", "温度异常", "注浆量", "注氮量", "防火状态"]
ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS
STATUS_ORDER = ["正常", "指标异常", "高温预警", "已处置"]
ABNORMAL_STATUSES = ["指标异常", "高温预警"]
ACTION_RULES = {"指标预警": "指标异常", "高温报警": "高温预警", "处置确认": "已处置"}
NEGATIVE_ACTIONS = []
MISSING_NOTE_KEY = "缺失说明"


def _normalize(value: Any) -> Any:
    """空白字符串按未填写处理（留空为 None），其余内容去首尾空白后原样保留。"""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    return value


class FirepreventService:
    def __init__(self) -> None:
        # 启动时先修一遍历史记录：能回填的回填，补不回来的在台账里标注。
        self.repair_entries()

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("监测编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str], bool]:
        """登记一条防火监测。

        返回 (记录, 缺失的必填字段, 是否新建)。必填字段缺一不可；非必填字段填了就
        落库、没填就留空；监测编号重复时只认第一次提交的内容，直接返回已有记录。
        """
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, False
        rows = store.rows(MODULE)
        code = str(values.get("监测编号")).strip()
        for row in rows:
            if str(row.get("监测编号", "")).strip() == code:
                return row, [], False
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: _normalize(values.get(field)) for field in ALL_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, [], True

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"防火监测 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于防灭火可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        # 异常标记跟着记录当前状态重算，运营概览的异常量才能跟着这些记录走。
        entry["abnormal"] = target in ABNORMAL_STATUSES or action in NEGATIVE_ACTIONS
        return entry, f"防火监测已{action}"

    def repair_entries(self) -> None:
        """修复历史记录：已有内容按当时提交原样保留，缺漏字段补不回来就在台账标注。

        老登记链路只落了必填三项，非必填字段的提交内容没有存下来，无法找回，
        这类字段补空值并在「缺失说明」里写明字段与原因；同时按记录当前状态
        重算异常标记，让运营概览的异常量跟着记录走。
        """
        for row in store.rows(MODULE):
            lost = [field for field in ALL_FIELDS if field not in row]
            for field in lost:
                row[field] = None
            if lost:
                row[MISSING_NOTE_KEY] = (
                    f"缺失字段：{'、'.join(lost)}（历史登记时未落库，"
                    "当时的提交内容已无法找回，按留空处理）"
                )
            row["abnormal"] = row.get("status") in ABNORMAL_STATUSES
