/**
 * 后端接口契约定义
 * 已对接 Django 后端 (http://127.0.0.1:8000/api/)
 * 通过 Vite proxy 转发 /api -> Django
 */
const BASE_URL = import.meta.env.VITE_API_BASE || '/api'

async function request(method, path, body) {
  const token = localStorage.getItem('sl_token') || ''
  const opts = {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    }
  }
  if (body && method !== 'GET') {
    opts.body = JSON.stringify(body)
  }
  const res = await fetch(`${BASE_URL}${path}`, opts)
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || `请求失败: ${res.status}`)
  return data
}

/* ==========================================================================
 * 鉴权相关
 * ========================================================================== */
export const authApi = {
  /**
   * 登录 POST /api/auth/login
   * @param {string} account
   * @param {string} password
   * @returns {Promise<{token:string, user:{account:string, nickname:string}}>}
   */
  async login(account, password) {
    return request('POST', '/auth/login', { account, password })
  },

  /**
   * 注册 POST /api/auth/register
   */
  async register(account, password) {
    return request('POST', '/auth/register', { account, password })
  },

  /**
   * 退出登录 POST /api/auth/logout
   */
  async logout() {
    return request('POST', '/auth/logout')
  },

  /**
   * 验证 token 是否有效 GET /api/auth/verify
   * @returns {Promise<{valid:boolean, user?:{account:string, nickname:string}}>}
   */
  async verifyToken() {
    return request('GET', '/auth/verify')
  }
}

/* ==========================================================================
 * AI 课堂（杏云同学）
 * ========================================================================== */
