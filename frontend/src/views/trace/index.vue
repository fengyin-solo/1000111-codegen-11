<template>
  <section class="page" data-module="trace">
    <header class="page-head">
      <div>
        <h2>批次追溯管理</h2>
        <p class="page-desc">维护追溯记录，围绕追溯码、货物名称、生产批次、上游供应商做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记追溯记录</button>
        <button class="btn" type="button" @click="exportRows">下载追溯码清单</button>
        <button class="btn" type="button" @click="triggerImport">导入追溯码清单</button>
        <input
          ref="fileInput"
          class="visually-hidden"
          type="file"
          accept=".csv,text/csv"
          @change="handleImport"
        />
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
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
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
          <td :colspan="columns.length + 1" class="empty-state">{{ emptyText }}</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条批次追溯记录</span>
      <span v-if="noticeMessage" class="ok-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/trace'
const columns = ["追溯码", "货物名称", "生产批次", "上游供应商", "入库单号", "全程温度区间", "追溯状态"]
const actions = ["关联上游", "发布追溯", "撤回追溯"]
const statuses = ["待关联", "已关联", "已发布", "已撤回"]
const stats = [{"label": "追溯码总量", "value": 0}, {"label": "待关联追溯", "value": 0}, {"label": "已发布追溯", "value": 0}]
// 过滤框与列表接口查询参数的对应关系，下载清单时复用同一套条件。
const FILTER_PARAMS: Record<string, string> = { 追溯码: 'keyword', 货物名称: 'goods', 生产批次: 'batch' }

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const fileInput = ref<HTMLInputElement | null>(null)

const hasActiveFilters = computed(() =>
  Object.values(filters.value).some((value) => String(value ?? '').trim() !== ''),
)
const emptyText = computed(() =>
  hasActiveFilters.value
    ? '当前过滤条件下没有匹配的追溯记录，可调整条件后重新查询'
    : '暂无批次追溯数据，可先登记追溯记录',
)

function buildQuery(): string {
  const params = new URLSearchParams()
  for (const [field, value] of Object.entries(filters.value)) {
    const key = FILTER_PARAMS[field]
    const keyword = String(value ?? '').trim()
    if (key && keyword) {
      params.set(key, keyword)
    }
  }
  return params.toString()
}

function resetFilters() {
  filters.value = {}
  void reload()
}

async function exportRows() {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/export?${buildQuery()}`)
    if (!response.ok) {
      const payload = await response.json().catch(() => null)
      throw new Error(payload?.detail ?? '追溯码清单生成失败，请稍后重试')
    }
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = '追溯码清单.csv'
    link.click()
    URL.revokeObjectURL(url)
    noticeMessage.value = '追溯码清单已下载，可填写上游供应商后重新导入'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '追溯码清单下载失败'
  }
}

function triggerImport() {
  fileInput.value?.click()
}

async function handleImport(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) {
    return
  }
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const content = await file.text()
    const response = await request(`${ENDPOINT}/import`, {
      method: 'POST',
      body: JSON.stringify({ filename: file.name, content }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message ?? payload?.detail ?? '追溯码清单导入失败，请检查文件内容')
    }
    noticeMessage.value = String(payload.message)
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '追溯码清单导入失败'
  }
}

function openCreate() {
  errorMessage.value = '追溯记录登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('批次追溯动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '批次追溯操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}?${buildQuery()}`)
    if (!response.ok) {
      throw new Error('追溯记录列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '批次追溯列表读取失败'
  }
}

onMounted(reload)
</script>
