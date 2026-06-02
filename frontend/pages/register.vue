<template>
  <view class="page-wrap">
    <view class="header">
      <text class="title">月读</text>
      <!-- <text class="sub-title">开启月读之旅</text> -->
    </view>

    <view class="card">
      <!-- 用户名 -->
      <view class="form-item">
        <text class="label">用户名</text>
        <input
          class="input"
          :class="{ error: error.username }"
          v-model="form.username"
          type="text"
          placeholder="2-12位字母/数字/中文"
          @blur="validateUsername"
        />
      </view>

      <!-- 邮箱 -->
      <view class="form-item">
        <text class="label">邮箱</text>
        <input
          class="input"
          :class="{ error: error.email }"
          v-model="form.email"
          type="text"
          placeholder="请输入邮箱"
          @blur="validateEmail"
        />
      </view>

      <!-- 验证码 -->
      <view class="form-item code-item">
        <text class="label">验证码</text>
        <view class="code-row">
          <input
            class="input code-input"
            :class="{ error: error.code }"
            v-model="form.code"
            type="text"
            placeholder="请输入4位验证码"
            @blur="validateCode"
          />
          <button
            class="code-btn"
            :class="{ disabled: countdown > 0 }"
            :disabled="countdown > 0"
            @tap="onSendCode"
          >
            {{ countdown > 0 ? `${countdown}s` : '获取验证码' }}
          </button>
        </view>
      </view>

      <!-- 密码 -->
      <view class="form-item">
        <text class="label">密码</text>
        <input
          class="input"
          :class="{ error: error.password }"
          v-model="form.password"
          type="password"
          placeholder="6-20位, 建议含字母+数字"
          @blur="validatePassword"
        />
      </view>

      <!-- 确认密码 -->
      <view class="form-item">
        <text class="label">确认密码</text>
        <input
          class="input"
          :class="{ error: error.rePassword }"
          v-model="form.rePassword"
          type="password"
          placeholder="请再次输入密码"
          @blur="validateRePassword"
        />
      </view>

      <button class="submit-btn" @tap="handleRegister">立即注册</button>

      <view class="link-tip">
        已有账号？
        <text class="link-text" @tap="goLogin">立即登录</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, reactive, onUnmounted } from 'vue'
import http from '/http/http.js'

const form = reactive({
  username: '',
  email: '',
  code: '',
  password: '',
  rePassword: ''
})

const error = reactive({
  username: false,
  email: false,
  code: false,
  password: false,
  rePassword: false
})

const countdown = ref(0)
const hasSendCode = ref(false)
let timer = null

// 用户名校验
const validateUsername = () => {
  if (!form.username.trim()) {
    error.username = true
    uni.showToast({ title: '请输入用户名', icon: 'none' })
    return false
  }
  if (form.username.length < 2 || form.username.length > 12) {
    error.username = true
    uni.showToast({ title: '用户名必须2-12位', icon: 'none' })
    return false
  }
  error.username = false
  return true
}

// 邮箱校验
const validateEmail = () => {
  if (!form.email.trim()) {
    error.email = true
    uni.showToast({ title: '请输入邮箱', icon: 'none' })
    return false
  }
  const reg = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!reg.test(form.email)) {
    error.email = true
    uni.showToast({ title: '邮箱格式不正确', icon: 'none' })
    return false
  }
  error.email = false
  return true
}

// 验证码校验
const validateCode = () => {
  if (!form.code.trim()) {
    error.code = true
    uni.showToast({ title: '请输入验证码', icon: 'none' })
    return false
  }
  if (form.code.length !== 4) {
    error.code = true
    uni.showToast({ title: '验证码错误', icon: 'none' })
    return false
  }
  error.code = false
  return true
}

// 密码校验
const validatePassword = () => {
  if (!form.password) {
    error.password = true
    uni.showToast({ title: '请输入密码', icon: 'none' })
    return false
  }
  if (form.password.length < 6 || form.password.length > 20) {
    error.password = true
    uni.showToast({ title: '密码长度6-20位', icon: 'none' })
    return false
  }
  error.password = false
  return true
}

// 确认密码校验
const validateRePassword = () => {
  if (!form.rePassword) {
    error.rePassword = true
    uni.showToast({ title: '请输入确认密码', icon: 'none' })
    return false
  }
  if (form.rePassword !== form.password) {
    error.rePassword = true
    uni.showToast({ title: '两次密码不一致', icon: 'none' })
    return false
  }
  error.rePassword = false
  return true
}

