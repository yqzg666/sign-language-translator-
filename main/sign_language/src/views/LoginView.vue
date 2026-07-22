<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/store/app'
import { authApi } from '@/api'
import { showToast } from '@/composables/useToast'

const router = useRouter()
const store = useAppStore()

// 登录表单
const account = ref('')
const password = ref('')
const rememberPwd = ref(false)
const logging = ref(false)
const loginError = ref('')

// 注册弹窗
const regVisible = ref(false)
const regForm = ref({ account: '', password: '', confirm: '' })
const regError = ref('')
const regLoading = ref(false)

// 页面加载：检查 token，填充记住密码
onMounted(async () => {
  if (store.state.isLoggedIn) {
    try {
      await authApi.verifyToken()
      router.push('/main')
      return
    } catch {
      store.logout()
    }
  }
  if (store.state.rememberPwd) {
    account.value = store.state.savedAccount
    password.value = store.state.savedPassword
    rememberPwd.value = true
  }
})

async function handleLogin() {
  loginError.value = ''
  if (!account.value) { loginError.value = '请输入账号'; return }
  if (!password.value) { loginError.value = '请输入密码'; return }
  logging.value = true
  try {
    const { token, user } = await authApi.login(account.value, password.value)
    localStorage.setItem('sl_token', token)
    store.saveCredential(account.value, password.value, rememberPwd.value)
    store.login(account.value, user?.nickname)
    showToast('登录成功')
    router.push('/main')
  } catch (e) {
    loginError.value = e.message || '登录失败'
  } finally {
    logging.value = false
  }
}

function openRegister() {
  regForm.value = { account: '', password: '', confirm: '' }
  regError.value = ''
  regVisible.value = true
}
function closeRegister() { regVisible.value = false }

