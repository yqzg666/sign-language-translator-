<script setup>
import { ref, onBeforeUnmount } from 'vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import SaveSheet from '@/components/ui/SaveSheet.vue'
import FolderPicker from '@/components/materials/FolderPicker.vue'
import { useMaterialsStore } from '@/store/materials'
import { chatApi } from '@/api'
import { showToast } from '@/composables/useToast'
import HistoryPanel from '@/components/history/HistoryPanel.vue'
import MaterialsPage from '@/components/materials/MaterialsPage.vue'

const materialsStore = useMaterialsStore()

// 保存相关状态
const saveSheetOpen = ref(false) // 保存选择面板
const pickerOpen = ref(false) // 保存到素材的文件夹选择弹窗

// ====== 语音转手语视频 ======
const voiceText = ref('') // 语音转文字后可编辑文本
const recording = ref(false) // 麦克风录音状态
const videoGenerated = ref(false) // 是否已展开视频预览
const videoUrl = ref('') // 后端返回的手语视频 URL
const videoEl2 = ref(null) // 视频预览 <video> 引用
const genProgress = ref(0) // 生成进度 0-100
const genStatus = ref('') // 当前状态文字
const videoInfo = ref(null) // 视频详情 { chinese_text, gloss_text, similarity, method }
let audioCtx = null
let micStream = null
let jsNode = null
let pcmBuffer = []

/**
 * 将 Float32Array 编码为 WAV Blob
 */
function encodeWAV(samples, sampleRate) {
  const len = samples.length
  const buf = new ArrayBuffer(44 + len * 2)
  const dv = new DataView(buf)
  const writeStr = (off, s) => { for (let i = 0; i < s.length; i++) dv.setUint8(off + i, s.charCodeAt(i)) }
  writeStr(0, 'RIFF')
  dv.setUint32(4, 36 + len * 2, true)
  writeStr(8, 'WAVE')
  writeStr(12, 'fmt ')
  dv.setUint32(16, 16, true)
  dv.setUint16(20, 1, true)
  dv.setUint16(22, 1, true)
  dv.setUint32(24, sampleRate, true)
  dv.setUint32(28, sampleRate * 2, true)
  dv.setUint16(32, 2, true)
  dv.setUint16(34, 16, true)
  writeStr(36, 'data')
  dv.setUint32(40, len * 2, true)
  for (let i = 0; i < len; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    dv.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true)
  }
  return new Blob([buf], { type: 'audio/wav' })
}

/**
 * 切换麦克风录音：点击开始录音，再次点击停止，发送到后端识别
 */
async function toggleMic() {
  if (recording.value) {
    // 停止录音
    recording.value = false
    if (jsNode) jsNode.disconnect()
    if (audioCtx) await audioCtx.close()
    if (micStream) micStream.getTracks().forEach(t => t.stop())
    jsNode = null
    audioCtx = null
    micStream = null

    // 编码 WAV 并发送识别
    if (pcmBuffer.length === 0) return
    const sampleRate = 16000
    // 合并所有 Float32Array
    let totalLen = 0
    for (const c of pcmBuffer) totalLen += c.length
    const all = new Float32Array(totalLen)
    let offset = 0
    for (const c of pcmBuffer) { all.set(c, offset); offset += c.length }
    pcmBuffer = []
    const wavBlob = encodeWAV(all, sampleRate)

    showToast('正在识别...')
    try {
      const { text } = await chatApi.speechToText(wavBlob)
      voiceText.value = text
      if (text) showToast('识别成功')
    } catch (e) {
      showToast('识别失败: ' + (e.message || '请重试'))
    }
    return
  }

  // 开始录音
  pcmBuffer = []
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    micStream = stream
    audioCtx = new AudioContext({ sampleRate: 16000 })
    const source = audioCtx.createMediaStreamSource(stream)
    jsNode = audioCtx.createScriptProcessor(4096, 1, 1)
    jsNode.onaudioprocess = (e) => {
      const ch = e.inputBuffer.getChannelData(0)
      pcmBuffer.push(new Float32Array(ch))
    }
    source.connect(jsNode)
    jsNode.connect(audioCtx.destination)
    recording.value = true
    showToast('录音中...点击停止')
  } catch {
    showToast('无法访问麦克风，请检查权限')
  }
}

