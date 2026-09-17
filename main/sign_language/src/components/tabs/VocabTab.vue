<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { vocabApi } from '@/api'
import { showToast } from '@/composables/useToast'

/* 手语斩：以百词斩式卡片记忆中国手语词汇
 * - 学词：看词→看手语视频/文字要领（正反双方向）
 * - 答题：看手语视频四选一选词
 * - 错题集：答错的词重点重练
 * - 打卡：自动记录连续学习天数
 */
const words = ref([])
const loading = ref(true)
const prepRunning = ref(false)  // 后端批量预加载中
const prepDone = ref(0)          // 本次已生成词数
let prepTimer = null

// 学习 / 答题 / 错题复习
const mode = ref('learn')           // learn | quiz | wrong
const direction = ref('forward')    // forward 看词学动作 | reverse 看动作猜词
const cardIndex = ref(0)
const flipped = ref(false)
const generatingId = ref(null)
const loadingText = ref('')

// 打卡
const streak = ref(0)
const todayChecked = ref(false)

// 学习进度 / 错题
const progressSet = ref(new Set())
const wrongSet = ref(new Set())

// 四选一答题
const quiz = ref(null)        // { wordId, options: [{id, word}] }
const quizAnswer = ref(null)  // 用户已选 id
const quizDone = ref(false)
const quizCorrect = ref(null)
const quizScore = ref(0)
const quizAnswered = ref(0)

const CHECKIN_KEY = 'sl_vocab_checkin'
const WRONG_KEY = 'sl_vocab_wrong'
const PROGRESS_KEY = 'sl_vocab_progress'

