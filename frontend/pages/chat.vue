<template>
  <div class="ai-practice-container">
    <!-- 左侧历史对话记录 -->
    <div :class="['history-panel', { collapsed: sidebarCollapsed }]">
      <template v-if="!sidebarCollapsed">
        <div class="new-chat-container">
          <button class="new-chat-btn" @click="newConversation">
            新建对话
            <el-icon class="plus-icon"><Plus/></el-icon>
          </button>
        </div>
        <ul class="history-list">
          <li v-for="(item, index) in historyList" :key="item.id ?? 'new'"
              :class="{ active: currentConversationIndex === index }"
              @click="selectConversation(index)"
              @mouseenter="hoveredIdx = index"
              @mouseleave="hoveredIdx = -1">

            <!-- 重命名模式 -->
            <el-input
                v-if="renamingIdx === index"
                v-model="renameText"
                size="small"
                @blur="commitRename(index)"
                @keyup.enter="commitRename(index)"
                @click.stop
            />

            <!-- 普通模式 -->
            <span v-else class="session-title">{{ item.title }}</span>

            <!-- "···" Popover，hover 或已打开时才显示 -->
            <el-popover
                v-if="(hoveredIdx === index || menuOpenIdx === index) && item.id !== null"
                placement="bottom"
                :width="120"
                trigger="click"
                @show="menuOpenIdx = index"
                @hide="menuOpenIdx = -1"
                @click.stop
            >
              <template #reference>
                <span class="more-btn">···</span>
              </template>
              <div class="pop-menu">
                <div class="pop-item" @click.stop="startRename(index)">重命名</div>

                <!-- 删除：嵌套 Popover 二次确认 -->
                <el-popover
                    :visible="deletePopIdx === index"
                    placement="top"
                    :width="200"
                    @click.stop
                >
                  <template #reference>
                    <div class="pop-item danger" @click.stop="deletePopIdx = index">删除</div>
                  </template>
                  <p>确定要删除该会话吗？</p>
                  <div style="text-align: right; margin-top: 12px">
                    <el-button size="small" text @click="deletePopIdx = -1">取消</el-button>
                    <el-button size="small" type="danger" @click="confirmDelete(index)">确认</el-button>
                  </div>
                </el-popover>
              </div>
            </el-popover>
          </li>
        </ul>
      </template>
    </div>

    <!-- 右侧对话页面 -->
    <div class="chat-wrapper">
      <div class="chat-panel">
        <!-- 上半部分聊天界面 -->
        <div class="chat-messages" ref="chatMessagesRef">
          <div v-for="(message, index) in currentConversation.messages" :key="index" :class="['message', message.role]">
            <div class="avatar">
              <div v-if="message.role !== 'user'" class="ai-avatar">
                <img src="@/assets/images/agent.png" alt="AI Avatar">
              </div>
              <div v-else>
                <img :src="userAvatar" alt="Me">
              </div>
            </div>
            <div class="content">
              <!-- 思考中：工具调用阶段 -->
              <div v-if="message.loading && !message.content" class="thinking-indicator">
                <span class="thinking-text">思考中</span>
                <span class="thinking-dots"><i></i><i></i><i></i></span>
              </div>
              <!-- 流式回答 -->
              <div v-if="message.content" class="markdown-body" v-html="renderMarkdown(message.content)"></div>
              <!-- 回答完成后显示 loading dots（持续流式写入中） -->
              <span v-if="message.loading && message.content" class="continuing-dot">●</span>
            </div>
          </div>
        </div>

        <!-- 输入框 -->
        <div class="input-area">
          <div class="input-wrapper">
            <el-icon class="input-icon link-icon" @click="handleUpload">
              <Link/>
            </el-icon>
            <input
                v-model="userInput"
                @keydown.enter.prevent="sendMessage"
                placeholder="输入消息，按回车发送..."
                type="text"
                :disabled="isInputDisabled"
            >
            <div class="button-group">
              <div class="audio-wave" v-if="isRecording" @click="finishRecording">
                <span v-for="n in 4" :key="n" :style="{ animationDelay: `${n * 0.2}s` }"></span>
              </div>
              <el-icon v-else class="input-icon microphone-icon" @click="toggleRecording">
                <Microphone/>
              </el-icon>
              <div class="separator"></div>
              <el-popover
                  placement="top"
                  :width="200"
                  trigger="hover"
                  :disabled="!!userInput.trim()"
              >
                <template #reference>
                  <el-button
                      class="send-button"
                      circle
                      @click="sendMessage"
                      :disabled="!userInput.trim()"
                  >
                    <el-icon>
                      <Top/>
                    </el-icon>
                  </el-button>
                </template>
                <span>请文字/录音/上传语音回复</span>
              </el-popover>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onUnmounted, inject } from 'vue'
