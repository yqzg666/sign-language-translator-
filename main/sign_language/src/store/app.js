import { reactive, computed, watch } from 'vue'

// 本地存储键名常量
const STORAGE_KEY = 'sign_ai_app_state'

/**
 * 从 localStorage 读取持久化状态
 * @returns {Object|null} 已保存的状态对象
 */
function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch (e) {
    return null
  }
}

// 初始默认状态
function defaultState() {
  return {
    isLoggedIn: false, // 登录态
    user: {
      account: '',
      nickname: '手语用户',
      avatar: '' // 头像地址，空则用占位
    },
    rememberPwd: false, // 记住密码
    savedAccount: '', // 缓存账号
    savedPassword: '', // 缓存密码
    settings: {
      notification: true, // 消息通知
      theme: '柔和' // 界面主题
    },
    selectedVoice: '声音 1', // 当前选用音色
    customVoices: [] // 自定义录音音色列表
  }
}

// 合并持久化状态与默认状态
const persisted = loadState()
const state = reactive({ ...defaultState(), ...persisted })

// 自动持久化：任意状态变更同步写入 localStorage
watch(
  state,
  (val) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(val))
  },
  { deep: true }
)

/**
 * 全局应用状态 composable
 * 提供登录、登出、注册、设置等操作的统一入口
 */
export function useAppStore() {
  // 是否已登录
  const isLoggedIn = computed(() => state.isLoggedIn)

  /**
   * 登录：写入登录态与用户信息
   * @param {string} account 账号
   * @param {string} [nickname] 昵称（来自后端响应，可选）
   */
  function login(account, nickname) {
    state.isLoggedIn = true
    state.user.account = account
    state.user.nickname = nickname || account || '手语用户'
  }

  /**
   * 注册：本地登记（实际注册由 authApi.register 完成）
   * @param {string} account 账号
   * @param {string} password 密码
   */
  function register(account, password) {
    state.savedAccount = account
    state.savedPassword = password
  }

  // 登出：清除登录态
  function logout() {
    state.isLoggedIn = false
  }

  /**
   * 更新用户资料：头像与昵称
   * 头像以 dataURL(base64) 形式存储，可在 localStorage 中持久化
   * @param {Object} patch 待更新字段 { avatar?, nickname? }
   */
  function updateProfile(patch) {
    if (Object.prototype.hasOwnProperty.call(patch, 'avatar')) {
      state.user.avatar = patch.avatar
    }
    if (Object.prototype.hasOwnProperty.call(patch, 'nickname')) {
      state.user.nickname = patch.nickname || state.user.nickname
    }
  }

  /**
   * 记住密码：缓存或清除账号密码
   * @param {string} account 账号
   * @param {string} password 密码
   * @param {boolean} remember 是否记住
   */
  function saveCredential(account, password, remember) {
    state.rememberPwd = remember
    if (remember) {
      state.savedAccount = account
      state.savedPassword = password
    } else {
      state.savedAccount = ''
      state.savedPassword = ''
    }
  }

  /**
   * 新增自定义音色
   * @param {string} name 音色名称
   */
  function addCustomVoice(name) {
    state.customVoices.push(name)
  }

  /**
   * 删除单个自定义音色
   * 若删除的是当前选用音色，则回退到默认系统音色
   * @param {string} name 音色名称
   */
  function removeCustomVoice(name) {
    state.customVoices = state.customVoices.filter((v) => v !== name)
    if (state.selectedVoice === name) {
      state.selectedVoice = '声音 1'
    }
  }

  /**
   * 批量删除自定义音色
   * @param {string[]} names 待删除音色名称数组
   */
  function removeCustomVoices(names) {
    const pending = new Set(names)
    state.customVoices = state.customVoices.filter((v) => !pending.has(v))
    if (pending.has(state.selectedVoice)) {
      state.selectedVoice = '声音 1'
    }
  }

  /**
   * 清除缓存：重置设置项与音色，保留登录态
   */
  function clearCache() {
    state.customVoices = []
    state.selectedVoice = '声音 1'
  }

  return {
    state,
    isLoggedIn,
    login,
    register,
    logout,
    updateProfile,
    saveCredential,
    addCustomVoice,
    removeCustomVoice,
    removeCustomVoices,
    clearCache
  }
}
