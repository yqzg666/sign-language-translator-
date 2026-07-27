import { reactive, computed } from 'vue'

/**
 * 生成唯一 ID
 * @param {string} prefix 前缀
 * @returns {string} 唯一标识
 */
function genId(prefix = 'id') {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`
}

/**
 * 当前时间格式化为 yyyy-MM-dd HH:mm
 * @returns {string} 格式化时间
 */
function nowStr() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/*
 * 素材数据：仅会话内存，未持久化到 localStorage。
 * 原因：图片/视频为 blob URL，无法跨会话存活；文本内容可持久化但为保持一致体验暂存内存。
 * 实际项目应接入后端存储。
 *
 * 后端对接：本 store 中每个方法都有对应的 REST 接口，见 src/api/index.js 的 materialsApi：
 *   addFolder         -> POST   /api/materials/folders
 *   renameFolder      -> PUT    /api/materials/folders/:id
 *   removeFolder(s)   -> DELETE /api/materials/folders
 *   addTextMaterial   -> POST   /api/materials/folders/:id/materials
 *   addMediaMaterial  -> POST   /api/materials/folders/:id/materials/upload
 *   renameMaterial    -> PUT    /api/materials/:id
 *   updateTextMaterial-> PUT    /api/materials/:id/content
 *   removeMaterial(s) -> DELETE /api/materials
 *   moveMaterials     -> POST   /api/materials/move
 */
const state = reactive({
  // folders: [{ id, name, createdAt, materials: [{ id, type, name, content?, url?, createdAt }] }]
  folders: []
})

/**
 * 素材数据 store：文件夹与素材的增删改查、批量删除、批量移动
 */
export function useMaterialsStore() {
  // 文件夹列表
  const folders = computed(() => state.folders)

  /**
   * 根据 ID 获取文件夹
   * @param {string} id 文件夹 ID
   * @returns {Object|null} 文件夹对象
   */
  function getFolder(id) {
    return state.folders.find((f) => f.id === id) || null
  }

  /**
   * 新建文件夹
   * @param {string} name 文件夹名称
   * @returns {Object} 新建的文件夹
   */
  function addFolder(name) {
    const folder = {
      id: genId('f'),
      name: name.trim() || `文件夹 ${state.folders.length + 1}`,
      createdAt: nowStr(),
      materials: []
    }
    state.folders.push(folder)
    return folder
  }

  /**
   * 重命名文件夹
   * @param {string} id 文件夹 ID
   * @param {string} name 新名称
   */
  function renameFolder(id, name) {
    const f = getFolder(id)
    if (f && name.trim()) f.name = name.trim()
  }

  /**
   * 删除单个文件夹
   * @param {string} id 文件夹 ID
   */
  function removeFolder(id) {
    const idx = state.folders.findIndex((f) => f.id === id)
    if (idx >= 0) state.folders.splice(idx, 1)
  }

  /**
   * 批量删除文件夹
   * @param {string[]} ids 文件夹 ID 数组
   */
  function removeFolders(ids) {
    const set = new Set(ids)
    state.folders = state.folders.filter((f) => !set.has(f.id))
  }

  /**
   * 获取指定文件夹内的素材
   * @param {string} folderId 文件夹 ID
   * @param {string} materialId 素材 ID
   * @returns {Object|null} 素材对象
   */
  function getMaterial(folderId, materialId) {
    const f = getFolder(folderId)
    return f ? f.materials.find((m) => m.id === materialId) : null
  }

  /**
   * 新建文本素材
   * @param {string} folderId 文件夹 ID
   * @param {string} name 素材名称
   * @param {string} content 文本内容
   * @returns {Object} 新建的素材
   */
  function addTextMaterial(folderId, name, content = '') {
    const f = getFolder(folderId)
    if (!f) return null
    const m = {
      id: genId('m'),
      type: 'text',
      name: name.trim() || '新建文本',
      content,
      createdAt: nowStr()
    }
    f.materials.push(m)
    return m
  }

  /**
   * 新增图片或视频素材
   * @param {string} folderId 文件夹 ID
   * @param {string} type 'image' | 'video'
   * @param {string} name 素材名称
   * @param {string} url 媒体 URL（blob）
   * @returns {Object} 新建的素材
   */
  function addMediaMaterial(folderId, type, name, url) {
    const f = getFolder(folderId)
    if (!f) return null
    const m = {
      id: genId('m'),
      type,
      name: name.trim() || `新建${type === 'image' ? '图片' : '视频'}`,
      url,
      createdAt: nowStr()
    }
    f.materials.push(m)
    return m
  }

  /**
   * 重命名素材
   * @param {string} folderId 文件夹 ID
   * @param {string} materialId 素材 ID
   * @param {string} name 新名称
   */
  function renameMaterial(folderId, materialId, name) {
    const m = getMaterial(folderId, materialId)
    if (m && name.trim()) m.name = name.trim()
  }

  /**
   * 更新文本素材内容（实时保存）
   * @param {string} folderId 文件夹 ID
   * @param {string} materialId 素材 ID
   * @param {string} content 文本内容
   */
  function updateTextMaterial(folderId, materialId, content) {
    const m = getMaterial(folderId, materialId)
    if (m && m.type === 'text') m.content = content
  }

  /**
   * 删除单个素材
   * @param {string} folderId 文件夹 ID
   * @param {string} materialId 素材 ID
   */
  function removeMaterial(folderId, materialId) {
    const f = getFolder(folderId)
    if (!f) return
    const idx = f.materials.findIndex((m) => m.id === materialId)
    if (idx >= 0) f.materials.splice(idx, 1)
  }

  /**
   * 批量删除素材
   * @param {string} folderId 文件夹 ID
   * @param {string[]} materialIds 素材 ID 数组
   */
  function removeMaterials(folderId, materialIds) {
    const f = getFolder(folderId)
    if (!f) return
    const set = new Set(materialIds)
    f.materials = f.materials.filter((m) => !set.has(m.id))
  }

  /**
   * 批量移动素材到目标文件夹
   * @param {string} fromFolderId 源文件夹 ID
   * @param {string[]} materialIds 待移动素材 ID 数组
   * @param {string} toFolderId 目标文件夹 ID
   */
  function moveMaterials(fromFolderId, materialIds, toFolderId) {
    const from = getFolder(fromFolderId)
    const to = getFolder(toFolderId)
    if (!from || !to || from === to) return
    const set = new Set(materialIds)
    const moving = from.materials.filter((m) => set.has(m.id))
    to.materials.push(...moving)
    from.materials = from.materials.filter((m) => !set.has(m.id))
  }

  return {
    folders,
    getFolder,
    addFolder,
    renameFolder,
    removeFolder,
    removeFolders,
    getMaterial,
    addTextMaterial,
    addMediaMaterial,
    renameMaterial,
    updateTextMaterial,
    removeMaterial,
    removeMaterials,
    moveMaterials
  }
}