import { ElMessage } from 'element-plus'
import { Link, Microphone, Plus, Top } from '@element-plus/icons-vue'
import { marked } from 'marked'
// 配置 marked
marked.setOptions({ breaks: true, gfm: true })

const renderMarkdown = (text) => {
  if (!text) return ''
  return marked.parse(text)
}

const BASE_URL = 'http://127.0.0.1:8000'

const userInput = ref('')
const currentConversationIndex = ref(-1)
const currentConversation = ref({ id: null, title: '', messages: [] })
const isAgentTyping = ref(false)
const chatMessagesRef = ref(null)
const historyList = ref([])
const hoveredIdx = ref(-1)     // 当前 hover 的会话索引
const renamingIdx = ref(-1)    // 正在重命名的会话索引
const renameText = ref('')     // 重命名输入框文本
const sidebarCollapsed = inject('sidebarCollapsed', ref(false))
const deletePopIdx = ref(-1)         // 删除确认 popover 索引
const menuOpenIdx = ref(-1)          // 当前打开的 "···" 菜单索引
const userAvatar = ref('/assets/images/user.png')     // 用户头像，默认图

// 录音相关
const isRecording = ref(false)
const isInputDisabled = ref(false)
const mediaStream = ref(null)
let mediaRecorder = null
let audioChunks = []