// 发送验证码
const onSendCode = async () => {
  if (!validateEmail()) return
  if (countdown.value > 0) return

  try {
    await http.getEmailCode(form.email)
    uni.showToast({ title: '验证码已发送', icon: 'success' })
    hasSendCode.value = true

    countdown.value = 60
    timer = setInterval(() => {
      countdown.value--
      if (countdown.value <= 0) clearInterval(timer)
    }, 1000)
  } catch (e) {
    uni.showToast({ title: e.message || '发送失败', icon: 'none' })
  }
}

// 注册提交
const handleRegister = async () => {
  if (!hasSendCode.value) {
    error.code = true
    uni.showToast({ title: '未获取验证码', icon: 'none' })
    return
  }

  if (!validateUsername()) return
  if (!validateEmail()) return
  if (!validateCode()) return
  if (!validatePassword()) return
  if (!validateRePassword()) return

  try {
    await http.register({
      username: form.username,
      email: form.email,
      code: form.code,
      password: form.password,
      confirm_password: form.rePassword
    })
    uni.showToast({ title: '注册成功', icon: 'success' })
    setTimeout(() => uni.redirectTo({ url: '/pages/login' }), 1500)
  } catch (e) {
    // -------------- 核心修复：读取后端返回的 detail ----------
    let msg = "注册失败";

    // 1. 优先取后端返回的错误详情（FastAPI 标准格式）
    if (e?.data?.detail) {
      msg = e.data.detail;
    } 
    // 2. 兼容其他格式
    else if (e?.message) {
      msg = e.message;
    }

    // 根据后端文字匹配提示
    if (msg === "该邮箱已存在！") {
      uni.showToast({ title: "注册失败，该邮箱已存在！", icon: "none" });
      error.email = true;
    } 
    else if (msg === "验证码错误！") {
      uni.showToast({ title: "注册失败，验证码错误！", icon: "none" });
      error.code = true;
    } 
    else {
      uni.showToast({ title: msg, icon: "none" });
    }
  }
}


const goLogin = () => uni.redirectTo({ url: '/pages/login' })

onUnmounted(() => timer && clearInterval(timer))
</script>

<style scoped>
.page-wrap {
  min-height: 100vh;
  background: linear-gradient(to bottom, #fff6ed, #ffffff);
  padding: 20rpx;
  box-sizing: border-box;
  background: url('@/assets/images/backGround.png') no-repeat center center;
  background-size: cover; /* 这将确保图片覆盖整个区域且不变形 */
}

.header {
  text-align: center;
  margin-bottom: 40rpx;
}

.title {
  font-size: 48rpx;
  color: #820ef5;
  font-weight: bold;
}

.sub-title {
  display: block;
  font-size: 28rpx;
  color: #666;
  margin-top: 10rpx;
}

.card {
  background: #fff;
  border-radius: 16px;
  padding: 30px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  max-width: 400px;
  margin: 0 auto;
}

.form-item {
  margin-bottom: 30rpx;
}

.label {
  display: block;
  font-size: 32rpx;
  color: #333;
  margin-bottom: 12rpx;
}

.input {
  width: 100%;
  height: 88rpx;
  border: 1rpx solid #eee;
  border-radius: 12rpx;
  padding: 0 20rpx;
  font-size: 30rpx;
  box-sizing: border-box;
}

.input.error {
  border-color: #f55027 !important;
  background-color: #fff5f5;
}

.code-item .code-row {
  display: flex;
  align-items: center;
  gap: 20rpx;
}

.code-input {
  flex: 1;
}

.code-btn {
  width: 180rpx;
  height: 88rpx;
  background: #fff;
  color: #f55027;
  border: 1rpx solid #eee;
  border-radius: 12rpx;
  font-size: 28rpx;
}

.code-btn.disabled {
  color: #999;
  background: #f5f5f5;
}

.submit-btn {
  width: 100%;
  height: 96rpx;
  background: linear-gradient(to right, #ff9053, #f55027);
  color: #fff;
  border: none;
  border-radius: 48rpx;
  font-size: 34rpx;
  margin-top: 20rpx;
}

.link-tip {
  text-align: center;
  margin-top: 40rpx;
  font-size: 28rpx;
  color: #666;
}

.link-text {
  color: #f55027;
}
</style>