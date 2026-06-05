<template>
  <div class="kb-page">
    <div class="kb-header">
      <h2>我的知识库</h2>
      <el-button type="primary" @click="handleUpload">上传文件</el-button>
    </div>
    <p class="kb-tip">支持 txt、pdf、doc、docx、xls、xlsx、csv</p>

    <div class="pagination-box" v-if="docList.length > 0">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="docList.length"
        :page-sizes="[5, 10, 20, 50]"
        layout="total, sizes, prev, pager, next, jumper"
        background
      />
    </div>

    <div v-if="uploading" class="kb-loading">上传中...</div>

    <el-table
      :data="pagedList"
      border
      style="width: 100%; max-width: 1200px; margin: 0 auto;"
      :header-cell-style="{ background: '#1ab5e0', color: '#fff' }"
    >
      <el-table-column label="文件名" min-width="160" align="center">
        <template #default="{ row }">
          <el-input
            v-if="renamingId === row.id"
            v-model="renameText"
            size="small"
            @blur="commitRename(row)"
            @keyup.enter="commitRename(row)"
          />
          <span v-else>{{ displayName(row.filename) }}</span>
        </template>
      </el-table-column>

      <el-table-column prop="file_type" label="类型" width="80" align="center" />
      <el-table-column label="大小" width="100" align="center">
        <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
      </el-table-column>
      <el-table-column label="上传时间" width="180" align="center">
        <template #default="{ row }">{{ formatTime(row.create_time) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200" align="center">
        <template #default="{ row }">
          <el-button size="small" type="success" link @click="previewDoc(row)">预览</el-button>
          <el-button size="small" type="primary" link @click="startRename(row)">重命名</el-button>
          <el-popconfirm title="确定删除？" @confirm="doDelete(row)">
            <template #reference>
              <el-button size="small" type="danger" link>删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="!uploading && docList.length === 0" class="kb-empty">
      还没有上传任何文档
    </div>

    <!-- 预览弹窗 -->
    <el-dialog v-model="previewVisible" :title="previewTitle" width="80%" top="2vh">
      <div v-if="previewLoading" class="kb-loading">加载中...</div>
      <div v-else-if="previewType === 'text'" class="preview-text">{{ previewContent }}</div>
      <div v-else class="preview-tip">{{ previewMsg }}</div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const BASE_URL = 'http://127.0.0.1:8000'
const docList = ref([])
const uploading = ref(false)
const renamingId = ref(null)
const renameText = ref('')

// 预览
const previewVisible = ref(false)
const previewLoading = ref(false)
const previewTitle = ref('')
const previewType = ref('')
const previewContent = ref('')
const previewMsg = ref('')

const pageSize = ref(10)
const currentPage = ref(1)

const token = uni.getStorageSync('token')
const authHeader = { Authorization: `Bearer ${token}` }

const pagedList = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return docList.value.slice(start, start + pageSize.value)
})

const displayName = (filename) => {
  if (!filename) return ''
  const lastDotIndex = filename.lastIndexOf('.')
  return lastDotIndex > 0 ? filename.slice(0, lastDotIndex) : filename
}

const formatSize = (b) =>
  b
    ? b < 1048576
      ? (b / 1024).toFixed(1) + 'KB'
      : (b / 1048576).toFixed(1) + 'MB'
    : '0B'

const formatTime = (t) => (t ? new Date(t).toLocaleString() : '')

const loadDocuments = async () => {
  try {
    const res = await fetch(`${BASE_URL}/kb/documents`, {
      headers: { 'Content-Type': 'application/json', ...authHeader },
    })
    if (res.ok) docList.value = await res.json()
  } catch {}
}

const doUpload = async (file) => {
  uploading.value = true
  try {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`${BASE_URL}/kb/upload`, {
      method: 'POST',
      headers: authHeader,
      body: form,
    })
    if (res.ok) {
      ElMessage.success('上传成功')
      loadDocuments()
    } else {
      ElMessage.error('上传失败！')
    }
  } catch {
    ElMessage.error('上传失败！')
  } finally {
    uploading.value = false
  }
}

const previewDoc = async (row) => {
  previewVisible.value = true
  previewTitle.value = row.filename
  previewLoading.value = true
  previewContent.value = ''
  previewMsg.value = ''
  try {
    const res = await fetch(`${BASE_URL}/kb/documents/${row.id}/preview`, {
      headers: { 'Content-Type': 'application/json', ...authHeader },
    })
    const data = await res.json()
    if (data.preview) {
      previewType.value = 'text'
      previewContent.value = data.content
    } else {
      previewType.value = 'tip'
      previewMsg.value = data.message || '不支持预览'
    }
  } catch {
    previewType.value = 'tip'
    previewMsg.value = '加载失败'
  } finally {
    previewLoading.value = false
  }
}

const handleUpload = () => {
  // #ifdef H5
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.txt,.pdf,.doc,.docx,.xls,.xlsx,.csv'
  input.onchange = (e) => {
    const f = e.target.files?.[0]
    if (f) doUpload(f)
  }
  input.click()
  // #endif
  // #ifndef H5
  uni.chooseFile({
    count: 1,
    extension: ['.txt','.pdf','.doc','.docx','.xls','.xlsx','.csv'],
    success: (r) => doUpload(r.tempFiles[0]),
  })
  // #endif
}

const startRename = (row) => {
  renamingId.value = row.id
  renameText.value = displayName(row.filename)
}

const commitRename = async (row) => {
  const name = renameText.value.trim()
  renamingId.value = null
  if (!name || name === displayName(row.filename)) return
  try {
    const res = await fetch(`${BASE_URL}/kb/documents/${row.id}/rename`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...authHeader },
      body: JSON.stringify({ filename: name }),
    })
    if (res.ok) {
      row.filename = name
      ElMessage.success('重命名成功')
    } else {
      ElMessage.error('重命名失败')
    }
  } catch {
    ElMessage.error('重命名失败')
  }
}

const doDelete = async (row) => {
  try {
    const res = await fetch(`${BASE_URL}/kb/documents/${row.id}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json', ...authHeader },
    })
    if (res.ok) {
      ElMessage.success('删除成功')
      loadDocuments()
    }
  } catch {
    ElMessage.error('删除失败')
  }
}

onMounted(() => loadDocuments())
</script>

<style scoped>
.kb-page {
  height: 100vh;
  padding: 28px 32px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.kb-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.kb-header h2 {
  margin: 0;
  font-size: 20px;
}

.kb-tip {
  color: #999;
  font-size: 13px;
}

.pagination-box {
  display: flex;
  justify-content: center;
  margin-bottom: 10px;
}

.kb-loading {
  color: #409eff;
  font-size: 14px;
}

.kb-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
  font-size: 15px;
}

.preview-text {
  white-space: pre-wrap;
  font-family: Consolas, monospace;
  font-size: 14px;
  line-height: 1.7;
  max-height: 70vh;
  overflow-y: auto;
  background: #f8f9fa;
  padding: 16px;
  border-radius: 6px;
}

.preview-tip {
  color: #999;
  font-size: 15px;
  text-align: center;
  padding: 40px 0;
}


:deep(.el-table__body-wrapper .el-table__row) {
  background-color: #cbebff;
}


:deep(.el-table) {
  --el-table-row-height: 52px !important;
}

:deep(.el-table td) {
  padding: 12px 0;
}
</style>