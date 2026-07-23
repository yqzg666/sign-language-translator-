<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import SaveSheet from '@/components/ui/SaveSheet.vue'
import FolderPicker from '@/components/ui/FolderPicker.vue'
import { useAppStore } from '@/store/app'
import { useMaterialsStore } from '@/store/materials'
import { videoApi, voiceApi } from '@/api'
import { showToast } from '@/composables/useToast'

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
 * 触发本地视频上传，并调用后端识别手语译文
 */
function triggerUpload() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'video/*'
  input.onchange = async (e) => {
    const file = e.target.files[0]
    if (!file) return
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
  input.click()
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

onBeforeUnmount(() => {
  if (videoSrc.value) URL.revokeObjectURL(videoSrc.value)
  if (progressTimer) clearInterval(progressTimer)
})
</script>

<template>
  <div class="vt-tab scroll-area">
    <!-- 上传按钮 -->
    <BaseButton variant="blue" block @click="triggerUpload">📁 本地视频上传</BaseButton>

    <!-- 视频预览框 -->
    <div class="video-frame glass">
      <template v-if="videoSrc">
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
      </template>
      <div v-else class="empty-state">
        <span>🎬</span>
        <p>请先上传视频</p>
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
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* 视频预览框 */
.video-frame {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.video-player {
  width: 100%;
  border-radius: var(--radius-md);
  background: #000;
  aspect-ratio: 16 / 9;
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
.empty-state {
  aspect-ratio: 16 / 9;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-secondary);
}
.empty-state span {
  font-size: 40px;
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
</style>
