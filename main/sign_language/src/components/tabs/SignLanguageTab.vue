<script setup>
import { ref, onBeforeUnmount, nextTick } from 'vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import SaveSheet from '@/components/ui/SaveSheet.vue'
import FolderPicker from '@/components/materials/FolderPicker.vue'
import { useMaterialsStore } from '@/store/materials'
import { signApi, chatApi } from '@/api'
import { showToast } from '@/composables/useToast'

const materialsStore = useMaterialsStore()

// 保存相关状态
const saveSheetOpen = ref(false) // 保存选择面板
const pickerOpen = ref(false) // 保存到素材的文件夹选择弹窗

// ====== 双子标签切换 ======
const subTab = ref('sign2voice') // sign2voice 手语转语音 / voice2sign 语音转手语

// ====== 手语转语音：摄像头预览与录像识别 ======
const videoEl = ref(null)
let mediaStream = null
const cameraReady = ref(false)

// 录像相关
const cameraRecording = ref(false)
let cameraMediaRec = null
let cameraRecChunks = []
const recognizing = ref(false)

/**
 * 启动摄像头预览，失败时显示占位
 * 注：网页环境调用 getUserMedia，原生 APP 中应替换为相机插件
 */
async function startCamera() {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user' },
      audio: false
    })
    // 先设为 true 让 Vue 渲染出 <video> 元素
    cameraReady.value = true
    // 等待 DOM 更新
    await nextTick()
    if (videoEl.value) {
      videoEl.value.srcObject = mediaStream
    }
  } catch (e) {
    cameraReady.value = false
    console.warn('[摄像头] 启动失败:', e.message)
    showToast('摄像头不可用（IDE 环境限制），请用外部浏览器打开')
  }
}

// 停止摄像头释放资源，并同步关闭状态与视频源
function stopCamera() {
  if (mediaStream) {
    mediaStream.getTracks().forEach((t) => t.stop())
    mediaStream = null
  }
  if (videoEl.value) {
    videoEl.value.srcObject = null
  }
  cameraReady.value = false
}

/**
 * 切换摄像头开关：开启时启动预览，关闭时释放摄像头
 */
async function toggleCamera() {
  if (cameraReady.value) {
    stopCamera()
  } else {
    await startCamera()
  }
}

/**
 * 开始/停止录像识别
 */
async function toggleRecord() {
  if (cameraRecording.value) {
    // 停止录像
    cameraRecording.value = false
    cameraMediaRec?.stop()
  } else {
    // 开始录像
    recognizing.value = false
    try {
      // 复用摄像头 stream，仅录像无需额外请求音频
      if (!mediaStream) {
        showToast('请先开启摄像头')
        return
      }
      // 使用 MediaRecorder 录制视频，无需音频
      cameraMediaRec = new MediaRecorder(mediaStream, { mimeType: 'video/webm' })
      cameraRecChunks = []
      cameraMediaRec.ondataavailable = (e) => cameraRecChunks.push(e.data)
      cameraMediaRec.onstop = () => {
        // 录像结束后立即进行识别
        startRecognition()
      }
      cameraMediaRec.start()
      cameraRecording.value = true
    } catch (e) {
      showToast('录像启动失败')
    }
  }
}

/**
 * 手语识别：将录像 Blob 发送到后端识别
 */
async function startRecognition() {
  if (cameraRecChunks.length === 0) return
  recognizing.value = true
  const blob = new Blob(cameraRecChunks, { type: 'video/webm' })
  try {
    const data = await signApi.recognizeSign(blob)
    const words = (data.words || []).map((w) => w.gloss || w).join(' ')
    showToast('识别结果: ' + words)
  } catch (e) {
    showToast('识别失败: ' + (e.message || '请重试'))
  } finally {
    recognizing.value = false
  }
}

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
  stopCamera()
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

    <!-- 子标签切换 -->
    <div class="sub-tabs">
      <button
        class="sub-tab btn-press"
        :class="{ active: subTab === 'sign2voice' }"
        @click="subTab = 'sign2voice'"
      >
        🤟 手语转语音
      </button>
      <button
        class="sub-tab btn-press"
        :class="{ active: subTab === 'voice2sign' }"
        @click="subTab = 'voice2sign'"
      >
        🎙 语音转手语
      </button>
    </div>

    <!-- 子标签：手语转语音 -->
    <div v-if="subTab === 'sign2voice'" class="tab-content">
      <!-- 摄像头预览区 -->
      <div class="camera-section glass">
        <div v-if="!cameraReady" class="camera-placeholder" @click="toggleCamera">
          <p class="camera-icon">📷</p>
          <p class="camera-text">点击开启摄像头</p>
        </div>
        <video v-else ref="videoEl" class="camera-video" autoplay playsinline muted></video>

        <!-- 进度提示 -->
        <div class="camera-hint" v-if="recognizing">
          <span class="hint-spinner">⏳</span>
          <span>正在识别手语...</span>
        </div>
      </div>

      <!-- 操作按钮组 -->
      <div class="camera-actions">
        <BaseButton variant="yellow" size="sm" @click="toggleCamera">
          {{ cameraReady ? '关闭摄像头' : '开启摄像头' }}
        </BaseButton>
        <BaseButton
          variant="yellow"
          size="sm"
          :disabled="!cameraReady || recognizing"
          @click="toggleRecord"
        >
          {{ cameraRecording ? '停止录像' : '开始录像' }}
        </BaseButton>
      </div>
    </div>

    <!-- 子标签：语音转手语 -->
    <div v-if="subTab === 'voice2sign'" class="tab-content">
      <!-- 麦克风输入区域 -->
      <div class="mic-zone">
        <button
          class="mic-btn btn-press"
          :class="{ recording }"
          @click="toggleMic"
          aria-label="语音输入"
        >
          <span class="mic-icon-inner">🎤</span>
        </button>
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
            <span class="detail-value">{{ (videoInfo.similarity * 100).toFixed(1) }}%</span>
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
}

/* 子标签切换 */
.sub-tabs {
  display: flex;
  gap: 8px;
  padding: 0 4px;
}
.sub-tab {
  flex: 1;
  padding: 14px 10px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.5);
  border: 1px solid transparent;
  font-size: 15px;
  font-weight: 500;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
  cursor: pointer;
  min-height: 52px;
}
.sub-tab.active {
  background: var(--gradient-yellow);
  color: var(--text-on-yellow);
  border-color: transparent;
}

/* 手语转语音 */
.tab-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--gap-md);
  overflow-y: auto;
}
.camera-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 240px;
  border-radius: var(--radius-lg);
  overflow: hidden;
  position: relative;
}
.camera-placeholder {
  cursor: pointer;
  text-align: center;
  padding: 40px 20px;
}
.camera-icon {
  font-size: 48px;
  margin: 0 0 8px;
}
.camera-text {
  color: var(--text-secondary);
  font-size: 14px;
  margin: 0;
}
.camera-video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: var(--radius-lg);
}
.camera-hint {
  position: absolute;
  bottom: 12px;
  left: 12px;
  right: 12px;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.hint-spinner {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.camera-actions {
  display: flex;
  gap: 8px;
  justify-content: center;
}

/* 语音转手语 */
.mic-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 24px 0 8px;
}
.mic-btn {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: var(--gradient-yellow);
  border: none;
  font-size: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all var(--transition-fast);
  box-shadow: var(--shadow-yellow);
}
.mic-btn.recording {
  background: var(--gradient-yellow);
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
