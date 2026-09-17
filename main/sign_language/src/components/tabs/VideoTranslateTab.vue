<script setup>
import { ref, computed, watch, onBeforeUnmount, onMounted, nextTick } from 'vue'
import { FilesetResolver, HandLandmarker } from '@mediapipe/tasks-vision'
// [Demo 手势识别] 可整段删除：演示用的静态手势识别（模块见 @/utils/handGesture.js）
import { recognizeHands, gestureLabel } from '@/utils/handGesture'
import BaseButton from '@/components/ui/BaseButton.vue'
import SaveSheet from '@/components/ui/SaveSheet.vue'
import FolderPicker from '@/components/materials/FolderPicker.vue'
import { useAppStore } from '@/store/app'
import { useMaterialsStore } from '@/store/materials'
import { videoApi, voiceApi } from '@/api'
import { showToast } from '@/composables/useToast'

// 手部骨架关联边（MediaPipe Hand 标准连线，21 个关键点）
const HAND_CONNECTIONS = [
  // 手掌
  [0, 1], [1, 2], [2, 3], [3, 4],       // 拇指
  [0, 5], [5, 6], [6, 7], [7, 8],       // 食指
  [0, 9], [9, 10], [10, 11], [11, 12],  // 中指
  [0, 13], [13, 14], [14, 15], [15, 16],// 无名指
  [0, 17], [17, 18], [18, 19], [19, 20],// 小指
  [5, 9], [9, 13], [13, 17],            // 指根横线
]
const HAND_DRAWING = { points: '#4ade80', lines: 'rgba(74, 222, 128, 0.85)' }

const store = useAppStore()
const materialsStore = useMaterialsStore()

// 保存相关状态
const saveSheetOpen = ref(false) // 保存选择面板
const pickerOpen = ref(false) // 保存到素材的文件夹选择弹窗

const videoSrc = ref('') // 上传视频预览地址
const videoEl = ref(null)
const isPlaying = ref(false)
const progress = ref(0) // 播放进度 0-100
const translating = ref(false)
const translateProgress = ref(0)
const translation = ref('') // AI 手语识别译文
const dubbing = ref(false) // 是否正在合成配音
const dubbed = ref(false) // 是否已合成配音
const audioUrl = ref('') // 配音音频 URL
const audioDuration = ref(0) // 配音时长（秒）
const audioEl = ref(null) // 配音 <audio> 引用
const audioPlaying = ref(false)
const audioProgress = ref(0) // 配音播放进度 0-100
const audioCurrentTime = ref('0:00')

// 录制视频相关状态
const recording = ref(false)
const recordDialogOpen = ref(false)
const mediaStream = ref(null)
let mediaRecorder = null
let recChunks = []

// ====== 手部骨架实时描线（MediaPipe，仅预览叠加，不进录制视频）======
let landmarker = null            // HandLandmarker 实例
let mpLoaded = false             // 是否已成功加载模型
let rafId = null                 // requestAnimationFrame 句柄
const handsReady = ref(false)    // 模型加载完成标记（用于可选提示）
const previewCanvas = ref(null)  // 叠加 canvas 引用
const previewVideo = ref(null)   // 预览 video 引用

// [Demo 手势识别] 识别结果 + 防抖（连续 ≥3 帧同手势才展示，避免抖动）
const liveGesture = ref('')
let _gestureKey = ''
let _gestureStreak = 0

function updateLiveGesture(hands) {
  const g = recognizeHands(hands) // 返回手势 key 或 null
  if (g === _gestureKey) {
    _gestureStreak++
  } else {
    _gestureKey = g
    _gestureStreak = 1
  }
  if (_gestureStreak >= 3) {
    liveGesture.value = gestureLabel(g)
  }
}

/**
 * 初始化 MediaPipe HandLandmarker（懒加载，成功后才开始检测）
 */
