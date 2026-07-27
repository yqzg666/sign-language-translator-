<script setup>
import { watch } from 'vue'
import { useAppStore } from '@/store/app'
import AppToast from '@/components/ui/AppToast.vue'

const store = useAppStore()

// 主题中文名 → data-theme 属性值映射
const themeAttrMap = { 柔和: 'soft', 明亮: 'bright', 深色: 'dark' }

/**
 * 应用界面主题：在 <html> 上设置 data-theme 属性，
 * global.css 中按属性值覆盖 CSS 变量实现整体换肤
 * @param {string} theme 主题中文名
 */
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', themeAttrMap[theme] || 'soft')
}

// 初始化应用一次，并在主题变更时同步换肤
watch(() => store.state.settings.theme, applyTheme, { immediate: true })
</script>

<template>
  <!-- 应用根组件：承载路由出口、全局过渡动画与全局轻提示 -->
  <router-view v-slot="{ Component }">
    <transition name="page-fade" mode="out-in">
      <component :is="Component" />
    </transition>
  </router-view>
  <AppToast />
</template>
