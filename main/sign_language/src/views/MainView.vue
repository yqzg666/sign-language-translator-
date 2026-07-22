<script setup>
import { ref, computed } from 'vue'
import SignLanguageTab from '@/components/tabs/SignLanguageTab.vue'
import VideoTranslateTab from '@/components/tabs/VideoTranslateTab.vue'
import AIClassroomTab from '@/components/tabs/AIClassroomTab.vue'
import SidebarPanel from '@/components/sidebar/SidebarPanel.vue'
import VoiceLibrary from '@/components/sidebar/VoiceLibrary.vue'
import AccountSettings from '@/components/sidebar/AccountSettings.vue'
import GeneralSettings from '@/components/sidebar/GeneralSettings.vue'
import EditProfile from '@/components/sidebar/EditProfile.vue'
import ChangePassword from '@/components/sidebar/ChangePassword.vue'
import MaterialsPage from '@/components/materials/MaterialsPage.vue'
import { useAppStore } from '@/store/app'

const store = useAppStore()

// 底部 Tab 配置：key / 标题 / 图标
const tabs = [
  { key: 'sign', title: '实时手语综合', icon: '👐' },
  { key: 'video', title: '视频翻译配音', icon: '🎬' },
  { key: 'classroom', title: '杏云同学', icon: '🎓' }
]

const activeTab = ref('sign') // 当前激活 Tab
const sidebarOpen = ref(false) // 侧边栏开关
const activeSubPage = ref(null) // 当前内嵌子页面：null / voice / account / general / profile / password / materials
const pageStack = ref([]) // 子页面历史栈：支持多级返回（如 account → password）
const materialsTitle = ref('我的素材') // 素材页当前标题（随层级变化）
const materialsRef = ref(null) // 素材页实例引用，用于调用 goBack

// 顶部标题随 Tab / 子页面同步
const currentTitle = computed(() => {
  const map = {
    voice: '语音库',
    account: '账号设置',
    general: '通用设置',
    profile: '编辑资料',
    password: '修改密码'
  }
  if (activeSubPage.value === 'materials') return materialsTitle.value
  if (activeSubPage.value) return map[activeSubPage.value]
  return tabs.find((t) => t.key === activeTab.value)?.title || ''
})

// 仅 Tab1 显示侧边栏入口按钮
const showSidebarBtn = computed(() => activeTab.value === 'sign' && !activeSubPage.value)

// 仅 Tab3 显示我的素材入口按钮（全局唯一入口）
const showMaterialsBtn = computed(() => activeTab.value === 'classroom' && !activeSubPage.value)

/**
 * 切换底部 Tab
 * @param {string} key Tab 标识
 */
function switchTab(key) {
  activeTab.value = key
}

// 打开侧边栏
function openSidebar() {
  sidebarOpen.value = true
}

// 关闭侧边栏
function closeSidebar() {
  sidebarOpen.value = false
  // 退出登录时一并关闭所有子页面
  activeSubPage.value = null
  pageStack.value = []
}

function handleLogout() {
  localStorage.removeItem('sl_token')
  store.logout()
  closeSidebar()
  location.href = '/'
}

// 打开我的素材页（从 Tab3 入口）
function openMaterials() {
  materialsTitle.value = '我的素材'
  openSubPage('materials')
}

/**
 * 进入顶层子页面：清空历史栈，返回时回到 Tab
 * @param {string} key 子页面标识
 */
function openSubPage(key) {
  pageStack.value = []
  activeSubPage.value = key
}

/**
 * 进入下一级子页面：压入当前页到历史栈，返回时回到上一级
 * @param {string} key 子页面标识
 */
function pushSubPage(key) {
  pageStack.value.push(activeSubPage.value)
  activeSubPage.value = key
}

/**
 * 侧边栏菜单点击：退出登录即时跳转；其余关闭侧边栏并加载对应子页面
 * @param {string} key 子页面标识
 */
function handleMenuClick(key) {
  if (key === 'logout') {
    localStorage.removeItem('sl_token')
    store.logout()
    closeSidebar()
    location.href = '/'
    return
  }
  closeSidebar()
  openSubPage(key)
}

/**
 * 顶部返回键上下文处理
 * 素材页：先交由 MaterialsPage 处理内部层级返回，到达顶层后再关闭
 * 其他子页面：从历史栈弹出上一级；栈空则回到 Tab
 */
function handleBack() {
  if (activeSubPage.value === 'materials' && materialsRef.value) {
    const handled = materialsRef.value.goBack()
    if (handled) return
  }
  activeSubPage.value = pageStack.value.pop() ?? null
}

// 同步素材页标题
function onMaterialsTitle(title) {
  materialsTitle.value = title
}
</script>

