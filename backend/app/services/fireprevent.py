"""防灭火业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "fireprevent"

# 登记字段沿用台账原有的中文命名：前三个为必填，其余填了就落库、没填留空。
REQUIRED_FIELDS = ["监测编号", "所在区域", "束管监测"]
OPTIONAL_FIELDS = ["标志气体", "温度异常", "注浆量", "注氮量"]
ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS

STATUS_ORDER = ["正常", "指标异常", "高温预警", "已处置"]
# 哪些动作会把记录标记为异常：概览的异常量按动作后的状态重算。
NEGATIVE_TARGETS = ["指标异常", "高温预警"]
ACTION_RULES = {"指标预警": "指标异常", "高温报警": "高温预警", "处置确认": "已处置"}

# 历史记录回填时的缺失标记字段，直接挂在防火台账记录上。
MISSING_MARK_FIELD = "缺失字段"
MISSING_REASON_FIELD = "缺失说明"


def _is_blank(value: Any) -> bool:
    return value is None or not str(value).strip()


def _abnormal_for_status(status: str) -> bool:
    return status in NEGATIVE_TARGETS


class FirepreventService:
    def __init__(self) -> None:
        # 内存仓库里的历史数据按当时的提交内容回填一遍：
        # 补不回来的非必填字段留空并在台账上标出原因，异常量同步重算。
        self._normalize_legacy_rows()

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        area: str | None = None,
        tube: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("监测编号", ""))]
        if area:
            rows = [row for row in rows if area in str(row.get("所在区域") or "")]
        if tube:
            rows = [row for row in rows if tube in str(row.get("束管监测") or "")]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(
        self, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, list[str], bool]:
        """登记一条防火监测。

        返回 (记录, 缺失的必填字段, 是否重复编号)。
        重复登记只认第一次提交的内容：原样返回首条记录，本次提交不落库。
        """
        code = str(values.get("监测编号") or "").strip()
        if code:
            existing = next(
                (
                    row
                    for row in store.rows(MODULE)
                    if str(row.get("监测编号") or "").strip() == code
                ),
                None,
            )
            if existing is not None:
                return existing, [], True

        missing = [field for field in REQUIRED_FIELDS if _is_blank(values.get(field))]
        if missing:
            return None, missing, False

        rows = store.rows(MODULE)
        entry: dict[str, Any] = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1
        }
        for field in ALL_FIELDS:
            value = values.get(field)
            entry[field] = None if _is_blank(value) else str(value).strip()
        # 登记、详情、列表读到的是同一份记录：状态两处保持同步。
        entry["status"] = STATUS_ORDER[0]
        entry["防火状态"] = entry["status"]
        entry["pending"] = True
        entry["abnormal"] = _abnormal_for_status(entry["status"])
        rows.append(entry)
        return entry, [], False

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"防火监测 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于防灭火可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        # 动作只改状态口径，登记时提交的业务字段原样保留，不再出现填完丢失。
        entry["status"] = target
        entry["防火状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = _abnormal_for_status(target)
        return entry, f"防火监测已{action}"

    def _normalize_legacy_rows(self) -> None:
        """历史记录回填：按当时提交内容补齐字段，缺失处留空并写明原因。"""
        for row in store.rows(MODULE):
            missing: list[str] = []
            for field in ALL_FIELDS:
                # 束管监测是必填：历史记录若连它都没有，说明当时登记链路丢过字段。
                if field not in row or row.get(field) is None:
                    row[field] = None
                    if field in OPTIONAL_FIELDS:
                        missing.append(field)
            status = str(row.get("status") or STATUS_ORDER[0])
            if status not in STATUS_ORDER:
                status = STATUS_ORDER[0]
            row["status"] = status
            row["防火状态"] = status
            # 异常量跟着记录重算：指标异常、高温预警计为异常，处置后解除。
            row["abnormal"] = _abnormal_for_status(status)
            row["pending"] = status != STATUS_ORDER[-1]
            if missing:
                row[MISSING_MARK_FIELD] = "、".join(missing)
                row[MISSING_REASON_FIELD] = "历史登记仅保存了必填字段，该字段在旧链路中未落库，无法按原提交内容补回"
            else:
                row[MISSING_MARK_FIELD] = None
                row[MISSING_REASON_FIELD] = None
