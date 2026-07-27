<script setup>
import { ref, computed, onMounted } from 'vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { useAppStore } from '@/store/app'
import { voiceApi } from '@/api'
import { showToast } from '@/composables/useToast'

const store = useAppStore()

// 系统内置音色
const systemVoices = ['声音 1', '声音 2', '声音 3']

// 自定义克隆音色
const customVoices = ref([])      // 来自后端的克隆音色列表
const loadingVoices = ref(false)

// 录音状态
const recording = ref(false)
const audioContext = ref(null)
const scriptNode = ref(null)
const mediaStream = ref(null)
const audioChunks = ref([])       // 录音数据块
const recordedBlob = ref(null)    // 录音完成后生成的 WAV Blob
const recordedDuration = ref(0)   // 录音时长（秒）
const recordTimer = ref(null)     // 计时器

// 参考文本（用户输入自己说的话）
const refText = ref('')

// 音色名称
const customName = ref('')

// 管理模式：批量勾选与删除
const manageMode = ref(false)
const selectedNames = ref([])
const confirmVisible = ref(false)

const isAllSelected = computed(
  () => customVoices.value.length > 0 &&
    selectedNames.value.length === customVoices.value.length
)

// 是否有录音待上传
const hasRecording = computed(() => recordedBlob.value !== null)

// 加载后端克隆音色列表
async function loadCustomVoices() {
  loadingVoices.value = true
  try {
    const res = await voiceApi.listCustomVoices()
    customVoices.value = (res.voices || []).map(v => ({
      ...v,
      // 确保自定义音色也出现在 store 中
      _inStore: true
    }))
    // 同步到 store
    store.state.customVoices = customVoices.value.map(v => v.name)
  } catch (e) {
    console.error('加载音色列表失败:', e)
  } finally {
    loadingVoices.value = false
  }
}

onMounted(() => {
  loadCustomVoices()
})

/**
 * 选用音色
 */
function selectVoice(name) {
  store.state.selectedVoice = name
}

/**
 * 录音：使用 Web Audio API 采集 16kHz WAV
 */
async function toggleRecord() {
  if (recording.value) {
    stopRecording()
    return
  }
  try {
    // 请求麦克风权限
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    mediaStream.value = stream

    const ctx = new AudioContext({ sampleRate: 16000 })
    audioContext.value = ctx

    const source = ctx.createMediaStreamSource(stream)
    const node = ctx.createScriptProcessor(4096, 1, 1)
    scriptNode.value = node

    audioChunks.value = []
    recordedBlob.value = null
    refText.value = ''
    const startTime = Date.now()

    node.onaudioprocess = (e) => {
      if (!recording.value) return
      const input = e.inputBuffer.getChannelData(0)
      // 复制一份 Float32Array
      audioChunks.value.push(new Float32Array(input))
      recordedDuration.value = (Date.now() - startTime) / 1000
    }

    source.connect(node)
    node.connect(ctx.destination)

    recording.value = true

    // 启动计时器更新
    recordTimer.value = setInterval(() => {
      recordedDuration.value = (Date.now() - startTime) / 1000
    }, 200)
  } catch (err) {
    showToast('无法访问麦克风，请检查权限')
    console.error('麦克风错误:', err)
  }
}

/**
 * 停止录音，生成 WAV Blob
 */
function stopRecording() {
  recording.value = false

  if (recordTimer.value) {
    clearInterval(recordTimer.value)
    recordTimer.value = null
  }

  // 编码为 WAV
  if (audioChunks.value.length > 0) {
    const totalLen = audioChunks.value.reduce((sum, chunk) => sum + chunk.length, 0)
    const combined = new Float32Array(totalLen)
    let offset = 0
    for (const chunk of audioChunks.value) {
      combined.set(chunk, offset)
      offset += chunk.length
    }
    recordedBlob.value = encodeWav(combined, 16000)
  }

  // 清理录音资源
  try { scriptNode.value?.disconnect() } catch (e) {}
  try { audioContext.value?.close() } catch (e) {}
  for (const track of mediaStream.value?.getTracks() || []) {
    track.stop()
  }
  scriptNode.value = null
  audioContext.value = null
  mediaStream.value = null
  audioChunks.value = []
}

/**
 * Float32Array PCM → WAV Blob
 */
function encodeWav(samples, sampleRate) {
  const numChannels = 1
  const bitsPerSample = 16
  const byteRate = sampleRate * numChannels * bitsPerSample / 8
  const blockAlign = numChannels * bitsPerSample / 8
  const dataSize = samples.length * blockAlign
  const bufferSize = 44 + dataSize
  const buffer = new ArrayBuffer(bufferSize)
  const view = new DataView(buffer)

  // WAV 头
  function writeStr(offset, str) {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i))
  }
  writeStr(0, 'RIFF')
  view.setUint32(4, bufferSize - 8, true)
  writeStr(8, 'WAVE')
  writeStr(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)  // PCM
  view.setUint16(22, numChannels, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, byteRate, true)
  view.setUint16(32, blockAlign, true)
  view.setUint16(34, bitsPerSample, true)
  writeStr(36, 'data')
  view.setUint32(40, dataSize, true)

  // PCM 数据（16-bit 有符号）
  let idx = 44
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(idx, s < 0 ? s * 0x8000 : s * 0x7FFF, true)
    idx += 2
  }

  return new Blob([buffer], { type: 'audio/wav' })
}

/**
 * 删除录音（重新录制）
 */
function discardRecording() {
  recordedBlob.value = null
  recordedDuration.value = 0
  refText.value = ''
}