// ===================== API 工具函数 =====================
const apiHeaders = () => ({
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${localStorage.getItem('token')}`
})

const handleApiError = (err) => {
  const detail = err.detail || err.message || '请求失败'
  if (err.status === 403 || err.status === 401) {
    uni.removeStorageSync('token')
    ElMessage.error('登录已过期，请重新登录')
    setTimeout(() => uni.redirectTo({ url: '/pages/login' }), 500)
    return
  }
  ElMessage.error(detail)
}

// ===================== 滚动到底部 =====================
const scrollToBottom = () => {
  const el = chatMessagesRef.value
  if (el) el.scrollTop = el.scrollHeight
}

// ===================== 加载会话列表 =====================
const loadSessionList = async () => {
  try {
    const res = await fetch(`${BASE_URL}/agent/sessions`, { headers: apiHeaders() })
    if (!res.ok) throw { status: res.status, detail: (await res.json().catch(() => ({}))).detail }
    historyList.value = await res.json()
    // 默认选中最近一个会话
    if (historyList.value.length > 0) {
      selectConversation(0)
    } else {
      // 没有任何历史会话，新建一个空的
      newConversation()
    }
  } catch (err) {
    handleApiError(err)
  }
}

// ===================== 选中会话（加载消息） =====================
const selectConversation = async (index) => {
  currentConversationIndex.value = index
  const session = historyList.value[index]

  // 新建但未保存的会话（id=null），直接加载空消息
  if (session.id === null) {
    currentConversation.value = { id: null, title: '新对话', messages: [] }
    await nextTick(scrollToBottom)
    return
  }

  try {
    const res = await fetch(`${BASE_URL}/agent/sessions/${session.id}`, { headers: apiHeaders() })
    if (!res.ok) throw { status: res.status, detail: (await res.json().catch(() => ({}))).detail }
    const messages = await res.json()

    currentConversation.value = {
      id: session.id,
      title: session.title,
      messages: messages.map(m => ({ role: m.role, content: m.content }))
    }
  } catch (err) {
    handleApiError(err)
    currentConversation.value = { id: session.id, title: session.title, messages: [] }
  }
  await nextTick(scrollToBottom)
}

// ===================== 新建对话 =====================
const newConversation = () => {
  // 如果已存在空会话，直接切换到它
  const existing = historyList.value.findIndex(h => h.id === null)
  if (existing >= 0) {
    currentConversationIndex.value = existing
    currentConversation.value = { id: null, title: '新对话', messages: [] }
    nextTick(scrollToBottom)
    return
  }
  currentConversation.value = { id: null, title: '新对话', messages: [] }
  historyList.value.unshift({
    id: null, title: '新对话', update_time: new Date().toISOString()
  })
  currentConversationIndex.value = 0
  nextTick(scrollToBottom)
}

// ===================== 发送消息 =====================
const sendMessage = async () => {
  const prompt = userInput.value.trim()
  if (!prompt || isAgentTyping.value) return

  // 推入用户消息
  currentConversation.value.messages.push({ role: 'user', content: prompt })
  userInput.value = ''
  await nextTick(scrollToBottom)

  // AI 占位
  const assistantMsg = { role: 'assistant', content: '', loading: true }
  currentConversation.value.messages.push(assistantMsg)
  const msgIndex = currentConversation.value.messages.length - 1
  isAgentTyping.value = true
  await nextTick(scrollToBottom)

  try {
    // 构造请求体（有 session_id 则带过去）
    const body = { query: prompt }
    if (currentConversation.value.id) {
      body.session_id = currentConversation.value.id
    }

    const response = await fetch(`${BASE_URL}/agent/chat`, {
      method: 'POST',
      headers: apiHeaders(),
      body: JSON.stringify(body)
    })

    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || `HTTP ${response.status}`)
    }

    // ---- SSE 流式读取 ----
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const payload = line.slice(6)
        if (payload === '[DONE]') continue

        try {
          const data = JSON.parse(payload)

          // 新会话
          if (data.session_id) {
            currentConversation.value.id = data.session_id
            const title = prompt.length > 10 ? prompt.slice(0, 10) + '...' : prompt
            currentConversation.value.title = title
            const idx = historyList.value.findIndex(h => h.id === null)
            if (idx >= 0) {
              historyList.value[idx].id = data.session_id
              historyList.value[idx].title = title
            } else {
              historyList.value.unshift({ id: data.session_id, title, update_time: new Date().toISOString() })
            }
            currentConversationIndex.value = historyList.value.findIndex(h => h.id === data.session_id)
            continue
          }

          // 清除试流内容（工具间过渡文本回撤）
          if (data.type === 'clear') {
            const m = currentConversation.value.messages[msgIndex]
            m.content = ''
            m.loading = true
            await nextTick(scrollToBottom)
            continue
          }

          // 工具调用：显示加载动画
          if (data.type === 'tool') {
            const m = currentConversation.value.messages[msgIndex]
            m.loading = true
            await nextTick(scrollToBottom)
            continue
          }

          // 错误：后端返回错误信息
          if (data.type === 'error') {
            const m = currentConversation.value.messages[msgIndex]
            m.content = data.data || '请求失败，请稍后重试'
            m.loading = false
            await nextTick(scrollToBottom)
            continue
          }

          // 正式回答：流式展示
          if (data.type === 'content') {
            const m = currentConversation.value.messages[msgIndex]
            m.content += data.data
            m.loading = false
            await nextTick(scrollToBottom)
          }
        } catch { /* skip */ }
      }
    }

    // 流结束
    const finalMsg = currentConversation.value.messages[msgIndex]
    finalMsg.loading = false
    // 兜底：流结束但无内容 → 说明 LLM 调用失败
    if (!finalMsg.content) {
      finalMsg.content = '模型暂时无法响应，请稍后重试'
    }
  } catch (error) {
    currentConversation.value.messages[msgIndex].content = '请求失败，请稍后重试'
    console.error('sendMessage error:', error)
    ElMessage.error('请求失败：' + (error.message || '请检查后端是否启动'))
  } finally {
    isAgentTyping.value = false
    await nextTick(scrollToBottom)
  }
}

// ===================== 上传文件到知识库 =====================
const handleUpload = () => {
  const token = uni.getStorageSync('token')
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.txt,.pdf,.doc,.docx,.xls,.xlsx,.csv'
  input.onchange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    try {
      const res = await fetch(`${BASE_URL}/kb/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form
      })
      if (res.ok) {
        ElMessage.success('文件已上传至知识库')
      } else {
        ElMessage.error('上传失败！')
      }
    } catch {
      ElMessage.error('上传失败')
    }
  }
  input.click()
}

