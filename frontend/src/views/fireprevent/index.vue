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
      <label class="filter-item">
        <span>防火状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="item in statuses" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <template v-if="column === '缺失字段'">
              <span v-if="row['缺失字段']" class="missing-tag" :title="String(row['缺失说明'] ?? '')">
                {{ row['缺失字段'] }}
              </span>
              <span v-else>—</span>
            </template>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td class="row-actions">
            <button
              v-for="item in actions"
              :key="item"
              class="link"
              type="button"
              @click="runAction(item, row)"
            >
              {{ item }}
            </button>
            <button class="link" type="button" @click="openDetail(row)">详情</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无防灭火数据，可先登记防火监测</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条防灭火记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <!-- 登记弹窗：字段名与接口约定一致，全部放进 values 提交 -->
    <div v-if="showCreate" class="modal-mask" @click.self="closeCreate">
      <div class="modal">
        <div class="modal-head">
          <h3>登记防火监测</h3>
          <button class="btn ghost" type="button" @click="closeCreate">关闭</button>
        </div>
        <form class="modal-body" @submit.prevent="submitCreate">
          <label v-for="field in formFields" :key="field.name" class="form-item">
            <span>{{ field.label }}<em v-if="field.required">*</em></span>
            <input
              v-model="form[field.name]"
              :placeholder="`请输入${field.label}${field.required ? '（必填）' : '（选填）'}`"
            />
          </label>
          <p v-if="formError" class="error-text">{{ formError }}</p>
          <div class="modal-foot">
            <button class="btn" type="button" @click="closeCreate">取消</button>
            <button class="btn primary" type="submit" :disabled="submitting">
              {{ submitting ? '提交中…' : '保存登记' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- 详情弹窗：直接读接口返回的同一份记录 -->
    <div v-if="detail" class="modal-mask" @click.self="detail = null">
      <div class="modal">
        <div class="modal-head">
          <h3>防火监测详情</h3>
          <button class="btn ghost" type="button" @click="detail = null">关闭</button>
        </div>
        <dl class="detail-list">
          <div v-for="field in detailFields" :key="field">
            <dt>{{ field }}</dt>
            <dd>{{ detail[field] ?? '—' }}</dd>
          </div>
          <div>
            <dt>缺失字段</dt>
            <dd>{{ detail['缺失字段'] ?? '—' }}</dd>
          </div>
          <div v-if="detail['缺失说明']">
            <dt>缺失说明</dt>
            <dd class="missing-reason">{{ detail['缺失说明'] }}</dd>
          </div>
        </dl>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/fireprevent'
const columns = ["监测编号", "所在区域", "束管监测", "标志气体", "温度异常", "注浆量", "注氮量", "防火状态", "缺失字段"]
const actions = ["指标预警", "高温报警", "处置确认"]
const statuses = ["正常", "指标异常", "高温预警", "已处置"]

// 非必填字段沿用台账原有的字段命名，不能再换名导致对不上。
const formFields = [
  { name: '监测编号', label: '监测编号', required: true },
  { name: '所在区域', label: '所在区域', required: true },
  { name: '束管监测', label: '束管监测', required: true },
  { name: '标志气体', label: '标志气体', required: false },
  { name: '温度异常', label: '温度异常', required: false },
  { name: '注浆量', label: '注浆量', required: false },
  { name: '注氮量', label: '注氮量', required: false },
] as const
const detailFields = ["监测编号", "所在区域", "束管监测", "标志气体", "温度异常", "注浆量", "注氮量", "防火状态"]

function emptyForm(): Record<string, string> {
  return Object.fromEntries(formFields.map((field) => [field.name, '']))
}

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const statusFilter = ref('')
const filterFields = columns.slice(0, 3)

const showCreate = ref(false)
const submitting = ref(false)
const formError = ref('')
const form = reactive<Record<string, string>>(emptyForm())
const detail = ref<Row | null>(null)

const stats = computed(() => [
  { label: '正常区域', value: rows.value.filter((row) => row['防火状态'] === '正常').length },
  { label: '异常区域', value: rows.value.filter((row) => row['防火状态'] === '指标异常').length },
  { label: '预警区域', value: rows.value.filter((row) => row['防火状态'] === '高温预警').length },
])

function resetFilters() {
  filters.value = {}
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  Object.assign(form, emptyForm())
  formError.value = ''
  showCreate.value = true
}

function closeCreate() {
  showCreate.value = false
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('防火监测详情读取失败')
    }
    detail.value = await response.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '防火监测详情读取失败'
  }
}

async function submitCreate() {
  formError.value = ''
  const values: Record<string, string | null> = {}
  for (const field of formFields) {
    const text = form[field.name].trim()
    values[field.name] = text ? text : null
  }
  submitting.value = true
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json().catch(() => null) as { ok?: boolean; message?: string } | null
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message || '防火监测登记失败，请检查必填项后重试')
    }
    showCreate.value = false
    errorMessage.value = payload.message || '防火监测已登记'
    await reload()
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '防火监测登记失败'
  } finally {
    submitting.value = false
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json().catch(() => null) as { ok?: boolean; message?: string } | null
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message || '防灭火动作未生效，请稍后重试')
    }
    errorMessage.value = payload.message || ''
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '防灭火操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const params: Record<string, string> = {}
  if (filters.value['监测编号']) params.keyword = filters.value['监测编号']
  if (filters.value['所在区域']) params['所在区域'] = filters.value['所在区域']
  if (filters.value['束管监测']) params['束管监测'] = filters.value['束管监测']
  if (statusFilter.value) params.status = statusFilter.value
  const query = new URLSearchParams(params).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('防火监测列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '防灭火列表读取失败'
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
  z-index: 100;
}

.modal {
  width: 560px;
  max-width: calc(100vw - 32px);
  max-height: 80vh;
  overflow: auto;
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px 20px;
}

.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.modal-head h3 {
  margin: 0;
  font-size: 16px;
}

.modal-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
}

.form-item em {
  color: #d9480f;
  font-style: normal;
  margin-left: 2px;
}

.form-item input,
.filter-item select {
  padding: 6px 8px;
  border: 1px solid var(--border, #d0d7de);
  border-radius: 6px;
}

.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 4px;
}

.detail-list {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
  margin: 0;
}

.detail-list div {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 8px;
  border-bottom: 1px dashed var(--border, #e5e9f0);
  padding-bottom: 6px;
}

.detail-list dt {
  color: #57606a;
}

.detail-list dd {
  margin: 0;
}

.missing-reason {
  color: #9a3412;
}

.missing-tag {
  color: #9a3412;
  border-bottom: 1px dotted #9a3412;
  cursor: help;
}
</style>
