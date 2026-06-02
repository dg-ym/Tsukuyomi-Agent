import axios from 'axios'
import { BASE_URL } from '../http/http.js'
// axios实例
const service = axios.create({
  baseURL: BASE_URL,
  timeout: 15000, 
})

// 请求拦截器
service.interceptors.request.use(
  config => {
    // 加通用请求头
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
// 跨域问题后端处理
service.interceptors.response.use(
  response => {
    return response.data
  },
  error => {
    console.error('请求错误：', error)
    return Promise.reject(error)
  }
)

export const get = (url, params) => {
  return service({
    url,
    method: 'get',
    params
  })
}

export const post = (url, data) => {
  return service({
    url,
    method: 'post',
    data
  })
} 

import { ElMessage } from 'element-plus'

const BASE_URL = 'http://127.0.0.1:8000'

async function request(url, options = {}) {
  const token = localStorage.getItem('token')

  const res = await fetch(`${BASE_URL}${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })

  if (res.status === 401 || res.status === 403) {
    localStorage.removeItem('token')
    ElMessage.error('登录已过期，请重新登录')
    // 用 window.location 跳转，无需依赖 router
    window.location.href = '/login'
    throw new Error('未登录')
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw { status: res.status, detail: err.detail || err.message }
  }

  return res
}

// SSE 流式请求（chat 专用）
async function streamRequest(url, body) {
  return request(url, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export { request, streamRequest }