// ===================== 重命名 =====================
const startRename = (index) => {
  renamingIdx.value = index
  renameText.value = historyList.value[index].title
  nextTick(() => {
    const el = document.querySelector('.rename-input')
    if (el) el.focus()
  })
}

const commitRename = async (index) => {
  const newTitle = renameText.value.trim()
  renamingIdx.value = -1

  if (!newTitle || newTitle === historyList.value[index].title) return

  const session = historyList.value[index]
  try {
    await fetch(`${BASE_URL}/agent/sessions/${session.id}/rename`, {
      method: 'PUT',
      headers: apiHeaders(),
      body: JSON.stringify({ title: newTitle })
    })
    historyList.value[index].title = newTitle
    if (currentConversation.value.id === session.id) {
      currentConversation.value.title = newTitle
    }
  } catch (err) {
    ElMessage.error('重命名失败')
  }
}

// ===================== 删除会话 =====================
const confirmDelete = async (index) => {
  deletePopIdx.value = -1  // 关闭确认 popover
  await doDelete(index)
}

const doDelete = async (index) => {
  const session = historyList.value[index]
  try {
    await fetch(`${BASE_URL}/agent/sessions/${session.id}`, {
      method: 'DELETE',
      headers: apiHeaders()
    })
    historyList.value.splice(index, 1)
    // 如果删除的是当前会话，切换到最近一个或新建
    if (currentConversation.value.id === session.id) {
      if (historyList.value.length > 0) {
        selectConversation(0)
      } else {
        newConversation()
      }
    } else if (currentConversationIndex.value > index) {
      currentConversationIndex.value--
    }
    ElMessage.success('已删除')
  } catch (err) {
    ElMessage.error('删除失败')
  }
}

// ===================== 录音相关 =====================
const finishRecording = () => {
  if (isRecording.value && mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop()
    isRecording.value = false
    isInputDisabled.value = false
  }
}
const sendAudioMessage = (audioBlob) => { /* ... */ }
const toggleRecording = () => { ElMessage.info('录音功能待实现') }
const stopMediaStream = () => {
  if (mediaStream.value) {
    mediaStream.value.getTracks().forEach(t => t.stop())
    mediaStream.value = null
  }
}

// ===================== 生命周期 =====================
onMounted(async () => {
  const token = uni.getStorageSync('token')
  if (!token) {
    uni.redirectTo({ url: '/pages/login' })
    return
  }
  // 加载用户头像
  try {
    const res = await fetch(`${BASE_URL}/user/profile`, {
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }
    })
    if (res.ok) {
      const profile = await res.json()
      if (profile.avatar) userAvatar.value = profile.avatar
    }
  } catch { /* use default */ }
  loadSessionList()
})
onUnmounted(() => {
  finishRecording()
  stopMediaStream()
})
</script>

<style scoped>
.ai-practice-container {
  display: flex;
  height: 100vh;
  font-family: Arial, sans-serif;
}