async function loadHandLandmarker() {
  if (landmarker || mpLoaded) return
  try {
    const vision = await FilesetResolver.forVisionTasks('/wasm')
    landmarker = await HandLandmarker.createFromOptions(vision, {
      baseOptions: {
        modelAssetPath: '/models/hand_landmarker.task',
        delegate: 'GPU',
      },
      runningMode: 'VIDEO',
      numHands: 2,
    })
    mpLoaded = true
    handsReady.value = true
  } catch (e) {
    console.warn('手部模型加载失败，将不显示骨架线:', e)
  }
}

/**
 * 在 canvas 上绘制手部骨架线
 * @param {Array} landmarks 归一化关键点 (x,y,z)
 * @param {number} w canvas 宽
 * @param {number} h canvas 高
 */
function drawHand(ctx, landmarks, w, h) {
  ctx.strokeStyle = HAND_DRAWING.lines
  ctx.lineWidth = 4
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  for (const [a, b] of HAND_CONNECTIONS) {
    const pa = landmarks[a]
    const pb = landmarks[b]
    if (!pa || !pb) continue
    const ax = pa.x * w
    const ay = pa.y * h
    const bx = pb.x * w
    const by = pb.y * h
    ctx.beginPath()
    ctx.moveTo(ax, ay)
    ctx.lineTo(bx, by)
    ctx.stroke()
  }
  // 关节圆点
  ctx.fillStyle = HAND_DRAWING.points
  for (const p of landmarks) {
    ctx.beginPath()
    ctx.arc(p.x * w, p.y * h, 5, 0, Math.PI * 2)
    ctx.fill()
  }
}

/**
 * 逐帧驱动：读取预览 video 当前帧 → 送入模型 → 描线
 */
function animateHands() {
  if (!landmarker || !previewCanvas.value || !previewVideo.value) return
  const v = previewVideo.value
  const c = previewCanvas.value
  if (v.readyState >= 2 && v.videoWidth > 0) {
    // 同步 canvas 与视频尺寸
    if (c.width !== v.videoWidth || c.height !== v.videoHeight) {
      c.width = v.videoWidth
      c.height = v.videoHeight
    }
    const ctx = c.getContext('2d')
    ctx.clearRect(0, 0, c.width, c.height)
    try {
      const result = landmarker.detectForVideo(v, performance.now())
      if (result.landmarks?.length) {
        for (const lm of result.landmarks) {
          drawHand(ctx, lm, c.width, c.height)
        }
        // [Demo 手势识别] 依据关键点识别当前手势
        updateLiveGesture(result.landmarks)
      } else {
        // 手离开画面 → 清空识别结果
        updateLiveGesture(null)
      }
    } catch (e) {
      // 检测瞬间失败可忽略，下一帧继续
    }
  }
  rafId = requestAnimationFrame(animateHands)
}

// 配音语言选项：中文默认使用语音库选定声音；其余为各语种配音
const dubLanguages = [
  { key: 'zh', label: '中文' },
  { key: 'en', label: '英文' },
  { key: 'yue', label: '粤语' },
  { key: 'sc', label: '四川方言' },
  { key: 'ja', label: '日语' }
]
const selectedLang = ref('zh')

// 当前语音库选定的声音（中文配音时使用）
const selectedVoice = computed(() => store.state.selectedVoice)

// 判断当前选中音色是否为克隆音色（非系统内置）
const isClonedVoice = computed(() => {
  const v = store.state.selectedVoice
  return v && !['声音 1', '声音 2', '声音 3'].includes(v)
})

/**
 * 获取语言中文名
 * @param {string} key 语言 key
 * @returns {string} 语言中文名
 */
function langLabel(key) {
  return dubLanguages.find((l) => l.key === key)?.label || key
}

/**
 * 识别视频中的手语译文（上传与录制共用），流式进度
 * @param {File|Blob} file 视频文件
 */