<template>
  <div class="main-page">
    <!-- 顶部导航栏 -->
    <header class="nav-bar">
      <div class="nav-left">
        <!-- 子页面返回按钮：素材页内部层级优先处理 -->
        <button
          v-if="activeSubPage"
          class="icon-btn btn-press"
          @click="handleBack"
          aria-label="返回"
        >
          ‹
        </button>
      </div>
      <h1 class="nav-title">{{ currentTitle }}</h1>
      <div class="nav-right">
        <!-- 仅 Tab1 显示侧边栏入口 -->
        <button
          v-if="showSidebarBtn"
          class="icon-btn btn-press"
          @click="openSidebar"
          aria-label="侧边栏"
        >
          ☰
        </button>
        <!-- 仅 Tab3 显示我的素材入口（全局唯一入口） -->
        <button
          v-else-if="showMaterialsBtn"
          class="icon-btn btn-press"
          @click="openMaterials"
          aria-label="我的素材"
        >
          📁
        </button>
      </div>
    </header>

    <!-- 内容区域：Tab 内容与子页面覆盖层 -->
    <main class="content">
      <!-- Tab 内容区 -->
      <div v-show="!activeSubPage" class="tab-content">
        <SignLanguageTab v-show="activeTab === 'sign'" />
        <VideoTranslateTab v-show="activeTab === 'video'" />
        <AIClassroomTab v-show="activeTab === 'classroom'" />
      </div>

      <!-- 内嵌子页面覆盖层 -->
      <transition name="sub-page">
        <div v-if="activeSubPage" class="sub-page">
          <VoiceLibrary v-if="activeSubPage === 'voice'" @back="handleBack" />
          <AccountSettings
            v-else-if="activeSubPage === 'account'"
            @back="handleBack"
            @navigate="pushSubPage"
            @logout="handleLogout"
          />
          <GeneralSettings v-else-if="activeSubPage === 'general'" @back="handleBack" />
          <EditProfile v-else-if="activeSubPage === 'profile'" @back="handleBack" />
          <ChangePassword v-else-if="activeSubPage === 'password'" @back="handleBack" />
          <MaterialsPage
            v-else-if="activeSubPage === 'materials'"
            ref="materialsRef"
            @title="onMaterialsTitle"
          />
        </div>
      </transition>
    </main>

    <!-- 底部常驻 3 Tab 导航（子页面时隐藏） -->
    <nav v-show="!activeSubPage" class="tab-bar glass">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-item btn-press"
        :class="{ active: activeTab === tab.key }"
        @click="switchTab(tab.key)"
      >
        <span class="tab-icon">{{ tab.icon }}</span>
        <span class="tab-label">{{ tab.title }}</span>
      </button>
    </nav>

    <!-- 侧边栏（仅 Tab1 可打开） -->
    <SidebarPanel
      :open="sidebarOpen"
      @close="closeSidebar"
      @menu="handleMenuClick"
    />
  </div>
</template>

<style scoped>
.main-page {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  position: relative;
}

/* 顶部导航：毛玻璃 + 蓝色渐变标题 */
.nav-bar {
  flex-shrink: 0;
  height: calc(58px + var(--safe-top));
  padding: var(--safe-top) 16px 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.6);
  box-shadow: 0 2px 12px rgba(120, 150, 200, 0.1);
  z-index: 10;
}
.nav-left,
.nav-right {
  width: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
}
/* 标题：蓝色渐变 + 加粗，告别黑色字 */
.nav-title {
  font-size: 19px;
  font-weight: 700;
  letter-spacing: 0.6px;
  background: var(--gradient-blue);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}
/* 图标按钮：蓝色色调圆圈 */
.icon-btn {
  width: var(--touch-target);
  height: var(--touch-target);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  color: #4a8fe0;
  background: rgba(104, 174, 247, 0.16);
}

/* 内容区 */
.content {
  flex: 1;
  position: relative;
  overflow: hidden;
}
.tab-content {
  width: 100%;
  height: 100%;
}
.sub-page {
  position: absolute;
  inset: 0;
  background: var(--gradient-bg);
  display: flex;
  flex-direction: column;
}
.sub-page-enter-active,
.sub-page-leave-active {
  transition: transform 0.3s cubic-bezier(0.2, 0, 0.2, 1), opacity 0.3s ease;
}
.sub-page-enter-from {
  transform: translateX(30px);
  opacity: 0;
}
.sub-page-leave-to {
  transform: translateX(-30px);
  opacity: 0;
}

/* 底部 Tab 栏 */
.tab-bar {
  flex-shrink: 0;
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  border-bottom: none;
  padding: 8px 4px calc(8px + var(--safe-bottom));
  display: flex;
  justify-content: space-around;
}
.tab-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px 0;
  min-height: var(--touch-target);
  color: var(--text-secondary);
  border-radius: var(--radius-md);
}
.tab-item.active {
  color: var(--text-primary);
  background: rgba(104, 174, 247, 0.14);
}
.tab-icon {
  font-size: 20px;
}
.tab-label {
  font-size: 11px;
}
</style>
