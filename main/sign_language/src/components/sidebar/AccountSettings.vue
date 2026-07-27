<script setup>
import { ref } from 'vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { userApi } from '@/api'
import { useAppStore } from '@/store/app'
import { showToast } from '@/composables/useToast'

const emit = defineEmits(['navigate', 'logout'])
const store = useAppStore()

const items = [
  { key: 'security', label: '账号与安全', value: '' },
  { key: 'phone', label: '绑定手机号', value: '未绑定' },
  { key: 'password', label: '修改登录密码', value: '' },
  { key: 'cancel', label: '注销账号', value: '' }
]

const confirmVisible = ref(false)
const cancelling = ref(false)

function onItemClick(key) {
  if (key === 'password') {
    emit('navigate', 'password')
    return
  }
  if (key === 'cancel') {
    confirmVisible.value = true
    return
  }
  const map = {
    security: '账号与安全：当前账号状态正常',
    phone: '绑定手机号：暂未开放绑定操作'
  }
  showToast(map[key] || '')
}

async function confirmCancel() {
  cancelling.value = true
  try {
    await userApi.deleteAccount()
    confirmVisible.value = false
    showToast('账号已注销')
    // 清除本地登录态，触发父组件跳转登录页
    localStorage.removeItem('sl_token')
    store.logout()
    emit('logout')
  } catch (e) {
    showToast(e.message || '注销失败，请稍后重试')
  } finally {
    cancelling.value = false
  }
}
</script>

<template>
  <div class="account-page scroll-area">
    <section class="group glass">
      <button
        v-for="item in items"
        :key="item.key"
        class="setting-item btn-press"
        @click="onItemClick(item.key)"
      >
        <span class="item-label">{{ item.label }}</span>
        <span class="item-right">
          <span v-if="item.value" class="item-value">{{ item.value }}</span>
          <span class="item-arrow">›</span>
        </span>
      </button>
    </section>

    <transition name="modal">
      <div v-if="confirmVisible" class="modal-mask" @click.self="confirmVisible = false">
        <div class="confirm-modal glass">
          <p class="confirm-title">确认注销账号</p>
          <p class="confirm-desc">
            注销后账号数据将无法恢复，确定要继续注销吗？
          </p>
          <div class="confirm-actions">
            <BaseButton variant="ghost" size="sm" :disabled="cancelling" @click="confirmVisible = false">
              取消
            </BaseButton>
            <BaseButton variant="yellow" size="sm" :disabled="cancelling" @click="confirmCancel">
              {{ cancelling ? '注销中...' : '确认注销' }}
            </BaseButton>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.account-page {
  flex: 1;
  padding: 16px;
  position: relative;
}
.group {
  padding: 6px 16px;
}
.setting-item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 0;
  min-height: var(--touch-target);
  border-bottom: 1px solid rgba(255, 255, 255, 0.6);
  text-align: left;
}
.setting-item:last-child {
  border-bottom: none;
}
.item-label {
  font-size: 15px;
  color: var(--text-primary);
}
.item-right {
  display: flex;
  align-items: center;
  gap: 6px;
}
.item-value {
  font-size: 14px;
  color: var(--text-secondary);
}
.item-arrow {
  color: var(--text-secondary);
  font-size: 18px;
}
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