function todayStr() {
  const d = new Date()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mm}-${dd}`
}

function loadLocal() {
  try {
    const c = JSON.parse(localStorage.getItem(CHECKIN_KEY) || 'null')
    if (c) { streak.value = c.streak; todayChecked.value = c.date === todayStr() }
    wrongSet.value = new Set(JSON.parse(localStorage.getItem(WRONG_KEY) || '[]'))
    progressSet.value = new Set(JSON.parse(localStorage.getItem(PROGRESS_KEY) || '[]'))
  } catch (e) { /* 忽略 */ }
}
const saveWrong = () => localStorage.setItem(WRONG_KEY, JSON.stringify([...wrongSet.value]))
const saveProgress = () => localStorage.setItem(PROGRESS_KEY, JSON.stringify([...progressSet.value]))

function checkIn() {
  const today = todayStr()
  const c = JSON.parse(localStorage.getItem(CHECKIN_KEY) || 'null')
  if (c && c.date === today) { streak.value = c.streak; todayChecked.value = true; return }
  let newStreak = 1
  if (c) {
    const diff = Math.round((new Date(today) - new Date(c.date)) / 86400000)
    newStreak = diff === 1 ? c.streak + 1 : 1
  }
  streak.value = newStreak
  todayChecked.value = true
  localStorage.setItem(CHECKIN_KEY, JSON.stringify({ date: today, streak: newStreak }))
}

// 当前学习词池：错题模式只看错题；其余优先展示已生成视频的词，避免翻到空白卡
const learnPool = computed(() => {
  let pool = mode.value === 'wrong' ? words.value.filter((w) => wrongSet.value.has(w.id)) : words.value
  if (mode.value !== 'wrong') {
    pool = [...pool].sort(
      (a, b) => Number(!!(b.generated && b.video_url)) - Number(!!(a.generated && a.video_url))
    )
  }
  return pool
})
const current = computed(() => learnPool.value[cardIndex.value] || null)
const learnedCount = computed(() => progressSet.value.size)
// 已有独立演示视频的词数（用于「扩充词库」展示）
const genCount = computed(() => words.value.filter((w) => w.generated && w.video_url).length)

async function loadWords() {
  loading.value = true
  try {
    const res = await vocabApi.list()
    words.value = res.words || []
  } catch (e) {
    showToast('词库加载失败')
  } finally {
    loading.value = false
  }
}

function markLearned(id) {
  progressSet.value.add(id)
  saveProgress()
}

// 首次查看某词：若未生成则调用后端生成视频+说明并缓存
async function ensureGenerated(word) {
  if (!word) return
  if (word.generated && word.video_url) return
  if (generatingId.value === word.id) return
  generatingId.value = word.id
  loadingText.value = '正在生成手语视频...'
  try {
    const updated = await vocabApi.generate(word.id)
    const idx = words.value.findIndex((w) => w.id === word.id)
    if (idx >= 0) words.value[idx] = { ...words.value[idx], ...updated }
  } catch (e) {
    showToast('生成失败：' + (e.message || '请重试'))
  } finally {
    generatingId.value = null
    loadingText.value = ''
  }
}

function prevWord() {
  if (!learnPool.value.length) return
  flipped.value = false
  cardIndex.value = (cardIndex.value - 1 + learnPool.value.length) % learnPool.value.length
}
function nextWord() {
  if (!learnPool.value.length) return
  flipped.value = false
  cardIndex.value = (cardIndex.value + 1) % learnPool.value.length
}

let touchX = 0
function onTouchStart(e) { touchX = e.changedTouches[0].clientX }
function onTouchEnd(e) {
  const dx = e.changedTouches[0].clientX - touchX
  if (Math.abs(dx) > 50) { if (dx < 0) nextWord(); else prevWord() }
}

function switchMode(m) {
  mode.value = m
  cardIndex.value = 0
  flipped.value = false
  if (m === 'quiz') buildQuiz()
}
function switchDirection(d) {
  direction.value = d
  flipped.value = false
}

// 轮询后端批量预加载进度；完成后刷新词库
function startPolling() {
  if (prepTimer) clearInterval(prepTimer)
  prepTimer = setInterval(async () => {
    try {
      const s = await vocabApi.preloadStatus()
      prepDone.value = s.done || 0
      if (!s.running) {
        clearInterval(prepTimer)
        prepTimer = null
        prepRunning.value = false
        if (s.error) showToast('扩充失败：' + s.error)
        else {
          showToast(`已扩充 ${s.done} 词`)
          await loadWords()
          if (current.value) ensureGenerated(current.value)
        }
      }
    } catch (e) { /* 单次查询失败忽略，继续轮询 */ }
  }, 3000)
}

async function startPreload() {
  if (prepRunning.value) return
  prepDone.value = 0
  try {
    await vocabApi.preload(80)
    prepRunning.value = true
    startPolling()
  } catch (e) {
    showToast('触发扩充失败：' + (e.message || '请重试'))
  }
}

function shuffle(arr) {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

function buildQuiz() {
  quiz.value = null
  quizAnswer.value = null
  quizDone.value = false
  quizCorrect.value = null
  // 优先用已有视频的词出题，否则退化为全部词（点击会触发兜底生成）
  const ready = words.value.filter((w) => w.generated && w.video_url)
  const pool = ready.length >= 4 ? ready : words.value
  if (pool.length < 4) { showToast('题库不足'); return }
  const target = pool[Math.floor(Math.random() * pool.length)]
  const others = shuffle(pool.filter((w) => w.id !== target.id)).slice(0, 3)
  const options = shuffle([target, ...others]).map((o) => ({ id: o.id, word: o.word }))
  quiz.value = { wordId: target.id, options }
  ensureGenerated(target)
}

const quizWord = computed(() => words.value.find((w) => w.id === quiz.value?.wordId) || null)

function chooseAnswer(id) {
  if (!quiz.value || quizDone.value) return
  quizAnswer.value = id
  quizDone.value = true
  quizAnswered.value++
  if (id === quiz.value.wordId) {
    quizCorrect.value = true
    quizScore.value++
    wrongSet.value.delete(quiz.value.wordId)
  } else {
    quizCorrect.value = false
    wrongSet.value.add(quiz.value.wordId)
  }
  saveWrong()
  markLearned(quiz.value.wordId)
}

// 当前卡片指向的展示信息
const videoUrl = computed(() => current.value?.video_url || '')
const description = computed(() => current.value?.description || '')
const isGenerating = computed(() => generatingId.value !== null)

onMounted(async () => {
  loadLocal()
  checkIn()
  await loadWords()
  // 若后端正在预加载（如页面刷新后仍在跑），恢复进度轮询
  try {
    const s = await vocabApi.preloadStatus()
    if (s.running) { prepRunning.value = true; prepDone.value = s.done || 0; startPolling() }
  } catch (e) { /* 忽略 */ }
  if (current.value) ensureGenerated(current.value)
})

onBeforeUnmount(() => {
  if (prepTimer) clearInterval(prepTimer)
})

watch(current, (w) => {
  flipped.value = false
  if (w) ensureGenerated(w)
})
</script>

<template>
  <div class="vocab-tab scroll-area">
    <!-- 统计 / 打卡 -->
    <div class="stats-row">
      <div class="stat-card glass">
        <span class="stat-num">{{ streak }}</span>
        <span class="stat-label">🔥 连续天数</span>
      </div>
      <div class="stat-card glass">
        <span class="stat-num">{{ learnedCount }}</span>
        <span class="stat-label">✅ 已学词汇</span>
      </div>
      <div class="stat-card glass">
        <span class="stat-num">{{ words.length }}</span>
        <span class="stat-label">📚 词库收录</span>
      </div>
    </div>

    <!-- 模式切换 -->
    <div class="segment glass">
      <button class="seg-btn btn-press" :class="{ active: mode === 'learn' }" @click="switchMode('learn')">📖 学词</button>
      <button class="seg-btn btn-press" :class="{ active: mode === 'quiz' }" @click="switchMode('quiz')">✍️ 答题</button>
      <button class="seg-btn btn-press" :class="{ active: mode === 'wrong' }" @click="switchMode('wrong')">📕 错题集</button>
    </div>

    <!-- 方向切换（仅学词模式） -->
    <div v-if="mode === 'learn'" class="segment glass segment--sm">
      <button class="seg-btn btn-press" :class="{ active: direction === 'forward' }" @click="switchDirection('forward')">词 → 手语</button>
      <button class="seg-btn btn-press" :class="{ active: direction === 'reverse' }" @click="switchDirection('reverse')">手语 → 词</button>
    </div>

    <!-- 扩充词库：后台裁剪下一批单词语视频 -->
    <div class="extend-bar glass">
      <template v-if="!prepRunning">
        <span class="extend-hint">已有 {{ genCount }} 词含视频 · 词库共 {{ words.length }}</span>
        <button class="extend-btn btn-press" @click="startPreload">📥 扩充词库</button>
      </template>
      <template v-else>
        <span class="extend-hint extend-hint--loading">⏳ 扩充中… 已生成 {{ prepDone }} 词</span>
      </template>
    </div>

    <!-- 加载态 -->
    <div v-if="loading" class="empty-state glass">加载词库中...</div>

    <!-- 错题集空态 -->
    <div v-else-if="mode === 'wrong' && !learnPool.length" class="empty-state glass">🎉 暂无错题，继续保持！</div>

    <!-- 学词 / 错题：翻转卡片 -->
    <template v-else-if="mode !== 'quiz'">
      <div
        v-if="current"
        class="card-stage"
        @touchstart="onTouchStart"
        @touchend="onTouchEnd"
      >
        <div class="flip-card" :class="{ flipped }" @click="flipped = !flipped">
          <!-- 正面 -->
          <div class="face front">
            <template v-if="direction === 'forward'">
              <p class="word">{{ current.word }}</p>
              <p class="pinyin">{{ current.pinyin }}</p>
              <p class="face-hint">👆 点击查看手语</p>
            </template>
            <template v-else>
              <div v-if="videoUrl" class="face-video">
                <video :src="videoUrl" controls muted playsinline preload="metadata"></video>
              </div>
              <div v-else class="face-video face-video--empty">{{ isGenerating ? loadingText : '手语视频生成中…' }}</div>
              <p class="face-hint">👆 看手势，猜意思</p>
            </template>
          </div>
          <!-- 背面 -->
          <div class="face back">
            <template v-if="direction === 'forward'">
              <div v-if="videoUrl" class="face-video">
                <video :src="videoUrl" controls muted playsinline preload="metadata"></video>
              </div>
              <div v-else class="face-video face-video--empty">{{ isGenerating ? loadingText : '手语视频生成中…' }}</div>
              <p class="desc">{{ description || '暂无动作说明' }}</p>
            </template>
            <template v-else>
              <p class="word word--back">{{ current.word }}</p>
              <p class="pinyin">{{ current.pinyin }}</p>
              <p class="desc">{{ description }}</p>
            </template>
          </div>
        </div>
        <span v-if="isGenerating" class="gen-chip">⏳ 生成中…</span>
      </div>

      <!-- 卡片控制 -->
      <div class="card-ctrls" v-if="learnPool.length">
        <button class="ctrl-btn btn-press" @click="prevWord">‹ 上一词</button>
        <span class="ctrl-count">{{ cardIndex + 1 }} / {{ learnPool.length }}</span>
        <button class="ctrl-btn btn-press" @click="nextWord">下一词 ›</button>
      </div>
    </template>

    <!-- 答题：看视频四选一 -->
    <template v-else-if="mode === 'quiz'">
      <div v-if="quiz" class="quiz-card glass">
        <p class="quiz-title">看手语视频，选出正确含义</p>
        <div v-if="quizWord?.video_url" class="quiz-video">
          <video :src="quizWord.video_url" controls muted playsinline preload="metadata"></video>
        </div>
        <div v-else class="quiz-video quiz-video--empty">{{ isGenerating ? loadingText : '手语视频生成中…' }}</div>

        <div class="quiz-options">
          <button
            v-for="opt in quiz.options"
            :key="opt.id"
            class="quiz-opt btn-press"
            :class="{
              correct: quizDone && opt.id === quiz.wordId,
              wrong: quizDone && quizAnswer === opt.id && opt.id !== quiz.wordId
            }"
            :disabled="quizDone"
            @click="chooseAnswer(opt.id)"
          >
            {{ opt.word }}
          </button>
        </div>

        <div v-if="quizDone" class="quiz-result" :class="quizCorrect ? 'ok' : 'no'">
          {{ quizCorrect ? '✅ 答对了！' : '❌ 答错了，已加入错题集' }}
        </div>
        <BaseButton v-if="quizDone" variant="yellow" block @click="buildQuiz">下一题</BaseButton>
        <BaseButton v-else variant="blue" block disabled>请选择一个答案</BaseButton>
        <p class="quiz-score">已答 {{ quizAnswered }} 题 · 答对 {{ quizScore }} 题</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.vocab-tab {
  width: 100%;
  height: 100%;
  min-width: 0;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
/* 内容变多时滚动，避免被压扁 */
.vocab-tab > * {
  flex-shrink: 0;
}

/* 统计卡 */
.stats-row {
  display: flex;
  gap: 10px;
}
.stat-card {
  flex: 1;
  min-width: 0;
  padding: 12px 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.stat-num {
  font-size: 24px;
  font-weight: 700;
  background: var(--gradient-blue);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.stat-label {
  font-size: 11px;
  color: var(--text-secondary);
}

/* 分段切换 */
.segment {
  display: flex;
  padding: 4px;
  gap: 4px;
}
.segment--sm {
  padding: 3px;
}
.seg-btn {
  flex: 1;
  min-height: 40px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  color: var(--text-secondary);
  background: transparent;
}
.seg-btn.active {
  background: var(--gradient-blue);
  color: #fff;
}

/* 扩充词库 */
.extend-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 14px;
}
.extend-hint {
  font-size: 12px;
  color: var(--text-secondary);
  min-width: 0;
}
.extend-hint--loading {
  color: #fbbf24;
}
.extend-btn {
  padding: 8px 14px;
  border-radius: var(--radius-sm);
  background: var(--gradient-blue);
  color: #fff;
  font-size: 13px;
  white-space: nowrap;
  min-height: 40px;
}

/* 空态 */
.empty-state {
  padding: 32px 16px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 14px;
}

/* 翻转卡片 */
.card-stage {
  position: relative;
  perspective: 1200px;
  flex: 1;
  min-height: 330px;
}
.flip-card {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 330px;
  transform-style: preserve-3d;
  transition: transform 0.55s cubic-bezier(0.2, 0, 0.2, 1);
  cursor: pointer;
}
.flip-card.flipped {
  transform: rotateY(180deg);
}
.face {
  position: absolute;
  inset: 0;
  border-radius: var(--radius-md);
  background: var(--glass-bg-strong);
  border: 1px solid var(--glass-border);
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 18px;
  gap: 8px;
  overflow: hidden;
  box-shadow: var(--shadow-card);
}
.face.back {
  transform: rotateY(180deg);
}
.word {
  font-size: 34px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 2px;
}
.word--back {
  font-size: 28px;
}
.pinyin {
  font-size: 14px;
  color: var(--text-secondary);
  letter-spacing: 1px;
}
.face-hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 6px;
}
.face-video {
  width: 100%;
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.face-video video {
  width: 100%;
  height: auto;
  max-height: 100%;
  border-radius: var(--radius-sm);
  background: #000;
  display: block;
  object-fit: contain;
}
.face-video--empty {
  height: 90px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  font-size: 13px;
  background: rgba(120, 150, 200, 0.08);
  border-radius: var(--radius-sm);
}
.desc {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-primary);
  text-align: center;
  max-height: 90px;
  overflow: auto;
}
.gen-chip {
  position: absolute;
  top: 12px;
  right: 12px;
  padding: 3px 10px;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.45);
  color: #fbbf24;
  font-size: 11px;
}

/* 卡片控制 */
.card-ctrls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.ctrl-btn {
  padding: 10px 16px;
  border-radius: var(--radius-sm);
  background: var(--surface-bg);
  border: 1px solid var(--glass-border);
  color: var(--text-primary);
  font-size: 14px;
  min-height: 44px;
}
.ctrl-count {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
}

/* 答题 */
.quiz-card {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.quiz-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  text-align: center;
}
.quiz-video {
  width: 100%;
  border-radius: var(--radius-md);
  background: #000;
  overflow: hidden;
}
.quiz-video video {
  width: 100%;
  display: block;
  object-fit: contain;
}
.quiz-video--empty {
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  font-size: 13px;
  background: rgba(120, 150, 200, 0.1);
}
.quiz-options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.quiz-opt {
  padding: 14px 10px;
  border-radius: var(--radius-sm);
  background: var(--surface-bg);
  border: 1px solid var(--glass-border);
  color: var(--text-primary);
  font-size: 16px;
  min-height: 48px;
  font-weight: 500;
}
.quiz-opt.correct {
  background: rgba(74, 222, 128, 0.25);
  border-color: #4ade80;
  color: #15803d;
}
.quiz-opt.wrong {
  background: rgba(248, 113, 113, 0.25);
  border-color: #f87171;
  color: #b91c1c;
}
.quiz-opt:disabled {
  opacity: 1;
}
.quiz-result {
  text-align: center;
  font-size: 15px;
  font-weight: 500;
}
.quiz-result.ok { color: #15803d; }
.quiz-result.no { color: #b91c1c; }
.quiz-score {
  font-size: 12px;
  color: var(--text-secondary);
  text-align: center;
}
</style>
