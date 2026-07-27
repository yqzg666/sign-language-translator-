<script setup>
import { useAppStore } from '@/store/app'
import { showToast } from '@/composables/useToast'

const store = useAppStore()

// 界面主题可选项
const themes = ['柔和', '明亮', '深色']

/**
 * 切换消息通知开关
 */
function toggleNotification() {
  store.state.settings.notification = !store.state.settings.notification
}

/**
 * 选择界面主题
 * @param {string} name 主题名称
 */
function selectTheme(name) {
  store.state.settings.theme = name
}

/**
 * 清除缓存：调用 store 重置并提示
 */
function clearCache() {
  store.clearCache()
  showToast('缓存已清除')
}

/**
 * 点击关于：展示版本信息
 */
function showAbout() {
  showToast('手语 AI 助手  版本 v1.0')
}
</script>

<template>
  <div class="general-page scroll-area">
    <!-- 消息通知 -->
    <section class="group glass">
      <div class="setting-item">
        <span class="item-label">消息通知</span>
        <label class="switch">
          <input
            type="checkbox"
            :checked="store.state.settings.notification"
            @change="toggleNotification"
          />
          <span class="slider"></span>
        </label>
      </div>
    </section>

    <!-- 界面主题 -->
    <section class="group glass">
      <p class="group-title">界面主题</p>
      <div class="theme-row">
        <button
          v-for="t in themes"
          :key="t"
          class="theme-item btn-press"
          :class="{ active: store.state.settings.theme === t }"
          @click="selectTheme(t)"
        >
          {{ t }}
        </button>
      </div>
    </section>

    <!-- 其他设置 -->
    <section class="group glass">
      <button class="setting-item btn-press" @click="clearCache">
        <span class="item-label">清除缓存</span>
        <span class="item-arrow">›</span>
      </button>
      <button class="setting-item btn-press" @click="showAbout">
        <span class="item-label">关于手语 AI 助手</span>
        <span class="item-version">v1.0</span>
      </button>
    </section>
  </div>
</template>

<style scoped>
.general-page {
  flex: 1;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  position: relative;
}
.group {
  padding: 6px 16px;
}
.group-title {
  padding: 12px 0 8px;
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
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
.item-arrow,
.item-version {
  font-size: 14px;
  color: var(--text-secondary);
}

/* 主题选择 */
.theme-row {
  display: flex;
  gap: 10px;
  padding-bottom: 12px;
}
.theme-item {
  flex: 1;
  padding: 12px 0;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.6);
  border: 2px solid transparent;
  font-size: 14px;
  color: var(--text-primary);
  min-height: var(--touch-target);
}
.theme-item.active {
  border-color: var(--gradient-blue);
  background: rgba(104, 174, 247, 0.14);
}

/* 开关组件 */
.switch {
  position: relative;
  display: inline-block;
  width: 46px;
  height: 26px;
}
.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}
.slider {
  position: absolute;
  inset: 0;
  background: rgba(120, 140, 170, 0.3);
  border-radius: 13px;
  transition: 0.24s;
}
.slider::before {
  content: '';
  position: absolute;
  width: 20px;
  height: 20px;
  left: 3px;
  top: 3px;
  background: #fff;
  border-radius: 50%;
  transition: 0.24s;
}
.switch input:checked + .slider {
  background: var(--gradient-blue);
}
.switch input:checked + .slider::before {
  transform: translateX(20px);
}
</style>