// 生成手语视频中状态
const generating = ref(false)


/**
 * 生成手语视频：调用后端接口，成功后展开视频预览模块
 */
async function generateVideo() {
  if (!voiceText.value || generating.value) return

  videoGenerated.value = false
  generating.value = true
  genProgress.value = 0
  genStatus.value = '正在连接...'
  videoUrl.value = ''
  videoInfo.value = null

  const token = localStorage.getItem('sl_token') || ''
  try {
    const res = await fetch('/api/sign/generate-stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ text: voiceText.value }),
    })

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop() || ''
      for (const line of lines) {
        if (!line.trim()) continue
        try {
          const data = JSON.parse(line)
          genProgress.value = data.progress ?? genProgress.value
          if (data.status) genStatus.value = data.status
          if (data.type === 'result') {
            videoUrl.value = data.videoUrl || ''
            videoInfo.value = {
              chinese_text: data.chinese_text || voiceText.value,
              gloss_text: data.gloss_text || '',
              similarity: data.similarity || 0,
              method: data.method || '',
            }
            // 生成成功后刷新历史记录
            historyPanelRef.value?.load()
          }
          if (data.type === 'error') {
            showToast(data.error || '生成失败')
          }
        } catch { /* 忽略不完整的行 */ }
      }
    }
  } catch {
    showToast('生成失败，请重试')
  } finally {
    generating.value = false
    videoGenerated.value = true
  }
}

/**
 * 保存到素材
 */
