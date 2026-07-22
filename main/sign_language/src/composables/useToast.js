import { ref } from 'vue'

// 全局唯一的 toast 消息（模块级单例，跨组件共享，避免每个组件重复定义）
const toastMessage = ref('')
let timer = null

/**
 * 显示轻提示，2 秒后自动消失
 * 用法：任意组件 import { showToast } from '@/composables/useToast' 后调用 showToast('文案')
 * @param {string} msg 提示文案
 */
export function showToast(msg) {
  toastMessage.value = msg
  clearTimeout(timer)
  timer = setTimeout(() => (toastMessage.value = ''), 2000)
}

// 供 AppToast 组件订阅消息
export function useToast() {
  return { toastMessage }
}
