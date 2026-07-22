<script setup>
// 全局轻提示组件：在 App.vue 挂载一次，由 useToast 的 showToast 触发
import { useToast } from '@/composables/useToast'

const { toastMessage } = useToast()
</script>

<template>
  <transition name="toast">
    <div v-if="toastMessage" class="app-toast">{{ toastMessage }}</div>
  </transition>
</template>

<style scoped>
/* 固定在屏幕底部居中，置顶且不拦截点击 */
.app-toast {
  position: fixed;
  left: 50%;
  bottom: calc(34px + var(--safe-bottom));
  transform: translateX(-50%);
  background: rgba(50, 55, 75, 0.86);
  color: #fff;
  padding: 10px 18px;
  border-radius: var(--radius-md);
  font-size: 13px;
  max-width: 86%;
  text-align: center;
  z-index: 9999;
  pointer-events: none;
}
.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}
</style>