async function recognizeVideo(file) {
  if (videoSrc.value) URL.revokeObjectURL(videoSrc.value)
  videoSrc.value = URL.createObjectURL(file)
  translation.value = ''
  dubbed.value = false
  // 调用后端：识别视频中的手语译文（流式进度）
  translating.value = true
  translateProgress.value = 0
  const decoder = new TextDecoder()
  try {
    const reader = await videoApi.translateVideoStream(file)
    let buf = ''
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop() || ''
      for (const line of lines) {
        if (!line.trim()) continue
        try {
          const evt = JSON.parse(line)
          translateProgress.value = evt.progress
          if (evt.type === 'result') {
            translation.value = evt.translation
          } else if (evt.type === 'error') {
            translation.value = evt.error || '识别失败'
          }
        } catch (e) {
          // 跳过损坏行
        }
      }
    }
  } catch {
    translation.value = '识别失败，请重试'
  } finally {
    translating.value = false
  }
}

/**
 * 触发本地视频上传，并调用后端识别手语译文
 */
function triggerUpload() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'video/*'
  input.onchange = (e) => {
    const file = e.target.files[0]
    if (!file) return
    recognizeVideo(file)
  }
  input.click()
}

/**
 * 关闭/移除当前视频：清空预览与译文，回到上传界面
 */
function closeVideo() {
  stopCameraStream()
  if (videoSrc.value) URL.revokeObjectURL(videoSrc.value)
  videoSrc.value = ''
  isPlaying.value = false
  progress.value = 0
  translation.value = ''
  translating.value = false
  dubbed.value = false
  audioUrl.value = ''
  audioDuration.value = 0
  audioProgress.value = 0
  audioPlaying.value = false
  audioCurrentTime.value = '0:00'
}

/**
 * 停止并释放摄像头
 */
function stopCameraStream() {
  if (mediaStream.value) {
    mediaStream.value.getTracks().forEach((t) => t.stop())
    mediaStream.value = null
  }
}

/**
 * 停止手部描线动画循环
 */
function stopHandLoop() {
  if (rafId) { cancelAnimationFrame(rafId); rafId = null }
}

/**
 * 打开摄像头预览（不录制）
 * 点击「录制视频」后先进入此态，等用户点「开始录制」才真正录制
 */
async function openPreview() {
  try {
    if (!mediaStream.value) {
      mediaStream.value = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    }
    recChunks = []
    // 仅创建 recorder，不 start
    mediaRecorder = new MediaRecorder(mediaStream.value, { mimeType: 'video/webm' })
    mediaRecorder.ondataavailable = (e) => recChunks.push(e.data)
    mediaRecorder.onstop = () => {
      const blob = new Blob(recChunks, { type: 'video/webm' })
      stopCameraStream()
      recordDialogOpen.value = false
      recording.value = false
      recognizeVideo(blob)
    }
    recording.value = false
    recordDialogOpen.value = true
    initializeHandPreview()
  } catch (e) {
    showToast('摄像头不可用，请检查权限')
  }
}

/**
 * 初始化录制预览的手部骨架描线（懒加载模型 + 启动逐帧检测循环）
 */
async function initializeHandPreview() {
  await loadHandLandmarker()
  if (!landmarker) return
  await nextTick()
  rafId = requestAnimationFrame(animateHands)
}

/**
 * 开始真正录制（预览态下点「开始录制」）
 */
function startCapturing() {
  if (!mediaRecorder) return
  recChunks = []
  mediaRecorder.start()
  recording.value = true
}

/**
 * 停止录制：停止 recorder，onstop 会关闭弹框并触发识别
 */
function stopCapturing() {
  if (!mediaRecorder) return
  recording.value = false
  mediaRecorder.stop()
}

/**
 * 预览态下关闭：未录制则直接关摄像头；录制中则走 onstop 关闭
 */
function closePreview() {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop()
    return
  }
  stopHandLoop()
  recordDialogOpen.value = false
  stopCameraStream()
}

/**
 * 录制入口：打开/关闭预览弹框
 */
function toggleRecord() {
  if (recordDialogOpen.value) {
    closePreview()
  } else {
    openPreview()
  }
}

/**
 * 播放 / 暂停切换
 */
