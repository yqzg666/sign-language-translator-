<script setup>
import { useAppStore } from '@/store/app'

defineProps({
  open: { type: Boolean, default: false }
})
const emit = defineEmits(['close', 'menu'])

const store = useAppStore()

// 菜单项配置
const menus = [
  { key: 'voice', label: '语音库', icon: '🎙' },
  { key: 'account', label: '账号设置', icon: '👤' },
  { key: 'general', label: '通用设置', icon: '⚙️' },
  { key: 'logout', label: '退出登录', icon: '🚪' }
]

/**
 * 点击菜单项：通知父组件处理
 * @param {string} key 菜单标识
 */
function onMenu(key) {
  emit('menu', key)
}
</script>

<template>
  <!-- 遮罩层：点击关闭侧边栏 -->
  <transition name="fade">
    <div v-if="open" class="sidebar-mask" @click="emit('close')"></div>
  </transition>

  <!-- 右侧滑出毛玻璃面板 -->
  <transition name="slide">
    <aside v-if="open" class="sidebar glass">
      <!-- 用户信息区：点击进入编辑资料页 -->
      <button class="user-info btn-press" @click="onMenu('profile')">
        <div class="avatar">
          <img v-if="store.state.user.avatar" :src="store.state.user.avatar" alt="头像" />
          <span v-else>😊</span>
        </div>
        <p class="nickname">{{ store.state.user.nickname }}</p>
        <p class="edit-hint">点击编辑资料 ›</p>
      </button>

      <!-- 功能菜单 -->
      <nav class="menu-list">
        <button
          v-for="item in menus"
          :key="item.key"
          class="menu-item btn-press"
          @click="onMenu(item.key)"
        >
          <span class="menu-icon">{{ item.icon }}</span>
          <span class="menu-label">{{ item.label }}</span>
          <span class="menu-arrow" v-if="item.key !== 'logout'">›</span>
        </button>
      </nav>
    </aside>
  </transition>
</template>

<style scoped>
.sidebar-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.32);
  backdrop-filter: blur(2px);
  z-index: 40;
}
.sidebar {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: 78%;
  max-width: 320px;
  border-radius: var(--radius-lg) 0 0 var(--radius-lg);
  padding: calc(20px + var(--safe-top)) 20px calc(20px + var(--safe-bottom));
  display: flex;
  flex-direction: column;
  z-index: 41;
}

/* 用户信息 */
.user-info {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 0 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.6);
  text-align: center;
}
.avatar {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: var(--gradient-blue);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36px;
  overflow: hidden;
  box-shadow: var(--shadow-blue);
}
.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.nickname {
  margin-top: 12px;
  font-size: 17px;
  font-weight: 500;
  color: var(--text-primary);
}
.edit-hint {
  margin-top: 4px;
  font-size: 13px;
  color: var(--text-secondary);
}

/* 菜单 */
.menu-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 18px;
}
.menu-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border-radius: var(--radius-md);
  min-height: var(--touch-target);
  text-align: left;
  color: var(--text-primary);
  font-size: 15px;
}
.menu-item:active {
  background: rgba(104, 174, 247, 0.12);
}
.menu-icon {
  font-size: 20px;
}
.menu-label {
  flex: 1;
}
.menu-arrow {
  color: var(--text-secondary);
  font-size: 18px;
}

/* 过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.26s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.3s cubic-bezier(0.2, 0, 0.2, 1);
}
.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}
</style>
