<template>
  <section class="page" data-module="trace">
    <header class="page-head">
      <div>
        <h2>批次追溯管理</h2>
        <p class="page-desc">维护追溯记录，围绕追溯码、货物名称、生产批次、上游供应商做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记追溯记录</button>
        <button class="btn" type="button" :disabled="exporting" @click="exportRows">
          {{ exporting ? '正在生成…' : '下载追溯码清单' }}
        </button>
        <button class="btn" type="button" :disabled="importing" @click="triggerImport">
          {{ importing ? '正在导入…' : '导入追溯码清单' }}
        </button>
        <input
          ref="fileInput"
          type="file"
          accept=".csv,text/csv"
          hidden
          @change="onFilePicked"
        />
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <p v-if="importHint" class="import-hint">
      清单需包含「追溯码、生产批次、上游供应商、全程温度区间」四列；导入按追溯码补齐缺失的上游供应商，重复追溯码只更新不新增。
    </p>

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
          <td :colspan="columns.length + 1" class="empty-state">
            当前过滤条件下暂无批次追溯记录，可调整筛选条件后重试，或先登记追溯记录
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条批次追溯记录</span>
      <span v-if="successMessage" class="success-text">{{ successMessage }}</span>
      <span v-else-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/trace'
const columns = ["追溯码", "货物名称", "生产批次", "上游供应商", "入库单号", "全程温度区间", "追溯状态"]
const actions = ["关联上游", "发布追溯", "撤回追溯"]
const statuses = ["待关联", "已关联", "已发布", "已撤回"]
const stats = [{"label": "追溯码总量", "value": 0}, {"label": "待关联追溯", "value": 0}, {"label": "已发布追溯", "value": 0}]
const importHint = true

// 页面列名到后端查询参数的映射，保证列表过滤与清单下载用的是同一套条件
const FILTER_PARAMS: Record<string, string> = {
  追溯码: 'keyword',
  货物名称: 'goods',
  生产批次: 'batch',
}

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const successMessage = ref('')
const exporting = ref(false)
const importing = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const filters = ref<Record<string, string>>({})
const filterFields = Object.keys(FILTER_PARAMS)

function buildQuery() {
  const params = new URLSearchParams()
  for (const [field, param] of Object.entries(FILTER_PARAMS)) {
    const value = filters.value[field]?.trim()
    if (value) {
      params.set(param, value)
    }
  }
  const query = params.toString()
  return query ? `?${query}` : ''
}

function resetFilters() {
  filters.value = {}
  void reload()
}

async function exportRows() {
  errorMessage.value = ''
  successMessage.value = ''
  if (!total.value) {
    errorMessage.value = '当前过滤条件下没有可下载的追溯记录，请先调整筛选条件'
    return
  }
  exporting.value = true
  try {
    const response = await request(`${ENDPOINT}/export${buildQuery()}`)
    if (!response.ok) {
      throw new Error(await readErrorDetail(response, '清单生成失败，请稍后重试'))
    }
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = '追溯码清单.csv'
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    successMessage.value = `已按当前过滤条件导出 ${total.value} 条追溯记录`
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '清单下载失败'
  } finally {
    exporting.value = false
  }
}

function triggerImport() {
  errorMessage.value = ''
  successMessage.value = ''
  fileInput.value?.click()
}

async function onFilePicked(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''  // 允许重复选择同一个文件再次导入
  if (!file) {
    return
  }
  importing.value = true
  try {
    const content = await file.text()
    const response = await request(`${ENDPOINT}/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'text/csv; charset=utf-8' },
      body: content,
    })
    if (!response.ok) {
      throw new Error(await readErrorDetail(response, '清单导入失败，请检查文件后重试'))
    }
    const payload = (await response.json()) as { message?: string }
    successMessage.value = payload.message ?? '清单导入完成'
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '清单导入失败'
  } finally {
    importing.value = false
  }
}

async function readErrorDetail(response: Response, fallback: string) {
  try {
    const payload = (await response.json()) as { detail?: string }
    return payload.detail || fallback
  } catch {
    return fallback
  }
}

function openCreate() {
  errorMessage.value = '追溯记录登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  successMessage.value = ''
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
  successMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}${buildQuery()}`)
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
