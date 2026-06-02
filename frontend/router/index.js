import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/pages/index', name: 'index', component: {} },
  { path: '/pages/login', name: 'login', component: {} },
  { path: '/pages/register', name: 'register', component: {} },
  { path: '/pages/chat', name: 'chat', component: {}, meta: { requiresAuth: true } },
  { path: '/pages/main', name: 'main', component: {}, meta: { requiresAuth: true } },
  { path: '/pages/reset-psw', name: 'reset-psw', component: {} },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to, from, next) => {
  if (!to.meta.requiresAuth) return next()

  const token = uni.getStorageSync('token')
  if (!token) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return next('/pages/login')
  }

  // 校验 token 是否过期
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    if (payload.exp * 1000 < Date.now()) {
      uni.removeStorageSync('token')
      uni.showToast({ title: '登录已过期', icon: 'none' })
      return next('/pages/login')
    }
  } catch {
    uni.removeStorageSync('token')
    return next('/pages/login')
  }

  next()
})

export default router