.history-panel {
  width: 280px;
  background: linear-gradient(135deg, rgba(230, 240, 255, 0.01), rgba(240, 230, 255, 0.01));
  background-color: #ffffff;
  padding: 20px;
  overflow-y: auto;
  position: relative;
  transition: width 0.3s ease;
  flex-shrink: 0;
}

.history-panel.collapsed {
  width: 50px;
  padding: 20px 10px;
  overflow: hidden;
}

.new-chat-container {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
}

.new-chat-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  padding: 13px; /* 略微增加内边距 */
  margin-top: 10px;
  margin-bottom: 5px;
  background: linear-gradient(to right, #0069e0, #0052bc); /* 改用更深的蓝色渐变 */
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: opacity 0.3s;
  font-size: 14px; /* 加大字号 */
  font-weight: bold; /* 加粗字体 */
}

.new-chat-btn:hover {
  opacity: 0.9;
}

.history-list {
  list-style-type: none;
  padding: 0;
}

.history-list li {
  padding: 10px;
  margin-bottom: 10px;
  background-color: #ffffff;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.3s;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: relative;
}

.history-list li:hover,
.history-list li.active {
  background-color: rgba(0, 105, 224, 0.15);
  color: #0052bc;
}

.session-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.more-btn {
  color: #999;
  font-size: 16px;
  cursor: pointer;
  letter-spacing: 2px;
  line-height: 1;
  padding: 0 4px;
}

.more-btn:hover {
  color: #0069e0;
}

.pop-menu .pop-item {
  padding: 8px 12px;
  cursor: pointer;
  border-radius: 4px;
  font-size: 14px;
}

.pop-menu .pop-item:hover {
  background-color: #f0f0f0;
}

.pop-menu .pop-item.danger {
  color: #f56c6c;
}

.pop-menu .pop-item.danger:hover {
  background-color: #fef0f0;
}

.chat-wrapper {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  background: linear-gradient(135deg,
  rgba(0, 105, 224, 0.08),
  rgba(0, 56, 148, 0.08)
  );
}

.chat-panel {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: transparent;
  box-shadow: none;
  padding-top: 12px; /* 添加顶部内边距 */
  /* padding-left: 10%;
  padding-right: 10%; */
}

.visitor-info {
  background-color: transparent; /* 背透明 */
  padding: 15px 20px; /* 增加内边距 */
  margin-bottom: 20px; /* 增加与第一条对话的距离 */
  font-weight: bold;
  color: #333;
  text-align: left;
  font-size: 18px; /* 增大字体大小 */
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding-top: 20px;
  padding-left: 10%;
  padding-right: 10%;
  background-color: transparent;
  /* 修改滚动条颜色 */
  scrollbar-width: thin;
  scrollbar-color: rgba(0, 105, 224, 0.3) transparent;
}

/* 为 Webkit 浏览器（如 Chrome、Safari）自定义滚动条样式 */
.chat-messages::-webkit-scrollbar {
  width: 6px;
}

.chat-messages::-webkit-scrollbar-track {
  background: transparent;
}

.chat-messages::-webkit-scrollbar-thumb {
  background-color: rgba(0, 105, 224, 0.3);
  border-radius: 3px;
}

.message {
  display: flex;
  margin-bottom: 20px;
}

.message .avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background-color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 10px;
  overflow: hidden;
}

.message .avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 50%;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #ffffff;
}

.message .content {
  background-color: rgba(255, 255, 255, 1);
  padding: 12px 18px; /* 增加内边距 */
  border-radius: 10px;
  max-width: 80%;
  font-size: 16px; /* 增加字体大小 */
  line-height: 1.8; /* 增加行高 */
  user-select: text;
  cursor: auto;
}

.message.user {
  flex-direction: row-reverse;
}

.message.user .avatar {
  margin-right: 0;
  margin-left: 10px;
}

.message.user .content {
  background-color: rgba(0, 105, 224, 0.12);
  color: black;
}

