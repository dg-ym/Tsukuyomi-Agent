<template>
  <div class="login-page">
	<div class="header">
      <h2 class="main-title">月读</h2>
      <p class="sub-title">请登录您的账号</p>
    </div>

    <div class="login-card">
      <div class="form-item">
        <label class="label">邮箱</label>
        <input
          class="input"
          :class="{ error: error.email }"
          v-model="form.email"
          type="text"
          placeholder="请输入注册邮箱"
          @blur="validateEmail"
        />
      </div>

      <div class="form-item">
        <label class="label">密码</label>
        <input
          class="input"
          :class="{ error: error.password }"
          v-model="form.password"
          type="password"
          placeholder="请输入密码"
          @blur="validatePassword"
        />
      </div>

      <div class="forgot-pwd">
        <span @click="goForgetPwd">忘记密码?</span>
      </div>

      <button class="login-btn" @click="handleLogin">立即登录</button>

      <div class="register-tip">
        还没有账号？
        <span class="link-text" @click="goRegister">立即注册</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import http from '/http/http.js'

onMounted(() => {
  const token = uni.getStorageSync('token')
  if (token && isTokenValid(token)) {
    uni.redirectTo({ url: '/pages/main' })
  }
})

function isTokenValid(token) {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.exp * 1000 > Date.now()
  } catch {
    uni.removeStorageSync('token')
    return false
  }
}

const form = reactive({
  email: '',
  password: ''
})

const error = reactive({
  email: false,
  password: false
})

// 邮箱校验
const validateEmail = () => {
  if (!form.email.trim()) {
    error.email = true
    uni.showToast({ title: '请输入邮箱', icon: 'none' })
    return false
  }
  const emailReg = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailReg.test(form.email)) {
    error.email = true
    uni.showToast({ title: '邮箱格式不正确', icon: 'none' })
    return false
  }
  error.email = false
  return true
}

// 密码校验
const validatePassword = () => {
  if (!form.password.trim()) {
    error.password = true
    uni.showToast({ title: '请输入密码', icon: 'none' })
    return false
  }
  if (form.password.length < 6 || form.password.length > 20) {
    error.password = true
    uni.showToast({ title: '密码长度为6-20位', icon: 'none' })
    return false
  }
  error.password = false
  return true
}

// 登录
const handleLogin = async () => {
  if (!validateEmail()) return
  if (!validatePassword()) return

  try {
    let result = await http.login(form.email, form.password)
    uni.showToast({ title: '登录成功！', icon: 'success' })
    
    let user = result.user
    let token = result.token
    uni.setStorageSync('user', user)
    uni.setStorageSync('token', token)

    uni.redirectTo({ url: '/pages/main' })
  } catch (e) {
    uni.showToast({
      title: e.message || '登录失败，邮箱或密码错误',
      icon: 'none'
    })
  }
}

const goRegister = () => {
  uni.redirectTo({ url: '/pages/register' })
}

const goForgetPwd = () => {
  uni.redirectTo({ url: '/pages/reset-psw' })
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  background: linear-gradient(to bottom, #fff, #ffefe0);
  padding: 20px;
  box-sizing: border-box;
  background: url('@/assets/images/backGround.png') no-repeat center center;
  background-size: cover; /* 这将确保图片覆盖整个区域且不变形 */
}

.header {
  text-align: center;
  margin-bottom: 30px;
}

.main-title {
  font-size: 40px;
  color: #f55027;
  font-weight: bold;
  margin: 10px 0;
}

.sub-title {
  font-size: 18px;
  color: #666;
  margin: 0;
}

.login-card {
  background: #fff;
  border-radius: 16px;
  padding: 30px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  max-width: 400px;
  margin: 0 auto;
}

.form-item {
  margin-bottom: 24px;
}

.label {
  display: block;
  font-size: 18px;
  color: #333;
  margin-bottom: 8px;
}

.input {
  width: 100%;
  height: 50px;
  border: 1px solid #eee;
  border-radius: 10px;
  padding: 0 16px;
  font-size: 16px;
  box-sizing: border-box;
}

.input.error {
  border-color: #f55027 !important;
  background-color: #fff5f5;
}

.input:focus {
  outline: none;
  border-color: #f55027;
}

.forgot-pwd {
  text-align: right;
  margin-bottom: 24px;
}

.forgot-pwd span {
  color: #f55027;
  font-size: 16px;
  cursor: pointer;
}

.login-btn {
  width: 100%;
  height: 56px;
  background: linear-gradient(to right, #ff9053, #f55027);
  color: #fff;
  border: none;
  border-radius: 28px;
  font-size: 20px;
  cursor: pointer;
}

.register-tip {
  text-align: center;
  margin-top: 30px;
  font-size: 16px;
  color: #666;
}

.link-text {
  color: #f55027;
  cursor: pointer;
}
</style>