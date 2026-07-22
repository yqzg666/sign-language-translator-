<script setup>
import { ref, computed } from 'vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { useAppStore } from '@/store/app'

const store = useAppStore()

// 系统内置音色
const systemVoices = ['声音 1', '声音 2', '声音 3']

// 自定义音色名称与录音状态
const customName = ref('')
const recording = ref(false)

// 管理模式：批量勾选与删除
const manageMode = ref(false) // 是否处于管理模式
const selectedNames = ref([]) // 勾选的待删除音色名称
const confirmVisible = ref(false) // 删除确认弹窗

// 是否已全选自定义音色
const isAllSelected = computed(
  () =>
    store.state.customVoices.length > 0 &&
    selectedNames.value.length === store.state.customVoices.length
)

/**
 * 选用音色：系统或自定义（管理模式下仅作用于系统音色）
 * @param {string} name 音色名称
 */
function selectVoice(name) {
  store.state.selectedVoice = name
}

/**
 * 录制自定义音色：切换录音状态（模拟）
 */
function toggleRecord() {
  recording.value = !recording.value
  if (recording.value) {
    setTimeout(() => (recording.value = false), 2000)
  }
}

/**
 * 保存自定义音色：名称写入列表并自动选用
 * 后端对接：voiceApi.saveCustomVoice(name, audioBlob)
 */
function saveCustomVoice() {
  const name = customName.value.trim() || `自定义音色 ${store.state.customVoices.length + 1}`
  store.addCustomVoice(name)
  store.state.selectedVoice = name
  customName.value = ''
}

// 进入管理模式：清空勾选
function enterManage() {
  selectedNames.value = []
  manageMode.value = true
}

// 退出管理模式：清空勾选
function exitManage() {
  manageMode.value = false
  selectedNames.value = []
}

/**
 * 切换单个自定义音色的勾选状态
 * @param {string} name 音色名称
 */
function toggleSelect(name) {
  const idx = selectedNames.value.indexOf(name)
  if (idx >= 0) {
    selectedNames.value.splice(idx, 1)
  } else {
    selectedNames.value.push(name)
  }
}

// 全选 / 取消全选
function toggleSelectAll() {
  if (isAllSelected.value) {
    selectedNames.value = []
  } else {
    selectedNames.value = [...store.state.customVoices]
  }
}

// 打开删除确认弹窗（至少勾选一项）
function openConfirm() {
  if (!selectedNames.value.length) return
  confirmVisible.value = true
}

/**
 * 执行批量删除：调用 store 后退出管理模式
 * 后端对接：voiceApi.deleteCustomVoices(ids)
 */
function doDelete() {
  store.removeCustomVoices(selectedNames.value)
  confirmVisible.value = false
  exitManage()
}
</script>