.input-area {
  padding: 20px 10% 0 10%;
  border-top: 0px solid #e0e0e0;
  background-color: transparent;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

input {
  width: 100%;
  padding: 12px 110px 12px 50px; /* 调整右侧padding以适应新的按钮组 */
  border: 1px solid rgba(204, 204, 204, 0.5);
  border-radius: 25px;
  font-size: 16px;
  background-color: rgba(255, 255, 255, 0.7);
  transition: border-color 0.3s;
  height: 55px;
}

input:focus {
  outline: none;
  border-color: #0069e0;
}

input::placeholder {
  color: #969696;
}

.button-group {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
}

.input-icon {
  color: #0069e0;
  font-size: 24px;
  cursor: pointer;
}

.link-icon {
  position: absolute;
  left: 18px;
  top: 50%;
  transform: translateY(-50%);
}

.microphone-icon {
  margin-right: 0; /* 将右侧边距改为0 */
}

.separator {
  width: 1px;
  height: 25px;
  background-color: rgba(204, 204, 204, 0.5);
  margin: 0 10px;
}

.send-button {
  width: 40px;
  height: 40px;
  background: linear-gradient(to right, #0069e0, #0052bc); /* 保持一致的蓝色渐变 */
  border: none;
  color: white;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.send-button:disabled {
  background: rgba(0, 105, 224, 0.1);
  color: rgba(0, 82, 188, 0.3);
  cursor: default;
}

.send-button :deep(.el-icon) {
  font-size: 24px;
}

.send-button:not(:disabled):hover {
  opacity: 0.9;
}

/* 新增的免责声明样式 */
.disclaimer {
  font-size: 10px;
  color: #999;
  text-align: center;
  margin-top: 12px;
  margin-bottom: 12px;
}

.audio-wave {
  display: flex;
  align-items: center;
  height: 24px;
  width: 24px;
}

.audio-wave span {
  display: inline-block;
  width: 3px;
  height: 100%;
  margin-right: 1px;
  background: #0069e0;
  animation: audio-wave 0.8s infinite ease-in-out;
}

@keyframes audio-wave {
  0%, 100% {
    transform: scaleY(0.3);
  }
  50% {
    transform: scaleY(1);
  }
}

.message .content audio {
  margin-top: 10px;
  width: 100%;
}

/* 思考中加载动画 */
.thinking-indicator {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 0;
  color: #888;
  font-size: 15px;
}
.thinking-text {
  font-weight: 500;
}
.thinking-dots {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.thinking-dots i {
  width: 5px;
  height: 5px;
  background: #0069e0;
  border-radius: 50%;
  animation: dot-pulse 1.2s infinite ease-in-out;
}
.thinking-dots i:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots i:nth-child(3) { animation-delay: 0.4s; }
@keyframes dot-pulse { 0%,60%,100% { transform: scale(0.6); opacity: 0.4; } 30% { transform: scale(1); opacity: 1; } }

/* 流式输出中的闪烁光标 */
.continuing-dot {
  color: #0069e0;
  font-size: 18px;
  animation: blink 0.8s infinite;
  margin-left: 2px;
}
@keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0; } }

/* Markdown 渲染样式 */
.markdown-body :deep(p) { margin: 0 0 8px; line-height: 1.7; }
.markdown-body :deep(h3) { margin: 12px 0 6px; font-size: 16px; }
.markdown-body :deep(strong) { font-weight: bold; }
.markdown-body :deep(blockquote) { border-left: 3px solid #0069e0; padding-left: 12px; color: #666; margin: 8px 0; }
.markdown-body :deep(code) { background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-size: 13px; }
.markdown-body :deep(a) { color: #0069e0; text-decoration: underline; }
.markdown-body :deep(ul), .markdown-body :deep(ol) { padding-left: 20px; margin: 8px 0; }
.markdown-body :deep(li) { margin-bottom: 4px; }
</style>