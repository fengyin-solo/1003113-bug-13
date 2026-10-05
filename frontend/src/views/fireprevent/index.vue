<template>
  <section class="page" data-module="fireprevent">
    <header class="page-head">
      <div>
        <h2>防灭火管理</h2>
        <p class="page-desc">维护防火监测，围绕监测编号、所在区域、束管监测、标志气体做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记防火监测</button>
        <button class="btn" type="button" @click="exportRows">导出防灭火清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>台账备注</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="note-cell">{{ row['缺失说明'] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">详情</button>
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 2" class="empty-state">暂无防灭火数据，可先登记防火监测</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条防灭火记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="createVisible" class="modal-mask" @click.self="closeCreate">
      <form class="modal-card" @submit.prevent="submitCreate">
        <h3 class="modal-title">登记防火监测</h3>
        <label v-for="field in createFields" :key="field.name" class="modal-item">
          <span>
            {{ field.name }}
            <em v-if="field.required" class="required-mark">*</em>
            <i v-else class="optional-mark">选填</i>
          </span>
          <input
            v-model="createForm[field.name]"
            :placeholder="field.required ? `必填，填写${field.name}` : `选填，不填则留空`"
          />
        </label>
        <p class="modal-hint">非必填字段填了就保存、没填就留空；监测编号重复时只认第一次提交的内容。</p>
        <p v-if="createError" class="error-text">{{ createError }}</p>
        <div class="modal-actions">
          <button class="btn primary" type="submit">保存登记</button>
          <button class="btn ghost" type="button" @click="closeCreate">取消</button>
        </div>
      </form>
    </div>

    <div v-if="detail" class="modal-mask" @click.self="closeDetail">
      <div class="modal-card">
        <h3 class="modal-title">防火监测详情</h3>
        <dl class="detail-list">
          <template v-for="field in detailFields" :key="field">
            <dt>{{ field }}</dt>
            <dd>{{ detail[field] ?? '—' }}</dd>
          </template>
          <dt>当前状态</dt>
          <dd>{{ detail.status ?? '—' }}</dd>
        </dl>
        <p v-if="detail['缺失说明']" class="error-text">{{ detail['缺失说明'] }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="closeDetail">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/fireprevent'
const columns = ["监测编号", "所在区域", "束管监测", "标志气体", "温度异常", "注浆量", "注氮量", "防火状态"]
const actions = ["指标预警", "高温报警", "处置确认"]
const statuses = ["正常", "指标异常", "高温预警", "已处置"]
const stats = [{"label": "正常区域", "value": 0}, {"label": "异常区域", "value": 0}, {"label": "预警区域", "value": 0}]
// 与后端接口约定的字段名保持一致：前三个必填，其余选填，提交时原样放进 values。
const createFields = [
  { name: "监测编号", required: true },
  { name: "所在区域", required: true },
  { name: "束管监测", required: true },
  { name: "标志气体", required: false },
  { name: "温度异常", required: false },
  { name: "注浆量", required: false },
  { name: "注氮量", required: false },
  { name: "防火状态", required: false },
]
const detailFields = columns

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const createVisible = ref(false)
const createForm = ref<Record<string, string>>({})
const createError = ref('')
const detail = ref<Row | null>(null)

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = {}
  createError.value = ''
  createVisible.value = true
}

function closeCreate() {
  createVisible.value = false
}

function closeDetail() {
  detail.value = null
}

async function readPayload(response: Response): Promise<{ ok?: boolean; message?: string; detail?: string }> {
  try {
    return (await response.json()) as { ok?: boolean; message?: string; detail?: string }
  } catch {
    return {}
  }
}

async function submitCreate() {
  createError.value = ''
  const values: Record<string, string> = {}
  for (const field of createFields) {
    const text = (createForm.value[field.name] ?? '').trim()
    if (field.required && !text) {
      createError.value = `请填写必填字段：${field.name}`
      return
    }
    if (text) {
      values[field.name] = text
    }
  }
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = await readPayload(response)
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.message ?? payload.detail ?? '防火监测登记失败')
    }
    closeCreate()
    noticeMessage.value = payload.message ?? '防火监测已登记'
    errorMessage.value = ''
    await reload()
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '防火监测登记失败'
  }
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      const payload = await readPayload(response)
      throw new Error(payload.detail ?? '防火监测详情读取失败')
    }
    detail.value = (await response.json()) as Row
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '防火监测详情读取失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await readPayload(response)
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.message ?? payload.detail ?? '防灭火动作未生效，请稍后重试')
    }
    noticeMessage.value = payload.message ?? `防火监测已${action}`
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '防灭火操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('防火监测列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '防火监测列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}
.modal-card {
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px;
  width: 420px;
  max-height: 80vh;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.modal-title {
  margin: 0;
  font-size: 15px;
}
.modal-item span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 2px;
}
.modal-item input {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
}
.required-mark {
  color: #b42318;
  font-style: normal;
}
.optional-mark {
  color: var(--muted);
  font-style: normal;
  font-size: 11px;
  margin-left: 4px;
}
.modal-hint {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
}
.modal-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.detail-list {
  margin: 0;
  display: grid;
  grid-template-columns: 96px 1fr;
  row-gap: 6px;
  font-size: 13px;
}
.detail-list dt {
  color: var(--muted);
}
.detail-list dd {
  margin: 0;
}
.note-cell {
  color: #b42318;
  font-size: 12px;
}
.notice-text {
  color: #067647;
}
</style>