/**
 * 保存并上传参考音频用于音色克隆
 */
async function saveCustomVoice() {
  if (!recordedBlob.value) {
    showToast('请先录制音频')
    return
  }
  if (!refText.value.trim()) {
    showToast('请输入录音对应的文本内容')
    return
  }

  const name = customName.value.trim() || `克隆音色 ${Date.now().toString().slice(-4)}`

  try {
    const res = await voiceApi.saveCustomVoice(name, recordedBlob.value, refText.value.trim())
    // 添加到本地列表
    customVoices.value.unshift({
      name: res.name,
      ref_text: refText.value.trim(),
    })
    store.state.customVoices.push(res.name)
    store.state.selectedVoice = res.name

    // 重置录音状态
    discardRecording()
    customName.value = ''
    showToast(`音色「${res.name}」已上传，可使用克隆配音`)
  } catch (e) {
    showToast(`上传失败: ${e.message}`)
  }
}

// 管理操作
function enterManage() {
  selectedNames.value = []
  manageMode.value = true
}
function exitManage() {
  manageMode.value = false
  selectedNames.value = []
}
function toggleSelect(name) {
  const idx = selectedNames.value.indexOf(name)
  if (idx >= 0) selectedNames.value.splice(idx, 1)
  else selectedNames.value.push(name)
}
function toggleSelectAll() {
  if (isAllSelected.value) {
    selectedNames.value = []
  } else {
    selectedNames.value = customVoices.value.map(v => v.name)
  }
}
function openConfirm() {
  if (!selectedNames.value.length) return
  confirmVisible.value = true
}
async function doDelete() {
  try {
    await voiceApi.deleteCustomVoices(selectedNames.value)
    // 从本地列表移除
    const pending = new Set(selectedNames.value)
    customVoices.value = customVoices.value.filter(v => !pending.has(v.name))
    store.removeCustomVoices(selectedNames.value)
    showToast('已删除')
  } catch (e) {
    showToast('删除失败')
  }
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

    <!-- 自定义克隆音色分组 -->
    <section class="group glass">
      <div class="group-head">
        <h3 class="group-title">克隆音色</h3>
        <button
          v-if="customVoices.length && !manageMode"
          class="manage-btn btn-press"
          @click="enterManage"
        >
          管理
        </button>
      </div>

      <!-- 管理模式 -->
      <div v-if="manageMode" class="manage-bar">
        <button class="manage-link btn-press" @click="toggleSelectAll">
          {{ isAllSelected ? '取消全选' : '全选' }}
        </button>
        <span class="manage-count">已选 {{ selectedNames.length }} 项</span>
        <button class="manage-link btn-press" @click="exitManage">完成</button>
      </div>

      <div v-if="customVoices.length" class="voice-grid">
        <button
          v-for="v in customVoices"
          :key="v.name"
          class="voice-item btn-press"
          :class="{
            active: !manageMode && store.state.selectedVoice === v.name,
            checked: manageMode && selectedNames.includes(v.name)
          }"
          @click="manageMode ? toggleSelect(v.name) : selectVoice(v.name)"
        >
          <span v-if="manageMode" class="check" :class="{ filled: selectedNames.includes(v.name) }">
            <span v-if="selectedNames.includes(v.name)" class="check-mark">✓</span>
          </span>
          🎙 {{ v.name }}
        </button>
      </div>
      <p v-else-if="!loadingVoices" class="empty-tip">暂无克隆音色，请录制并上传</p>
      <p v-else class="empty-tip">加载中...</p>

      <!-- 录音与上传（非管理模式） -->
      <template v-if="!manageMode">
        <!-- 录音按钮 -->
        <div class="record-area">
          <BaseButton
            variant="yellow"
            size="sm"
            :disabled="loadingVoices"
            @click="toggleRecord"
          >
            {{ recording ? '⏹ 停止录制' : '● 录制' }}
          </BaseButton>
          <span v-if="recording" class="recording-indicator">
            录音中 {{ recordedDuration.toFixed(1) }}s
          </span>
          <span v-else-if="hasRecording" class="recording-done">
            已录制 {{ recordedDuration.toFixed(1) }}s
          </span>
        </div>

        <!-- 录音完成后显示：参考文本输入 + 音色名称 + 保存/重录 -->
        <template v-if="hasRecording">
          <input
            v-model="refText"
            class="voice-input"
            placeholder="输入刚才说的话（如：大家好，欢迎使用手语翻译系统）"
          />
          <span class="input-hint">克隆效果需要参考音频与文本一致，请准确输入</span>
          <input
            v-model="customName"
            class="voice-input"
            placeholder="音色名称（可选，自动生成）"
          />
          <div class="custom-actions">
            <BaseButton variant="ghost" size="sm" @click="discardRecording">重录</BaseButton>
            <BaseButton variant="blue" size="sm" :disabled="!refText.trim()" @click="saveCustomVoice">
              上传并克隆
            </BaseButton>
          </div>
        </template>
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
            确定删除选中的 {{ selectedNames.length }} 个克隆音色？删除后不可恢复。
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
.voice-item.checked {
  border-color: var(--gradient-blue);
  background: rgba(104, 174, 247, 0.18);
}
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

/* 录音区域 */
.record-area {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
}
.recording-indicator {
  font-size: 13px;
  color: #e74c3c;
  animation: pulse 1s ease-in-out infinite;
}
.recording-done {
  font-size: 13px;
  color: #27ae60;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
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
  box-sizing: border-box;
}
.input-hint {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 4px;
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