function togglePlay() {
  if (!videoEl.value) return
  if (videoEl.value.paused) videoEl.value.play()
  else videoEl.value.pause()
}

// 重播：回到起点并播放
function replay() {
  if (!videoEl.value) return
  videoEl.value.currentTime = 0
  videoEl.value.play()
}

// 视频时间更新：同步进度条
function onTimeUpdate() {
  if (!videoEl.value) return
  const dur = videoEl.value.duration || 1
  progress.value = (videoEl.value.currentTime / dur) * 100
}

// 拖动进度条跳转
function seekProgress(e) {
  if (!videoEl.value || !videoEl.value.duration) return
  videoEl.value.currentTime = (Number(e.target.value) / 100) * videoEl.value.duration
}

// 切换配音语言时，隐藏已有的配音播放条
watch(selectedLang, () => {
  dubbed.value = false
  audioUrl.value = ''
  audioDuration.value = 0
  audioProgress.value = 0
  audioPlaying.value = false
  audioCurrentTime.value = '0:00'
})

/**
 * 下载配音音频
 */
function downloadAudio() {
  if (!audioUrl.value) return
  const a = document.createElement('a')
  a.href = audioUrl.value
  a.download = ''
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

/**
 * 合成配音：文本 → TTS 音频，显示独立播放条
 */
async function compose() {
  if (!translation.value) return
  dubbing.value = true
  audioUrl.value = ''
  audioProgress.value = 0
  audioPlaying.value = false
  audioCurrentTime.value = '0:00'
  try {
    // 中文 + 克隆音色 → 使用 dub-v2 API
    if (selectedLang.value === 'zh' && isClonedVoice.value) {
      const res = await voiceApi.dubWithClone(
        translation.value,
        'zh',
        selectedVoice.value
      )
      audioUrl.value = res.audio_url || ''
      audioDuration.value = res.duration || 0
      dubbed.value = true
      showToast(`已合成配音（${selectedVoice.value} 克隆音色）`)
    } else {
      const res = await videoApi.dubVideo(translation.value, selectedLang.value)
      audioUrl.value = res.audio_url || ''
      audioDuration.value = res.duration || 0
      dubbed.value = true
      showToast(`已合成配音（${langLabel(selectedLang.value)}）`)
    }
  } catch {
    showToast('合成失败，请重试')
  } finally {
    dubbing.value = false
  }
}

// 配音音频播放控制
function toggleAudioPlay() {
  if (!audioEl.value) return
  if (audioEl.value.paused) {
    audioEl.value.play()
  } else {
    audioEl.value.pause()
  }
}

function onAudioTimeUpdate() {
  if (!audioEl.value || !audioEl.value.duration) return
  const cur = audioEl.value.currentTime
  const dur = audioEl.value.duration
  audioProgress.value = (cur / dur) * 100
  const m = Math.floor(cur / 60)
  const s = Math.floor(cur % 60)
  audioCurrentTime.value = `${m}:${String(s).padStart(2, '0')}`
}

function onAudioPlay() { audioPlaying.value = true }
function onAudioPause() { audioPlaying.value = false }
function onAudioEnded() { audioPlaying.value = false; audioProgress.value = 0; audioCurrentTime.value = '0:00' }

function seekAudio(e) {
  if (!audioEl.value || !audioEl.value.duration) return
  audioEl.value.currentTime = (Number(e.target.value) / 100) * audioEl.value.duration
}

function formatDur(sec) {
  if (!sec) return '0:00'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

// 保存到相册（模拟）
function saveToAlbum() {
  showToast('已保存到相册（模拟）')
}

/**
 * 将配音视频对应的译文脚本保存到素材：唤起文件夹选择弹窗
 * 注：视频为前端模拟，故以译文脚本形式保存
 */
function saveToMaterials() {
  if (!translation.value) return
  pickerOpen.value = true
}

/**
 * 选择文件夹后写入文本素材（配音视频脚本）
 * @param {string} folderId 目标文件夹 ID
 */
function onPickFolder(folderId) {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  const name = `配音视频脚本 ${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
  materialsStore.addTextMaterial(folderId, name, translation.value)
  pickerOpen.value = false
  showToast('已保存到素材')
}

// 保存选择面板：选择保存到相册
function onSaveAlbum() {
  saveSheetOpen.value = false
  saveToAlbum()
}

// 保存选择面板：选择保存到素材
function onSaveMaterials() {
  saveSheetOpen.value = false
  saveToMaterials()
}

// 组件挂载时预加载手部模型，避免用户点录制时等待下载/初始化
onMounted(() => {
  loadHandLandmarker()
})

onBeforeUnmount(() => {
  stopHandLoop()
  stopCameraStream()
  if (videoSrc.value) URL.revokeObjectURL(videoSrc.value)
})
</script>

<template>
  <div class="vt-tab scroll-area">
    <!-- 上传 / 录制入口 -->
    <div class="source-actions">
      <BaseButton variant="blue" @click="triggerUpload">
        <img src="/bg/btn-upload.png" class="source-icon" alt="" />
        本地视频上传
      </BaseButton>
      <BaseButton variant="blue" @click="toggleRecord">
        {{ recordDialogOpen ? '关闭预览' : '录制视频' }}
        <img src="/bg/btn-record.png" class="source-icon" alt="" />
      </BaseButton>
    </div>

    <!-- 预览区：录制摄像头预览（内嵌卡片）/ 上传视频预览 / 空态 -->
    <div v-if="recordDialogOpen" class="video-frame glass">
      <button class="video-close btn-press" @click="closePreview" aria-label="关闭预览">✕</button>
      <div class="record-preview-wrap">
        <video ref="previewVideo" :srcObject="mediaStream" class="record-preview" autoplay playsinline muted></video>
        <canvas ref="previewCanvas" class="record-overlay"></canvas>
        <span v-if="handsReady" class="hand-badge">🖐 手部追踪</span>
        <span v-else class="hand-badge hand-badge--loading">🖐 手部追踪加载中…</span>
        <!-- [Demo 手势识别] 实时识别词 -->
        <span v-if="liveGesture" class="gesture-badge">{{ liveGesture }}</span>
      </div>
      <BaseButton
        v-if="!recording"
        variant="yellow"
        block
        :disabled="!handsReady"
        @click="startCapturing"
      >
        ▶ 开始录制
      </BaseButton>
      <BaseButton v-else variant="yellow" block @click="stopCapturing">⏹ 停止录制</BaseButton>
    </div>
    <div v-else-if="!videoSrc" class="upload-panel glass">
      <img src="/bg/upload-hero.jpg" class="upload-hero" alt="" />
      <p>请先上传视频或录制手语动作</p>
    </div>
    <div v-else class="video-frame glass">
      <button class="video-close btn-press" @click="closeVideo" aria-label="关闭预览">✕</button>
      <video
        ref="videoEl"
        class="video-player"
        :src="videoSrc"
        playsinline
        @play="isPlaying = true"
        @pause="isPlaying = false"
        @timeupdate="onTimeUpdate"
      ></video>
      <input
        type="range"
        min="0"
        max="100"
        :value="progress"
        class="progress-bar"
        @input="seekProgress"
      />
      <div class="frame-ctrls">
        <button class="ctrl-btn btn-press" @click="togglePlay">
          {{ isPlaying ? '⏸ 暂停' : '▶ 播放' }}
        </button>
        <button class="ctrl-btn btn-press" @click="replay">🔁 重播</button>
      </div>
    </div>

    <!-- AI 手语识别译文（只读）+ 进度条 -->
    <div v-if="videoSrc" class="translation-card glass">
      <p class="card-label">AI 手语识别译文</p>
      <div v-if="translating" class="trans-progress">
        <div class="gen-progress-bar">
          <div class="gen-progress-fill" :style="{ width: translateProgress + '%' }"></div>
        </div>
        <span class="gen-progress-text">{{ Math.round(translateProgress) }}%</span>
      </div>
      <p v-else class="translation-text">{{ translation || '暂无识别结果' }}</p>
    </div>

    <!-- 配音声音/语言选择（上传后显示，与语音库区分） -->
    <div v-if="videoSrc" class="dub-card glass">
      <p class="card-label">配音声音</p>
      <div class="lang-chips">
        <button
          v-for="l in dubLanguages"
          :key="l.key"
          class="lang-chip btn-press"
          :class="{ active: selectedLang === l.key }"
          @click="selectedLang = l.key"
        >
          {{ l.label }}
        </button>
      </div>
      <p class="dub-hint">
        {{
          selectedLang === 'zh'
            ? isClonedVoice
              ? `中文将使用克隆音色「${selectedVoice}」合成`
              : `中文将使用语音库声音：${selectedVoice}`
            : `将以 ${langLabel(selectedLang)} 生成配音`
        }}
      </p>
    </div>

    <!-- 黄色合成按钮（未上传隐藏） -->
    <BaseButton v-if="videoSrc" variant="yellow" block :disabled="dubbing" @click="compose">
      {{ dubbing ? '合成中...' : '🎵 合成配音' }}
    </BaseButton>

    <!-- 配音播放条（合成后展开） -->
    <div v-if="dubbed && audioUrl" class="audio-bar glass">
      <audio
        ref="audioEl"
        :src="audioUrl"
        preload="auto"
        @timeupdate="onAudioTimeUpdate"
        @play="onAudioPlay"
        @pause="onAudioPause"
        @ended="onAudioEnded"
      ></audio>
      <div class="audio-bar-inner">
        <button class="audio-play-btn btn-press" @click="toggleAudioPlay">
          {{ audioPlaying ? '⏸' : '▶' }}
        </button>
        <div class="audio-track-wrap">
          <input
            type="range"
            min="0"
            max="100"
            :value="audioProgress"
            class="audio-track"
            @input="seekAudio"
          />
        </div>
        <span class="audio-time">{{ audioCurrentTime }} / {{ formatDur(audioDuration) }}</span>
        <span class="audio-lang-tag">{{ langLabel(selectedLang) }}</span>
        <button class="audio-dl-btn btn-press" title="下载配音音频" @click="downloadAudio">⬇</button>
      </div>
    </div>

    <!-- 合成完成后统一保存按钮 -->
    <BaseButton v-if="dubbed" variant="blue" block @click="saveSheetOpen = true">
      💾 保存
    </BaseButton>

    <!-- 保存选择面板：相册 / 素材 -->
    <SaveSheet
      :open="saveSheetOpen"
      @close="saveSheetOpen = false"
      @album="onSaveAlbum"
      @materials="onSaveMaterials"
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
.vt-tab {
  width: 100%;
  height: 100%;
  min-width: 0;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
/* 关键：内容变多时改为滚动而非把子项压扁，否则 video-frame 会被压缩并裁剪掉播放控件 */
.vt-tab > * {
  flex-shrink: 0;
}

/* 上传 / 录制入口按钮组 */
.source-actions {
  display: flex;
  gap: 10px;
  min-width: 0;
}
.source-actions > * {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
}
.source-icon {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  object-fit: cover;
  flex-shrink: 0;
}

/* 摄像头预览：高度跟随视频原始比例，避免强制 16:9 造成黑边错位 */
.record-preview {
  width: 100%;
  max-width: 100%;
  display: block;
  height: auto;
  background: #000;
  border-radius: var(--radius-md);
  object-fit: contain;
}
.record-preview-wrap {
  position: relative;
  width: 100%;
  min-width: 0;
  overflow: hidden;
  border-radius: var(--radius-md);
}
.record-overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  border-radius: var(--radius-md);
}
.hand-badge {
  position: absolute;
  top: 12px;
  right: 12px;
  padding: 4px 10px;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.5);
  color: #4ade80;
  font-size: 12px;
  pointer-events: none;
  backdrop-filter: blur(4px);
}
.hand-badge--loading {
  color: #fbbf24;
}
/* [Demo 手势识别] 识别词徽标 */
.gesture-badge {
  position: absolute;
  bottom: 14px;
  left: 50%;
  transform: translateX(-50%);
  padding: 7px 18px;
  border-radius: 18px;
  background: rgba(0, 0, 0, 0.62);
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.5px;
  pointer-events: none;
  backdrop-filter: blur(4px);
}

/* 上传提示面板 */
.upload-panel {
  aspect-ratio: 16 / 9;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-secondary);
}
.upload-hero {
  width: 108px;
  height: 108px;
  border-radius: 16px;
  object-fit: cover;
}
.upload-panel span {
  font-size: 40px;
}

/* 视频预览框（与页面毛玻璃 + 蓝调统一，非纯黑） */
.video-frame {
  position: relative;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
  overflow: hidden;
}
.video-close {
  position: absolute;
  top: 19px;
  left: 19px;
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: var(--surface-bg-strong);
  color: var(--text-primary);
  font-size: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
  box-shadow: var(--shadow-card);
}
.video-player {
  width: 100%;
  max-width: 100%;
  display: block;
  border-radius: var(--radius-md);
  background: #000;
  height: auto;
  object-fit: contain;
}
.progress-bar {
  width: 100%;
  height: 6px;
  -webkit-appearance: none;
  appearance: none;
  background: rgba(120, 150, 200, 0.25);
  border-radius: 3px;
}
.progress-bar::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--gradient-blue);
  cursor: pointer;
}
.frame-ctrls {
  display: flex;
  gap: 10px;
}
.ctrl-btn {
  padding: 8px 14px;
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid var(--glass-border);
  font-size: 13px;
  color: var(--text-primary);
  min-height: 40px;
}

/* 译文卡片（只读） */
.translation-card {
  padding: 16px;
}
.card-label {
  font-weight: 500;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}
/* 进度条 */
.trans-progress {
  display: flex;
  align-items: center;
  gap: 10px;
}
.trans-progress .gen-progress-bar {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: rgba(120, 150, 200, 0.2);
  overflow: hidden;
}
.trans-progress .gen-progress-fill {
  height: 100%;
  border-radius: 3px;
  background: var(--gradient-blue);
  transition: width 0.3s ease;
}
.trans-progress .gen-progress-text {
  font-size: 12px;
  color: var(--text-secondary);
  min-width: 32px;
  text-align: right;
}
.translation-text {
  font-size: 15px;
  color: var(--text-primary);
  line-height: 1.6;
}

/* 配音语言选择卡片 */
.dub-card {
  padding: 16px;
}
.lang-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}
.lang-chip {
  padding: 8px 14px;
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid var(--glass-border);
  font-size: 13px;
  color: var(--text-primary);
  min-height: 40px;
}
.lang-chip.active {
  background: var(--gradient-blue);
  border-color: transparent;
  color: #fff;
}
.dub-hint {
  font-size: 12px;
  color: var(--text-secondary);
}

/* 配音播放条 */
.audio-bar {
  padding: 10px 14px;
}
.audio-bar-inner {
  display: flex;
  align-items: center;
  gap: 10px;
}
.audio-play-btn {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--gradient-blue);
  color: #fff;
  font-size: 15px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.audio-track-wrap {
  flex: 1;
}
.audio-track {
  width: 100%;
  height: 5px;
  -webkit-appearance: none;
  appearance: none;
  background: rgba(120, 150, 200, 0.25);
  border-radius: 3px;
  outline: none;
}
.audio-track::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--gradient-blue);
  cursor: pointer;
}
.audio-time {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
  min-width: 80px;
  text-align: right;
}
.audio-lang-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(99, 102, 241, 0.1);
  color: #6366f1;
  white-space: nowrap;
}
.audio-dl-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(99, 102, 241, 0.1);
  color: #6366f1;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}
.audio-dl-btn:hover {
  background: rgba(99, 102, 241, 0.2);
}
</style>