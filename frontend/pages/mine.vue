<template>
  <div class="mine-page">
    <h2>个人中心</h2>

    <!-- 头像 -->
    <div class="avatar-section">
      <img :src="avatarUrl" class="avatar" @click="pickAvatar" />
      <p class="avatar-hint">点击头像更换</p>
    </div>

    <!-- 用户名 -->
    <el-form label-width="80px" class="profile-form">
      <el-form-item label="邮箱">
        <el-input :model-value="profile.email" disabled />
      </el-form-item>
      <el-form-item label="用户名">
        <el-input v-model="editUsername" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="saveProfile" :loading="saving">保存信息</el-button>
      </el-form-item>
    </el-form>

    <!-- 修改密码 -->
    <el-divider />
    <h3>修改密码</h3>
    <el-form label-width="80px" class="profile-form" :model="pwdForm">
      <el-form-item label="原密码">
        <el-input v-model="pwdForm.old_password" type="password" show-password />
      </el-form-item>
      <el-form-item label="新密码">
        <el-input v-model="pwdForm.new_password" type="password" show-password />
      </el-form-item>
      <el-form-item label="确认密码">
        <el-input v-model="pwdForm.confirm_password" type="password" show-password />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="changePwd" :loading="savingPwd">修改密码</el-button>
      </el-form-item>
    </el-form>

    <el-divider />
    <div class="danger-zone">
      <el-button type="danger" plain @click="handleDeleteAccount">注销账号</el-button>
      <p class="danger-hint">该操作不可逆，将删除您所有数据</p>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const BASE_URL = 'http://127.0.0.1:8000'
const token = uni.getStorageSync('token')
const authHeader = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }

const profile = reactive({ id: 0, email: '', username: '', avatar: '' })
const editUsername = ref('')
const saving = ref(false)
const savingPwd = ref(false)

const pwdForm = reactive({ old_password: '', new_password: '', confirm_password: '' })
const avatarUrl = ref('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="50" fill="%230069e0"/><text x="50" y="65" text-anchor="middle" fill="white" font-size="40">👤</text></svg>')

const loadProfile = async () => {
  try {
    const res = await fetch(`${BASE_URL}/user/profile`, { headers: authHeader })
    if (res.ok) {
      const data = await res.json()
      Object.assign(profile, data)
      editUsername.value = data.username
      if (data.avatar) avatarUrl.value = data.avatar
    }
  } catch { /* ignore */ }
}

const pickAvatar = () => {
  // #ifdef H5
  const input = document.createElement('input')
  input.type = 'file'; input.accept = 'image/*'
  input.onchange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = async (ev) => {
      const base64 = ev.target.result
      avatarUrl.value = base64
      profile.avatar = base64
      await saveProfile()
    }
    reader.readAsDataURL(file)
  }
  input.click()
  // #endif
  // #ifndef H5
  uni.chooseImage({
    count: 1, sizeType: ['compressed'],
    success: (res) => {
      uni.getFileSystemManager().readFile({
        filePath: res.tempFilePaths[0],
        encoding: 'base64',
        success: (fsRes) => {
          const base64 = 'data:image/png;base64,' + fsRes.data
          avatarUrl.value = base64
          profile.avatar = base64
          saveProfile()
        }
      })
    }
  })
  // #endif
}

const saveProfile = async () => {
  saving.value = true
  try {
    const body = { username: editUsername.value }
    if (profile.avatar) body.avatar = profile.avatar
    const res = await fetch(`${BASE_URL}/user/profile`, {
      method: 'PUT', headers: authHeader, body: JSON.stringify(body)
    })
    const data = await res.json()
    if (res.ok) {
      profile.username = data.username
      if (data.avatar) profile.avatar = data.avatar
      ElMessage.success('保存成功')
    } else {
      ElMessage.error(data.detail || '保存失败')
    }
  } catch { ElMessage.error('保存失败') }
  finally { saving.value = false }
}

const changePwd = async () => {
  if (pwdForm.new_password !== pwdForm.confirm_password) {
    ElMessage.warning('两次密码不一致'); return
  }
  if (pwdForm.new_password.length < 6) {
    ElMessage.warning('密码至少6位'); return
  }
  savingPwd.value = true
  try {
    const res = await fetch(`${BASE_URL}/user/password`, {
      method: 'PUT', headers: authHeader, body: JSON.stringify(pwdForm)
    })
    const data = await res.json()
    if (res.ok) {
      ElMessage.success('密码修改成功')
      pwdForm.old_password = ''; pwdForm.new_password = ''; pwdForm.confirm_password = ''
    } else {
      ElMessage.error(data.detail || '修改失败')
    }
  } catch { ElMessage.error('修改失败') }
  finally { savingPwd.value = false }
}

const handleDeleteAccount = () => {
  uni.showModal({
    title: '注销账号',
    content: '该操作不可逆，确定要注销账号吗？\n将删除您的所有数据（会话、知识库、个人资料）',
    success: async (res) => {
      if (!res.confirm) return
      try {
        const resp = await fetch(`${BASE_URL}/user/account`, {
          method: 'DELETE', headers: authHeader
        })
        if (resp.ok) {
          uni.removeStorageSync('token')
          uni.removeStorageSync('user')
          uni.showToast({ title: '账号已注销', icon: 'success' })
          setTimeout(() => uni.redirectTo({ url: '/pages/register' }), 800)
        } else {
          const data = await resp.json()
          ElMessage.error(data.detail || '注销失败')
        }
      } catch { ElMessage.error('注销失败') }
    }
  })
}

onMounted(() => loadProfile())
</script>

<style scoped>
.mine-page { padding: 24px; height: 100vh; overflow-y: auto; box-sizing: border-box; display: flex; flex-direction: column; align-items: center; }
.mine-page h2, .mine-page h3 { align-self: flex-start; margin: 0 0 20px; }
.avatar-section { text-align: center; margin-bottom: 24px; }
.avatar { width: 80px; height: 80px; border-radius: 50%; border: 2px solid #0069e0; cursor: pointer; object-fit: cover; }
.avatar-hint { color: #999; font-size: 12px; margin-top: 6px; }
.profile-form { width: 440px; max-width: 100%; }
.el-divider { width: 440px; max-width: 100%; }
.danger-zone { width: 440px; max-width: 100%; text-align: center; }
.danger-hint { color: #999; font-size: 12px; margin-top: 8px; }
</style>
