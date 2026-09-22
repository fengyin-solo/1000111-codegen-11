<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常。</p>
      </div>
    </header>
    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>
    <table class="data-table">
      <thead>
        <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in moduleRows" :key="row.name">
          <td>{{ row.name }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson } from '@/api/client'

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}

const cards = ref<Overview['cards']>([])
const moduleRows = ref<Overview['modules']>([])

onMounted(async () => {
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = payload.cards
    moduleRows.value = payload.modules
  } catch {
    cards.value = [{"label": "业务模块", "value": 0}, {"label": "今日新增", "value": 0}]
    moduleRows.value = [{"name": "冷链订单", "created": 0, "pending": 0, "abnormal": 0}, {"name": "运单管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "冷藏车管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "司机管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "温控监控", "created": 0, "pending": 0, "abnormal": 0}, {"name": "温度异常", "created": 0, "pending": 0, "abnormal": 0}, {"name": "冷库管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "入库管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "出库管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "库存管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "批次追溯", "created": 0, "pending": 0, "abnormal": 0}, {"name": "质检管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "线路管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "调度派单", "created": 0, "pending": 0, "abnormal": 0}, {"name": "温控设备", "created": 0, "pending": 0, "abnormal": 0}, {"name": "维保工单", "created": 0, "pending": 0, "abnormal": 0}, {"name": "告警中心", "created": 0, "pending": 0, "abnormal": 0}, {"name": "客户管理", "created": 0, "pending": 0, "abnormal": 0}, {"name": "计费结算", "created": 0, "pending": 0, "abnormal": 0}, {"name": "报表导出", "created": 0, "pending": 0, "abnormal": 0}, {"name": "系统设置", "created": 0, "pending": 0, "abnormal": 0}]
  }
})
</script>
