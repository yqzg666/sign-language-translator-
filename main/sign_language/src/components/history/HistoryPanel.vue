<script setup>
import { ref, onMounted } from 'vue'
import { recordsApi } from '@/api'
import { showToast } from '@/composables/useToast'

/* 历史纪录（Tab1 手语实时综合）—— 对接后端 /api/records，持久化不丢失
 * 仅展示「文本→手语」类型的生成记录
 */
const list = ref([])
const loading = ref(false)
const removing = ref(false)

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(+d)) return iso
  const p = (n) => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

async function load() {
  loading.value = true
  try {
    const res = await recordsApi.list(1, 50)
    // 只取「文本→手语」类型的记录（Tab1 生成手语视频）
    list.value = (res.results || []).filter((r) => r.type === '文本→手语')
  } catch (e) {
    showToast('历史记录加载失败')
  } finally {
    loading.value = false
  }
}

async function remove(item) {
  removing.value = true
  try {
    await recordsApi.remove(item.id)
    showToast('已删除')
    await load()
  } catch (e) {
    showToast('删除失败：' + (e.message || '请重试'))
  } finally {
    removing.value = false
  }
}

onMounted(load)

defineExpose({ load })
</script>

<template>
  <div class="history-panel glass">
    <div class="history-head">
      <span class="history-title">📜 历史记录</span>
    </div>

    <div v-if="loading" class="history-empty">加载中…</div>
    <div v-else-if="!list.length" class="history-empty">暂无历史记录</div>

    <ul v-else class="history-list">
      <li v-for="item in list" :key="item.id" class="history-item">
        <div class="history-main">
          <p class="history-input">{{ item.input || '（无输入文本）' }}</p>
          <p v-if="item.detail" class="history-detail">{{ item.detail }}</p>
          <span class="history-time">{{ fmtTime(item.created_at) }}</span>
        </div>
        <video
          v-if="item.video_url"
          :src="item.video_url"
          class="history-video"
          controls
          muted
          playsinline
          preload="metadata"
        ></video>
        <button
          class="history-del btn-press"
          :disabled="removing"
          title="删除"
          @click="remove(item)"
        >✕</button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.history-panel {
  padding: 16px;
}
.history-head {
  margin-bottom: 10px;
}
.history-title {
  font-weight: 500;
  font-size: 13px;
  color: var(--text-secondary);
}
.history-empty {
  padding: 18px 0;
  text-align: center;
  font-size: 13px;
  color: var(--text-secondary);
}
.history-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.history-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 10px;
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid var(--glass-border);
}
.history-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.history-input {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.5;
}
.history-detail {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}
.history-time {
  font-size: 11px;
  color: var(--text-secondary);
}
.history-video {
  width: 110px;
  max-height: 80px;
  border-radius: var(--radius-sm);
  background: #000;
  object-fit: contain;
  flex-shrink: 0;
}
.history-del {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  flex-shrink: 0;
  background: rgba(248, 113, 113, 0.15);
  color: #dc2626;
  font-size: 13px;
}
.history-del:disabled {
  opacity: 0.5;
}
</style>