export const chatApi = {
  /**
   * 发送消息并获取 DeepSeek AI 回复
   * POST /api/chat/message  { question, history } → { reply }
   */
  async sendMessage(question, history = []) {
    return request('POST', '/chat/message', { question, history })
  },

  /**
   * 从 AI 教学回复中提取手语关键词
   * POST /api/chat/extract-sign  { reply } → { keyword }
   */
  async extractSign(reply) {
    return request('POST', '/chat/extract-sign', { reply })
  },

  /**
   * 语音转文字：上传 WAV 音频 → 返回识别文本
   * POST /api/chat/speech-to-text  (multipart) → { text }
   * @param {Blob} wavBlob WAV 格式的音频 blob
   */
  async speechToText(wavBlob) {
    const token = localStorage.getItem('sl_token') || ''
    const form = new FormData()
    form.append('audio', wavBlob, 'audio.wav')
    const res = await fetch(`${BASE_URL}/chat/speech-to-text`, {
      method: 'POST',
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: form
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || '请求失败')
    return data
  }
}

/* ==========================================================================
 * 手语识别与生成（Tab1 实时手语综合）
 * ========================================================================== */
export const signApi = {
  /**
   * 手语转语音：识别视频中的手势并返回文本
   * 支持两种方式：
   *   - 上传 Blob/File: signApi.recognizeSign(blob)
   *   - 数据集路径: signApi.recognizeSign('train-00001.mp4')
   * @param {Blob|File|string} video 视频 blob/文件 或 数据集视频路径
   * @returns {Promise<{text:string, gloss_text:string}>}
   */
  async recognizeSign(video) {
    if (typeof video === 'string') {
      return request('POST', '/sign/recognize', { video_path: video })
    }
    // Blob/File upload via multipart
    const token = localStorage.getItem('sl_token') || ''
    const form = new FormData()
    form.append('video', video, 'recording.webm')
    const res = await fetch(`${BASE_URL}/sign/recognize`, {
      method: 'POST',
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: form
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || '请求失败')
    return data
  },

  /**
   * 语音转手语：将文本转换为手语视频
   * POST /api/sign/generate  { text } → { videoUrl }
   */
  async generateSignVideo(text) {
    return request('POST', '/sign/generate', { text })
  }
}

/* ==========================================================================
 * 视频翻译配音（Tab2）
 * ========================================================================== */
export const videoApi = {
  /**
   * 视频翻译：识别上传视频中的手语并返回译文
   * POST /api/video/translate  { video_path } 或 multipart
   * @param {File|string} video 视频文件或视频路径
   * @returns {Promise<{translation:string}>}
   */
  async translateVideo(video) {
    if (typeof video === 'string') {
      return request('POST', '/video/translate', { video_path: video })
    }
    // File upload via multipart
    const token = localStorage.getItem('sl_token') || ''
    const form = new FormData()
    form.append('video', video)
    const res = await fetch(`${BASE_URL}/video/translate`, {
      method: 'POST',
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: form
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || '请求失败')
    return data
  },

  /**
   * 合成配音：文本 → TTS 音频
   * POST /api/video/dub  { text, language, voice? }  →  { audio_url, duration }
   */
  async dubVideo(text, language) {
    return request('POST', '/video/dub', { text, language })
  },

  /**
   * 视频翻译（流式）：上传视频 → SSE 进度流 → 最终结果
   * POST /api/video/translate-stream  (multipart)
   * 返回的 reader 产出 { progress, status, type?, translation?, error? }
   * @param {File} video
   * @returns {Promise<ReadableStreamDefaultReader>}
   */
  translateVideoStream(video) {
    const token = localStorage.getItem('sl_token') || ''
    const form = new FormData()
    form.append('video', video)
    return fetch(`${BASE_URL}/video/translate-stream`, {
      method: 'POST',
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: form
    }).then(res => {
      if (!res.ok) throw new Error('请求失败')
      return res.body.getReader()
    })
  }
}

/* ==========================================================================
 * 语音库（已对接后端音色克隆）
 * ========================================================================== */
export const voiceApi = {
  /**
   * 获取系统内置音色列表
   */
  async listSystemVoices() {
    return { voices: ['声音 1', '声音 2', '声音 3'] }
  },

  /**
   * 上传参考音频用于音色克隆
   * POST /api/voice/reference (multipart)
   * @param {string} name 音色名称
   * @param {Blob} audioBlob 录制的音频 WAV Blob
   * @param {string} text 音频对应的文本内容
   */
  async saveCustomVoice(name, audioBlob, text) {
    const token = localStorage.getItem('sl_token') || ''
    const form = new FormData()
    form.append('audio', audioBlob, 'recording.wav')
    form.append('text', text || '')
    form.append('name', name)
    const res = await fetch(`${BASE_URL}/voice/reference`, {
      method: 'POST',
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: form
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || '上传失败')
    return data
  },

  /**
   * 获取已保存的参考音色列表
   * GET /api/voice/references
   */
  async listCustomVoices() {
    return request('GET', '/voice/references')
  },

  /**
   * 删除指定参考音色
   * DELETE /api/voice/references/{name}
   * @param {string[]} names 音色名称数组
   */
  async deleteCustomVoices(names) {
    // 逐个删除
    const results = []
    for (const name of names) {
      try {
        await request('DELETE', `/voice/references/${encodeURIComponent(name)}`)
        results.push({ name, success: true })
      } catch (e) {
        results.push({ name, success: false, error: e.message })
      }
    }
    return { success: true, results }
  },

  /**
   * 使用克隆音色合成配音
   * POST /api/video/dub-v2 { text, language, voice_name }
   * @param {string} text 配音文本
   * @param {string} language 语言
   * @param {string} voiceName 克隆音色名称
   */
  async dubWithClone(text, language, voiceName) {
    return request('POST', '/video/dub-v2', { text, language, voice_name: voiceName })
  }
}

/* ==========================================================================
 * 我的素材（暂未对接后端，保留 Mock）
 * ========================================================================== */
export const materialsApi = {
  async listFolders() { return request('GET', '/materials/folders') },
  async createFolder(name) { return request('POST', '/materials/folders', { name }) },
  async renameFolder(id, name) { return request('PATCH', `/materials/folders/${id}`, { name }) },
  async deleteFolders(ids) { return request('DELETE', '/materials/folders', { ids }) },
  async listMaterials(folderId) { return request('GET', `/materials/?folderId=${folderId}`) },
  async createMaterial(folderId, data) { return request('POST', '/materials/', { folder_id: folderId, ...data }) },
  async uploadMaterial(folderId, type, name, file) {
    const token = localStorage.getItem('sl_token') || ''
    const form = new FormData()
    form.append('file', file)
    form.append('name', name || file.name)
    form.append('type', type || 'file')
    form.append('folder_id', folderId)
    const res = await fetch(`${BASE_URL}/materials/upload`, {
      method: 'POST',
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: form
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || '上传失败')
    return data
  },
  async renameMaterial(materialId, name) { return request('PATCH', `/materials/${materialId}`, { name }) },
  async updateMaterialContent(materialId, content) { return request('PATCH', `/materials/${materialId}`, { content }) },
  async deleteMaterials(ids) { return request('DELETE', '/materials/', { ids }) },
  async moveMaterials(ids, toFolderId) { return request('POST', '/materials/move', { ids, to_folder_id: toFolderId }) }
}

/* ==========================================================================
 * 账号与用户
 * ========================================================================== */
export const userApi = {
  /**
   * 获取用户资料 GET /api/user/profile
   */
  async getProfile() {
    return request('GET', '/user/profile')
  },

  /**
   * 更新用户资料 PUT /api/user/profile
   * @param {string} nickname
   */
  async updateProfile(nickname) {
    return request('PUT', '/user/profile', { nickname })
  },

  /**
   * 修改密码 PUT /api/user/password  { oldPwd, newPwd }
   */
  async changePassword(oldPwd, newPwd) {
    return request('PUT', '/user/password', { oldPwd, newPwd })
  },

  /**
   * 注销账号 DELETE /api/user/account
   */
  async deleteAccount() {
    return request('DELETE', '/user/account')
  }
}

/* ==========================================================================
 * 手语斩（背词模块）
 * ========================================================================== */
export const vocabApi = {
  /**
   * 手语词库列表 GET /api/vocab/list → { words: [...] }
   */
  async list() {
    return request('GET', '/vocab/list')
  },

  /**
   * 单个词详情 GET /api/vocab/{id}/
   */
  async get(id) {
    return request('GET', `/vocab/${id}/`)
  },

  /**
   * 首次生成该词的手语视频 + 文字说明（服务端缓存）
   * POST /api/vocab/{id}/generate → { id, word, pinyin, video_url, description, generated }
   */
  async generate(id) {
    return request('POST', `/vocab/${id}/generate`)
  },

  /**
   * 批量预加载：后台裁剪下一批单词语视频
   * POST /api/vocab/preload  { limit } → { running, done }
   */
  async preload(limit = 80) {
    return request('POST', '/vocab/preload', { limit })
  },

  /**
   * 查询批量预加载状态
   * GET /api/vocab/preload-state → { running, done, limit, error }
   */
  async preloadStatus() {
    return request('GET', '/vocab/preload-state')
  }
}


export const recordsApi = {
  async list(page = 1, pageSize = 20) {
    return request('GET', `/records/?page=${page}&page_size=${pageSize}`)
  },
  async remove(id) {
    const token = localStorage.getItem('sl_token') || ''
    const res = await fetch(`${BASE_URL}/records/${encodeURIComponent(id)}/`, { method: 'DELETE', headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) } })
    const d = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(d.error || '删除失败')
    return true
  }
}