<template>
  <div class="voice-page scroll-area">
    <!-- 系统内置音色分组 -->
    <section class="group glass">
      <h3 class="group-title">系统内置音色</h3>
      <div class="voice-grid">
        <button
          v-for="v in systemVoices"
          :key="v"
          class="voice-item btn-press"
          :class="{ active: store.state.selectedVoice === v }"
          @click="selectVoice(v)"
        >
          🎵 {{ v }}
        </button>
      </div>
    </section>

    <!-- 自定义录音音色分组 -->
    <section class="group glass">
      <div class="group-head">
        <h3 class="group-title">自定义录音音色</h3>
        <button
          v-if="store.state.customVoices.length && !manageMode"
          class="manage-btn btn-press"
          @click="enterManage"
        >
          管理
        </button>
      </div>

      <!-- 管理模式下的批量操作栏 -->
      <div v-if="manageMode" class="manage-bar">
        <button class="manage-link btn-press" @click="toggleSelectAll">
          {{ isAllSelected ? '取消全选' : '全选' }}
        </button>
        <span class="manage-count">已选 {{ selectedNames.length }} 项</span>
        <button class="manage-link btn-press" @click="exitManage">完成</button>
      </div>

      <div v-if="store.state.customVoices.length" class="voice-grid">
        <button
          v-for="v in store.state.customVoices"
          :key="v"
          class="voice-item btn-press"
          :class="{
            active: !manageMode && store.state.selectedVoice === v,
            checked: manageMode && selectedNames.includes(v)
          }"
          @click="manageMode ? toggleSelect(v) : selectVoice(v)"
        >
          <!-- 管理模式下的勾选圆圈 -->
          <span v-if="manageMode" class="check" :class="{ filled: selectedNames.includes(v) }">
            <span v-if="selectedNames.includes(v)" class="check-mark">✓</span>
          </span>
          🎙 {{ v }}
        </button>
      </div>
      <p v-else class="empty-tip">暂无自定义音色，请在下方录制</p>

      <!-- 非管理模式：录制与保存 -->
      <template v-if="!manageMode">
        <input v-model="customName" class="voice-input" placeholder="自定义音色名称" />
        <div class="custom-actions">
          <BaseButton variant="yellow" size="sm" @click="toggleRecord">
            {{ recording ? '⏹ 停止录制' : '● 录制' }}
          </BaseButton>
          <BaseButton variant="blue" size="sm" @click="saveCustomVoice">保存</BaseButton>
        </div>
      </template>

      <!-- 管理模式下的底部删除按钮 -->
      <BaseButton
        v-else
        variant="yellow"
        block
        :disabled="!selectedNames.length"
        @click="openConfirm"
      >
        删除 ({{ selectedNames.length }})
      </BaseButton>
    </section>

    <!-- 删除确认弹窗 -->
    <transition name="modal">
      <div v-if="confirmVisible" class="modal-mask" @click.self="confirmVisible = false">
        <div class="confirm-modal glass">
          <p class="confirm-title">确认删除</p>
          <p class="confirm-desc">
            确定删除选中的 {{ selectedNames.length }} 个自定义音色？删除后不可恢复。
          </p>
          <div class="confirm-actions">
            <BaseButton variant="ghost" size="sm" @click="confirmVisible = false">取消</BaseButton>
            <BaseButton variant="yellow" size="sm" @click="doDelete">确认删除</BaseButton>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.voice-page {
  flex: 1;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  position: relative;
}
.group {
  padding: 16px;
}
.group-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.group-title {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 12px;
}
.manage-btn {
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  background: rgba(104, 174, 247, 0.14);
  color: var(--text-primary);
  font-size: 13px;
  min-height: 32px;
}

/* 批量操作栏 */
.manage-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 4px;
  margin-bottom: 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.6);
}
.manage-link {
  padding: 4px 8px;
  font-size: 14px;
  color: #4a8fe0;
  min-height: 36px;
}
.manage-count {
  font-size: 13px;
  color: var(--text-secondary);
}

.voice-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.voice-item {
  position: relative;
  padding: 14px 10px;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.6);
  border: 2px solid transparent;
  font-size: 14px;
  color: var(--text-primary);
  min-height: var(--touch-target);
}
.voice-item.active {
  border-color: var(--gradient-blue);
  background: rgba(104, 174, 247, 0.14);
}
/* 管理模式下的勾选态 */
.voice-item.checked {
  border-color: var(--gradient-blue);
  background: rgba(104, 174, 247, 0.18);
}

/* 勾选圆圈 */
.check {
  position: absolute;
  top: 8px;
  left: 8px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 1.5px solid rgba(120, 150, 200, 0.6);
  background: rgba(255, 255, 255, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
}
.check.filled {
  background: var(--gradient-blue);
  border-color: transparent;
}
.check-mark {
  font-size: 12px;
  color: #fff;
  line-height: 1;
}

.empty-tip {
  color: var(--text-secondary);
  font-size: 13px;
  margin-bottom: 12px;
}
.voice-input {
  width: 100%;
  padding: 12px 14px;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid var(--glass-border);
  font-size: 14px;
  margin-top: 12px;
  color: var(--text-primary);
}
.custom-actions {
  display: flex;
  gap: 10px;
  margin-top: 12px;
}
.custom-actions > * {
  flex: 1;
}

/* 删除确认弹窗 */
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(3px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 60;
}
.confirm-modal {
  width: 100%;
  max-width: 320px;
  padding: 24px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
}
.confirm-title {
  font-size: 18px;
  font-weight: 500;
  color: var(--text-primary);
}
.confirm-desc {
  font-size: 14px;
  color: var(--text-secondary);
  text-align: center;
  line-height: 1.5;
}
.confirm-actions {
  display: flex;
  gap: 12px;
  width: 100%;
}
.confirm-actions > * {
  flex: 1;
}

/* 弹窗过渡 */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.24s ease;
}
.modal-enter-active .confirm-modal,
.modal-leave-active .confirm-modal {
  transition: transform 0.28s cubic-bezier(0.2, 0, 0.2, 1), opacity 0.28s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-from .confirm-modal,
.modal-leave-to .confirm-modal {
  transform: scale(0.92);
  opacity: 0;
}
</style>
