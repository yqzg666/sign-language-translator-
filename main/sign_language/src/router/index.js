import { createRouter, createWebHashHistory } from 'vue-router'
import { useAppStore } from '@/store/app'

// 路由表：登录页与主页面，个人中心类需登录态守卫
const routes = [
  { path: '/', redirect: '/login' },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录' }
  },
  {
    path: '/main',
    name: 'main',
    component: () => import('@/views/MainView.vue'),
    meta: { title: '手语 AI 助手', requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

// 全局前置守卫：未登录访问受保护页面时跳转登录
router.beforeEach((to) => {
  const store = useAppStore()
  const loggedIn = store.state.isLoggedIn
  if (to.meta.requiresAuth && !loggedIn) {
    return { name: 'login' }
  }
  if (to.name === 'login' && loggedIn) {
    return { name: 'main' }
  }
  return true
})

export default router
