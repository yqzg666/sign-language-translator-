/**
 * [Demo · 手势识别] 基于 MediaPipe 21 关键点的 **CSL 静态手势识别**
 *
 * 说明：
 *  - 纯前端、零后端，仅靠单帧关键点的几何特征做**近似**识别；
 *  - 识别内容为中国手语（CSL）中静态区分度高的几类：
 *      数字类  0–6（握拳/一~六）
 *      单指/组合手势  停（五指并拢立掌）、好（竖拇指）
 *  - 依赖数据：MediaPipe HandLandmarker 的 landmarks（每只手 21 个归一化 {x,y,z}）。
 *
 * 👉 这是演示用的独立模块，演示完可整段删除（连同 VideoTranslateTab 里的接入点即可）。
 */

// 手势 key → 展示文案（demo 用，可自行改词）
export const GESTURE_LABELS = {
  n0: '零 0',
  n1: '一 1',
  n2: '二 2',
  n3: '三 3',
  n4: '四 4',
  n5: '五 5',
  n6: '六 6',
  stop: '停 立掌',
  good: '好 竖拇指',
}

function dist(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y)
}

// 手指是否伸直：指尖到手腕距离 明显大于 该指根到手腕距离（k 越小越灵敏）
function fingerStraight(lm, tip, mcp, k = 1.12) {
  return dist(lm[tip], lm[0]) > dist(lm[mcp], lm[0]) * k
}

/**
 * 识别单手（21 点）→ 返回手势 key 或 null
 */
export function recognizeGesture(lm) {
  if (!lm || lm.length < 21) return null

  const handScale = dist(lm[0], lm[9]) || 1 // 手腕到中指根，用于相对阈值
  if (handScale <= 0) return null

  // 四指伸直状态
  const index = fingerStraight(lm, 8, 5)
  const middle = fingerStraight(lm, 12, 9)
  const ring = fingerStraight(lm, 16, 13)
  const pinky = fingerStraight(lm, 20, 17)
  const straightCount = [index, middle, ring, pinky].filter(Boolean).length

  // 拇指张开：拇指尖(4) 到 食指根(5)。阈值放低，覆盖竖拇指/张开的差异
  const thumbOpen = dist(lm[4], lm[5]) > 0.55 * handScale
  // 四指并拢度：相邻伸直指尖平均间距（用于识别「立掌(并拢)」，阈值收紧避免 4/5 误判为停）
  let close = false
  if (straightCount >= 3) {
    const tips = []
    if (index) tips.push(8)
    if (middle) tips.push(12)
    if (ring) tips.push(16)
    if (pinky) tips.push(20)
    let sum = 0
    let n = 0
    for (let i = 0; i + 1 < tips.length; i++) {
      sum += dist(lm[tips[i]], lm[tips[i + 1]])
      n++
    }
    if (n > 0) close = sum / n < 0.6 * handScale
  }

  // 1) 六：仅小指伸（食/中/无名弯）—— 不强制拇指，保证可识别
  if (!index && !middle && !ring && pinky) return 'n6'
  // 2) 好：拇指张开 + 四指基本弯（直指数 ≤2）→ 竖拇指
  if (thumbOpen && straightCount <= 2) return 'good'
  // 3) 零：四指全弯 + 拇指收
  if (straightCount === 0) return 'n0'
  // 4) 四指全直 → 停(立掌) / 五 / 四（4 与 5 只用拇指区分：张开=五，收起=四）
  if (straightCount === 4) {
    if (close) return 'stop'          // 五指并拢竖起 → 立掌(停)
    return thumbOpen ? 'n5' : 'n4'    // 4 与 5 只用拇指区分：张开=五，收起=四
  }
  // 5) 三：食中无名直，小指弯
  if (index && middle && ring && !pinky) return 'n3'
  // 6) 二：食中指直
  if (index && middle && !ring && !pinky) return 'n2'
  // 7) 一：仅食指直
  if (index && !middle && !ring && !pinky) return 'n1'

  return null
}

/**
 * 组合双手 landmarks → 返回当前最优手势 key（多手取第一个非空）
 * @param {Array<Array<{x,y}>>} hands
 */
export function recognizeHands(hands) {
  if (!hands || !hands.length) return null
  for (const h of hands) {
    const g = recognizeGesture(h)
    if (g) return g
  }
  return null
}

/**
 * 手势 → 展示文案
 */
export function gestureLabel(key) {
  return key ? GESTURE_LABELS[key] : ''
}
