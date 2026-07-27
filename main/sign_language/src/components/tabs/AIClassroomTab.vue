<script setup>
import { ref, nextTick, onMounted } from 'vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import FolderPicker from '@/components/materials/FolderPicker.vue'
import { useMaterialsStore } from '@/store/materials'
import { chatApi } from '@/api'
import { showToast } from '@/composables/useToast'

const materialsStore = useMaterialsStore()

// 对话消息列表：role 为 ai / user
const messages = ref([])
const inputText = ref('')
const chatList = ref(null)

// 保存到素材相关状态
const pickerOpen = ref(false)
const pendingSaveName = ref('')
const pendingSaveContent = ref('')

// 快捷提问标签
const quickTags = ['你好', '谢谢', '几点了', '今天天气']

// 麦克风录音+后端ASR
const recording = ref(false)
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
      inputText.value = text
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

/**
 * 滚动对话区域到底部
 */
function scrollToBottom() {
  nextTick(() => {
    if (chatList.value) chatList.value.scrollTop = chatList.value.scrollHeight
  })
}

/**
 * 发送消息：追加用户气泡，调用后端获取 AI 自动回复
 * @param {string} text 发送内容
 */
async function sendMessage(text) {
  const content = (text ?? inputText.value).trim()
  if (!content) return
  messages.value.push({ role: 'user', text: content })
  inputText.value = ''
  scrollToBottom()
  try {
    const { reply } = await chatApi.sendMessage(content, messages.value)
    messages.value.push({ role: 'ai', text: reply, sign: null })
  } catch {
    messages.value.push({ role: 'ai', text: '回复失败，请稍后重试', sign: null })
  }
  scrollToBottom()
}

// 回车快捷发送
function onEnter() {
  sendMessage()
}

/**
 * 点击"查看手语视频"：先提取关键词，再调用流式接口生成视频
 * @param {Object} msg AI 消息对象
 */