async function submitRegister() {
  const { account: acc, password: pwd, confirm } = regForm.value
  if (!acc || !pwd || !confirm) { regError.value = '请填写完整信息'; return }
  if (pwd !== confirm) { regError.value = '两次输入的密码不一致'; return }
  if (acc.length < 2) { regError.value = '账号至少 2 个字符'; return }
  if (pwd.length < 6) { regError.value = '密码至少 6 位'; return }
  regLoading.value = true
  regError.value = ''
  try {
    await authApi.register(acc, pwd)
    showToast('注册成功，请登录')
    closeRegister()
    account.value = acc
    password.value = pwd
  } catch (e) {
    regError.value = e.message || '注册失败'
  } finally {
    regLoading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <!-- 装饰背景元素 -->
    <div class="bg-decoration">
      <div class="bg-circle c1"></div>
      <div class="bg-circle c2"></div>
      <div class="bg-circle c3"></div>
    </div>

    <div class="login-container">
      <!-- Logo / 品牌区 -->
      <div class="brand">
        <div class="brand-icon">🤟</div>
        <h1 class="brand-title">手语 AI 助手</h1>
        <p class="brand-desc">让沟通没有障碍</p>
      </div>

      <!-- 登录卡片 -->
      <div class="login-card glass">
        <div class="card-header">
          <span class="card-title">欢迎回来</span>
          <span class="card-subtitle">请登录您的账号</span>
        </div>

        <div class="input-group">
          <div class="input-field">
            <span class="input-icon">👤</span>
            <input
              v-model="account"
              class="input-box"
              placeholder="请输入账号"
              autocomplete="username"
            />
          </div>
          <div class="input-field">
            <span class="input-icon">🔒</span>
            <input
              v-model="password"
              type="password"
              class="input-box"
              placeholder="请输入密码"
              autocomplete="current-password"
              @keyup.enter="handleLogin"
            />
          </div>
        </div>

        <label class="remember-row">
          <div class="check-box" :class="{ checked: rememberPwd }" @click="rememberPwd = !rememberPwd">
            <span v-if="rememberPwd" class="check-mark">✓</span>
          </div>
          <span class="remember-text">记住密码</span>
        </label>

        <p v-if="loginError" class="error-msg">{{ loginError }}</p>

        <button class="login-btn" :disabled="logging" @click="handleLogin">
          {{ logging ? '登录中...' : '登 录' }}
        </button>

        <div class="divider"><span>还没有账号？</span></div>

        <button class="register-btn" @click="openRegister">注册新账号</button>
      </div>
    </div>

    <!-- 注册弹窗 -->
    <transition name="modal">
      <div v-if="regVisible" class="modal-mask" @click.self="closeRegister">
        <div class="register-card glass">
          <button class="modal-x btn-press" @click="closeRegister">✕</button>
          <div class="modal-brand">
            <span class="modal-brand-icon">🤟</span>
            <h2 class="modal-title">注册账号</h2>
          </div>
          <div class="input-field">
            <span class="input-icon">👤</span>
            <input v-model="regForm.account" class="input-box" placeholder="设置账号（至少 2 位）" autocomplete="username" />
          </div>
          <div class="input-field">
            <span class="input-icon">🔒</span>
            <input v-model="regForm.password" type="password" class="input-box" placeholder="设置密码（至少 6 位）" autocomplete="new-password" />
          </div>
          <div class="input-field">
            <span class="input-icon">🔒</span>
            <input v-model="regForm.confirm" type="password" class="input-box" placeholder="确认密码" autocomplete="new-password" @keyup.enter="submitRegister" />
          </div>
          <p v-if="regError" class="error-msg">{{ regError }}</p>
          <button class="login-btn register-submit" :disabled="regLoading" @click="submitRegister">
            {{ regLoading ? '注册中...' : '提交注册' }}
          </button>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.login-page {
  width: 100%;
  min-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  padding: 24px;
}

/* 装饰背景元素 */
.bg-decoration {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.bg-circle {
  position: absolute;
  border-radius: 50%;
  opacity: 0.5;
}
.c1 {
  width: 280px;
  height: 280px;
  background: linear-gradient(130deg, rgba(104,174,247,0.3), rgba(132,192,255,0.15));
  top: -60px;
  right: -80px;
}
.c2 {
  width: 200px;
  height: 200px;
  background: linear-gradient(130deg, rgba(255,221,136,0.3), rgba(255,235,181,0.15));
  bottom: 60px;
  left: -50px;
}
.c3 {
  width: 120px;
  height: 120px;
  background: linear-gradient(130deg, rgba(200,160,255,0.25), rgba(180,140,255,0.1));
  bottom: -30px;
  right: 40px;
}

.login-container {
  width: 100%;
  max-width: 360px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 32px;
  position: relative;
  z-index: 1;
}

/* 品牌区 */
.brand {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
.brand-icon {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: var(--gradient-blue);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36px;
  box-shadow: 0 6px 20px rgba(104,174,247,0.35);
  margin-bottom: 4px;
}
.brand-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 1px;
}
.brand-desc {
  font-size: 14px;
  color: var(--text-secondary);
  letter-spacing: 2px;
}

/* 登录卡片 */
.login-card {
  width: 100%;
  padding: 28px 24px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.card-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 4px;
}
.card-title {
  font-size: 20px;
  font-weight: 500;
  color: var(--text-primary);
}
.card-subtitle {
  font-size: 13px;
  color: var(--text-secondary);
}

/* 输入框 */
.input-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.input-field {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.65);
  border: 1.5px solid rgba(200, 215, 235, 0.4);
  transition: border-color 0.2s;
}
.input-field:focus-within {
  border-color: var(--gradient-blue);
  background: rgba(255, 255, 255, 0.85);
}
.input-icon {
  font-size: 18px;
  flex-shrink: 0;
}
.input-box {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 15px;
  color: var(--text-primary);
  min-height: 24px;
}
.input-box::placeholder {
  color: var(--text-secondary);
  opacity: 0.7;
}

/* 记住密码 */
.remember-row {
  display: flex;
  align-items: center;
  gap: 10px;
  user-select: none;
  cursor: pointer;
}
.check-box {
  width: 20px;
  height: 20px;
  border-radius: 6px;
  border: 1.5px solid rgba(120, 150, 200, 0.5);
  background: rgba(255, 255, 255, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.2s;
}
.check-box.checked {
  background: var(--gradient-blue);
  border-color: transparent;
}
.check-mark {
  font-size: 12px;
  color: #fff;
  line-height: 1;
}
.remember-text {
  font-size: 14px;
  color: var(--text-secondary);
}

/* 错误信息 */
.error-msg {
  color: #e06a78;
  font-size: 13px;
  text-align: center;
  margin: -4px 0;
}

/* 登录按钮 */
.login-btn {
  width: 100%;
  padding: 14px;
  border-radius: var(--radius-md);
  background: var(--gradient-blue);
  color: #fff;
  font-size: 16px;
  font-weight: 500;
  letter-spacing: 4px;
  min-height: var(--touch-target);
  box-shadow: 0 4px 14px rgba(104,174,247,0.3);
  transition: opacity 0.2s;
}
.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.login-btn:active:not(:disabled) {
  opacity: 0.85;
}

/* 分割线 */
.divider {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--text-secondary);
  font-size: 13px;
}
.divider::before,
.divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: rgba(120, 150, 200, 0.2);
}

/* 注册按钮 */
.register-btn {
  width: 100%;
  padding: 12px;
  border-radius: var(--radius-md);
  border: 1.5px solid rgba(255, 221, 136, 0.6);
  background: rgba(255, 221, 136, 0.1);
  color: var(--text-primary);
  font-size: 15px;
  min-height: var(--touch-target);
  transition: background 0.2s;
}
.register-btn:active {
  background: rgba(255, 221, 136, 0.25);
}

/* ===== 注册弹窗 ===== */
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 50;
}
.register-card {
  width: 100%;
  max-width: 340px;
  padding: 28px 24px 24px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  position: relative;
}
.modal-x {
  position: absolute;
  top: 14px;
  right: 14px;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(230, 238, 250, 0.6);
  color: var(--text-secondary);
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.modal-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 4px;
}
.modal-brand-icon {
  font-size: 28px;
}
.modal-title {
  font-size: 20px;
  font-weight: 500;
  color: var(--text-primary);
}
.register-submit {
  background: var(--gradient-yellow);
  color: var(--text-primary);
  letter-spacing: 2px;
  box-shadow: 0 4px 14px rgba(255,221,136,0.3);
}

/* 弹窗过渡 */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.24s ease;
}
.modal-enter-active .register-card,
.modal-leave-active .register-card {
  transition: transform 0.28s cubic-bezier(0.2, 0, 0.2, 1), opacity 0.28s ease;
}
.modal-enter-from,
.modal-leave-to { opacity: 0; }
.modal-enter-from .register-card,
.modal-leave-to .register-card {
  transform: scale(0.88);
  opacity: 0;
}
</style>