function saveVoice2Sign() {
  if (!voiceText.value) return
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  // 名称使用当前时间
  const name = `语音转手语 ${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
  pickerOpen.value = true
  pendingSaveName.value = name
  pendingSaveContent.value = voiceText.value
}

// 保存到素材的临时状态
const pendingSaveName = ref('')
const pendingSaveContent = ref('')

function onPickFolder(folderId) {
  materialsStore.addTextMaterial(folderId, pendingSaveName.value, pendingSaveContent.value)
  pickerOpen.value = false
  showToast('已保存到素材')
}

// 生命周期
onBeforeUnmount(() => {
  if (audioCtx) {
    audioCtx.close()
    audioCtx = null
  }
  if (micStream) {
    micStream.getTracks().forEach(t => t.stop())
    micStream = null
  }
})
</script>

<template>
  <div class="sign-tab">

    <!-- 语音转手语 -->
    <div class="tab-content">
      <!-- 麦克风输入区域 -->
      <div class="mic-zone">
        <button
          class="mic-btn btn-press"
          :class="{ recording }"
          style="background-image: url(/bg/mic.png)"
          @click="toggleMic"
          aria-label="语音输入"
        ></button>
        <p class="mic-tip">{{ recording ? '正在录音...点击停止' : '点击麦克风开始说话' }}</p>
      </div>

      <!-- 文字编辑区 -->
      <div class="text-edit-zone">
        <textarea
          v-model="voiceText"
          class="voice-textarea"
          placeholder="语音转文字后可在此修改内容"
          rows="3"
        ></textarea>
        <div class="text-actions">
          <BaseButton variant="yellow" size="sm" @click="generateVideo">
            ✨ 生成手语视频
          </BaseButton>
          <button class="save-btn btn-press" @click="saveVoice2Sign">
            💾 保存到素材
          </button>
        </div>
      </div>

      <!-- 生成进度条 -->
      <div v-if="generating" class="gen-progress">
        <div class="gen-bar-track">
          <div class="gen-bar-fill" :style="{ width: genProgress + '%' }"></div>
        </div>
        <div class="gen-info">
          <span>{{ genStatus }}</span>
          <span>{{ Math.round(genProgress) }}%</span>
        </div>
      </div>

      <!-- 视频预览展开区 -->
      <div v-if="videoGenerated && videoUrl" class="video-preview glass">
        <video ref="videoEl2" class="preview-video" controls autoplay>
          <source :src="videoUrl" type="video/mp4" />
        </video>
        <div class="video-detail" v-if="videoInfo">
          <div class="detail-row">
            <span class="detail-label">原文</span>
            <span class="detail-value">{{ videoInfo.chinese_text }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">手语单词</span>
            <span class="detail-value">{{ videoInfo.gloss_text || '—' }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">匹配度</span>
            <span class="detail-value">{{ (videoInfo.method === 'stitch' ? 100 : videoInfo.similarity * 100).toFixed(1) }}%</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">检索方式</span>
            <span
              class="detail-value method-tag"
              :class="videoInfo.method"
            >{{ { retrieval: '句向量检索', deepseek: 'DeepSeek 改写', gloss: 'Gloss 匹配', stitch: '视频拼接' }[videoInfo.method] || videoInfo.method }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 历史记录（沿用玻璃卡片风格，对接后端持久化） -->
    <HistoryPanel ref="historyPanelRef" />

    <!-- 我的素材（复用素材库，直接内嵌，让界面更充实） -->
    <MaterialsPage />

    <!-- 保存选择面板 -->
    <SaveSheet
      v-if="saveSheetOpen"
      :open="saveSheetOpen"
      @pick-folder="onPickFolder"
      @close="saveSheetOpen = false"
    />
    <!-- 文件夹选择弹窗 -->
    <FolderPicker
      :open="pickerOpen"
      @close="pickerOpen = false"
      @select="onPickFolder"
    />
  </div>
</template>

<style scoped>
.sign-tab {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--gap-md);
  overflow-y: auto;
  padding: 0 12px 12px;
}

/* 语音转手语内容 */
.tab-content {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--gap-md);
  padding: 16px 4px 12px;
}

/* 麦克风输入区 */
.mic-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 6px 0 0;
}
.mic-btn {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background-color: var(--gradient-yellow);
  background-repeat: no-repeat;
  background-position: center;
  background-size: cover;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all var(--transition-fast);
  box-shadow: var(--shadow-yellow);
  overflow: hidden;
}
.mic-btn.recording {
  animation: mic-pulse 1.2s infinite;
}
@keyframes mic-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(255, 221, 136, 0.5); }
  50% { box-shadow: 0 0 0 18px rgba(255, 221, 136, 0); }
}
.mic-icon-inner {
  display: block;
  line-height: 1;
}
.mic-tip {
  color: var(--text-secondary);
  font-size: 13px;
  margin: 0;
}

/* 文字编辑区 */
.text-edit-zone {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.voice-textarea {
  width: 100%;
  padding: 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--glass-border);
  background: var(--glass-bg-strong);
  backdrop-filter: blur(var(--glass-blur));
  font-size: 14px;
  color: var(--text-primary);
  resize: none;
  outline: none;
  min-height: 80px;
  box-sizing: border-box;
}
.text-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.save-btn {
  padding: 8px 18px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid var(--glass-border);
  font-size: 14px;
  color: var(--text-primary);
  min-height: 40px;
  cursor: pointer;
}

/* 生成进度条 */
.gen-progress {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 0 4px;
}
.gen-bar-track {
  width: 100%;
  height: 6px;
  background: rgba(255, 255, 255, 0.3);
  border-radius: 3px;
  overflow: hidden;
}
.gen-bar-fill {
  height: 100%;
  background: var(--gradient-yellow);
  border-radius: 3px;
  transition: width 0.3s;
}
.gen-info {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-secondary);
}

/* 视频预览 */
.video-preview {
  padding: 12px;
  border-radius: var(--radius-lg);
}
.preview-video {
  width: 100%;
  border-radius: var(--radius-md);
  display: block;
}
.video-detail {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.detail-row {
  display: flex;
  gap: 8px;
  font-size: 13px;
}
.detail-label {
  color: var(--text-secondary);
  min-width: 56px;
  flex-shrink: 0;
}
.detail-value {
  color: var(--text-primary);
}
.method-tag {
  display: inline-block;
  padding: 0 8px;
  border-radius: 4px;
  font-size: 12px;
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}
.method-tag.stitch {
  background: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
}
</style>