async function loadSignVideo(msg) {
  if (msg.sign?.videoUrl || msg.sign?.generating) return
  msg.sign = { generating: true, progress: 5, status: '正在提取手语关键词...', videoUrl: '', videoInfo: null }
  try {
    // 第一步：从 AI 回复中提取手语关键词
    const { keyword } = await chatApi.extractSign(msg.text)
    if (!keyword) {
      showToast('未检测到手语词汇')
      msg.sign.generating = false
      return
    }
    msg.sign.status = '正在生成「' + keyword + '」的手语视频...'
    msg.sign.progress = 15
    // 第二步：调用流式接口生成对应手语视频
    const token = localStorage.getItem('sl_token') || ''
    const res = await fetch('/api/sign/generate-stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ text: keyword }),
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
          msg.sign.progress = 15 + Math.round(data.progress * 0.85)
          if (data.status) msg.sign.status = data.status
          if (data.type === 'result') {
            msg.sign.videoUrl = data.videoUrl || ''
            msg.sign.videoInfo = {
              chinese_text: data.chinese_text || keyword,
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
    msg.sign.generating = false
  }
}

function _methodLabel(method) {
  const map = { retrieval: '句向量检索', deepseek: 'DeepSeek 改写', gloss: 'Gloss 匹配', stitch: '视频拼接' }
  return map[method] || method
}

/**
 * 将 AI 优质问答保存到素材
 * @param {Object} msg AI 消息对象
 */
function saveToMaterials(msg) {
  const idx = messages.value.indexOf(msg)
  const question = idx > 0 && messages.value[idx - 1].role === 'user' ? messages.value[idx - 1].text : ''
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  pendingSaveName.value = `AI问答 ${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
  pendingSaveContent.value = question ? `问：${question}\n\n答：${msg.text}` : msg.text
  pickerOpen.value = true
}

function onPickFolder(folderId) {
  materialsStore.addTextMaterial(folderId, pendingSaveName.value, pendingSaveContent.value)
  pickerOpen.value = false
  showToast('已保存到素材')
}

onMounted(() => {
  messages.value.push({
    role: 'ai',
    text: '你好，我是杏云 AI 课堂助手，可以教你学手语，试试下面的快捷提问吧！',
    sign: null,
  })
  scrollToBottom()
})
</script>

<template>
  <div class="class-tab">
    <!-- 对话内容区 -->
    <div ref="chatList" class="chat-list scroll-area">
      <div
        v-for="(msg, i) in messages"
        :key="i"
        class="msg-row"
        :class="msg.role === 'user' ? 'msg-user' : 'msg-ai'"
      >
        <div class="bubble-wrap" :class="msg.role === 'user' ? 'wrap-user' : 'wrap-ai'">
          <div class="bubble" :class="msg.role === 'user' ? 'bubble-user' : 'bubble-ai'">
            {{ msg.text }}
          </div>
          <!-- AI 气泡操作按钮 -->
          <div v-if="msg.role === 'ai'" class="bubble-actions">
            <button class="act-btn btn-press" @click="saveToMaterials(msg)">
              💾 保存
            </button>
            <button
              v-if="!msg.sign?.videoUrl && !msg.sign?.generating"
              class="act-btn btn-press"
              @click="loadSignVideo(msg)"
            >
              🤟 手语视频
            </button>
            <!-- 生成中进度 -->
            <div v-if="msg.sign?.generating" class="sign-generating">
              <span class="gen-spin">⏳</span>
              <span class="gen-text">{{ msg.sign.status || '生成中...' }}</span>
              <span class="gen-pct">{{ Math.round(msg.sign.progress) }}%</span>
            </div>
          </div>
          <!-- 手语视频预览（生成完成后展开） -->
          <div v-if="msg.sign?.videoUrl" class="sign-video-card glass">
            <video class="sign-video" controls autoplay>
              <source :src="msg.sign.videoUrl" type="video/mp4" />
            </video>
            <div v-if="msg.sign.videoInfo" class="sign-video-info">
              <span class="info-label">匹配度</span>
              <span class="info-val">{{ (msg.sign.videoInfo.similarity * 100).toFixed(1) }}%</span>
              <span class="info-label">方式</span>
              <span class="info-val method-tag" :class="msg.sign.videoInfo.method">{{ _methodLabel(msg.sign.videoInfo.method) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 快捷提问标签 -->
    <div class="quick-tags">
      <button
        v-for="tag in quickTags"
        :key="tag"
        class="quick-tag btn-press"
        @click="sendMessage(tag)"
      >
        {{ tag }}
      </button>
    </div>

    <!-- 底部输入发送栏 -->
    <div class="input-bar glass">
      <button
        class="mic-icon btn-press"
        :class="{ recording }"
        @click="toggleMic"
        aria-label="语音输入"
      >
        🎤
      </button>
      <input
        v-model="inputText"
        class="chat-input"
        placeholder="输入问题或点击麦克风语音提问..."
        @keyup.enter="onEnter"
      />
      <BaseButton variant="yellow" size="sm" @click="sendMessage()">发送</BaseButton>
    </div>

    <!-- 文件夹选择弹窗 -->
    <FolderPicker
      :open="pickerOpen"
      @close="pickerOpen = false"
      @select="onPickFolder"
    />
  </div>
</template>

<style scoped>
.class-tab {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* 对话区 */
.chat-list {
  flex: 1;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.msg-row {
  display: flex;
}
.msg-ai {
  justify-content: flex-start;
}
.msg-user {
  justify-content: flex-end;
}
.bubble-wrap {
  display: flex;
  flex-direction: column;
  max-width: 85%;
}
.wrap-ai {
  align-items: flex-start;
}
.wrap-user {
  align-items: flex-end;
}
.bubble {
  padding: 12px 16px;
  border-radius: 18px;
  font-size: 14px;
  line-height: 1.5;
  word-break: break-word;
}
.bubble-ai {
  background: var(--gradient-yellow);
  color: var(--text-on-yellow);
  border-bottom-left-radius: 6px;
}
.bubble-user {
  background: var(--glass-bg-strong);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  color: var(--text-primary);
  border-bottom-right-radius: 6px;
}

/* AI 气泡操作按钮 */
.bubble-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}
.act-btn {
  padding: 5px 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid var(--glass-border);
  font-size: 12px;
  color: var(--text-primary);
  min-height: 32px;
  cursor: pointer;
}
.sign-generating {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.4);
  font-size: 12px;
  color: var(--text-secondary);
}
.gen-spin {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.gen-pct {
  min-width: 28px;
  text-align: right;
}

/* 手语视频卡片 */
.sign-video-card {
  margin-top: 8px;
  padding: 10px;
  border-radius: var(--radius-md);
  width: 100%;
  max-width: 300px;
}
.sign-video {
  width: 100%;
  border-radius: 8px;
  display: block;
}
.sign-video-info {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 6px;
  font-size: 12px;
  flex-wrap: wrap;
}
.info-label {
  color: var(--text-secondary);
}
.info-val {
  color: var(--text-primary);
}
.method-tag {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 4px;
  font-size: 11px;
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}
.method-tag.stitch {
  background: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
}

/* 快捷标签 */
.quick-tags {
  flex-shrink: 0;
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  overflow-x: auto;
}
.quick-tags::-webkit-scrollbar {
  display: none;
}
.quick-tag {
  flex-shrink: 0;
  padding: 8px 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid var(--glass-border);
  font-size: 13px;
  color: var(--text-primary);
  min-height: 40px;
  cursor: pointer;
}

/* 底部输入栏 */
.input-bar {
  flex-shrink: 0;
  margin: 0 12px calc(12px + var(--safe-bottom));
  padding: 8px 8px 8px 8px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-radius: 28px;
}
.mic-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.7);
  font-size: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  cursor: pointer;
  transition: background 0.2s;
  border: none;
}
.mic-icon.recording {
  background: var(--gradient-yellow);
  box-shadow: var(--shadow-yellow);
  animation: pulse 1.2s infinite;
}
@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(255, 221, 136, 0.5); }
  50% { box-shadow: 0 0 0 10px rgba(255, 221, 136, 0); }
}
.chat-input {
  flex: 1;
  border: none;
  background: none;
  font-size: 14px;
  color: var(--text-primary);
  min-height: 40px;
  outline: none;
}
</style>
