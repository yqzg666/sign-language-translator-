import { reactive, computed } from 'vue'
import { materialsApi } from '@/api'

/**
 * 素材数据 store
 * 已对接 Django 后端 (records app 的 MaterialFolder / Material)。
 * 所有增删改查均调用后端 REST 接口，刷新后数据从后端加载，保证持久化。
 *
 * 字段映射：
 *   folder  { id, name, createdAt, materialsCount, materials: [] }
 *   material { id, type, name, content?, url?, createdAt, folderId }
 */

const state = reactive({
  folders: []
})

export function useMaterialsStore() {
  // 文件夹列表
  const folders = computed(() => state.folders)

  /**
   * 从后端加载所有文件夹（含素材数量），供刷新后恢复
   */
  async function load() {
    const res = await materialsApi.listFolders()
    const folders = res.folders || []
    state.folders = folders.map((f) => ({
      id: f.id,
      name: f.name,
      createdAt: f.createdAt || '',
      materialsCount: f.materialsCount || 0,
      materials: []
    }))
  }

  /**
   * 根据 ID 获取文件夹
   * @param {string|number} id 文件夹 ID
   * @returns {Object|null} 文件夹对象
   */
  function getFolder(id) {
    return state.folders.find((f) => String(f.id) === String(id)) || null
  }

  /**
   * 加载指定文件夹内的素材列表（首次进入文件夹时调用）
   * @param {string|number} folderId 文件夹 ID
   */
  async function ensureMaterials(folderId) {
    const f = getFolder(folderId)
    if (!f) return
    const res = await materialsApi.listMaterials(folderId)
    f.materials = (res.materials || []).map((m) => ({
      id: m.id,
      type: m.type,
      name: m.name,
      content: m.content || '',
      url: m.url || '',
      createdAt: m.createdAt || '',
      folderId: m.folderId
    }))
    f.materialsCount = f.materials.length
  }

  /**
   * 新建文件夹（后端持久化）
   * @param {string} name 文件夹名称
   * @returns {Promise<Object>} 新建的文件夹
   */
  async function addFolder(name) {
    const f = await materialsApi.createFolder(name.trim() || `文件夹 ${state.folders.length + 1}`)
    const folder = {
      id: f.id,
      name: f.name,
      createdAt: f.createdAt || '',
      materialsCount: 0,
      materials: []
    }
    state.folders.push(folder)
    return folder
  }

  /**
   * 重命名文件夹（后端持久化）
   * @param {string|number} id 文件夹 ID
   * @param {string} name 新名称
   */
  async function renameFolder(id, name) {
    const f = getFolder(id)
    const newName = (name || '').trim()
    if (!f || !newName) return
    await materialsApi.renameFolder(id, newName)
    f.name = newName
  }

  /**
   * 删除单个文件夹（后端持久化）
   * @param {string|number} id 文件夹 ID
   */
  async function removeFolder(id) {
    await materialsApi.deleteFolders([id])
    const idx = state.folders.findIndex((f) => String(f.id) === String(id))
    if (idx >= 0) state.folders.splice(idx, 1)
  }

  /**
   * 批量删除文件夹（后端持久化）
   * @param {Array} ids 文件夹 ID 数组
   */
  async function removeFolders(ids) {
    await materialsApi.deleteFolders(ids)
    const set = new Set(ids.map(String))
    state.folders = state.folders.filter((f) => !set.has(String(f.id)))
  }

  /**
   * 获取指定文件夹内的素材
   * @param {string|number} folderId 文件夹 ID
   * @param {string|number} materialId 素材 ID
   * @returns {Object|null} 素材对象
   */
  function getMaterial(folderId, materialId) {
    const f = getFolder(folderId)
    return f ? f.materials.find((m) => String(m.id) === String(materialId)) : null
  }

  /**
   * 新建文本素材（后端持久化）
   * @param {string|number} folderId 文件夹 ID
   * @param {string} name 素材名称
   * @param {string} content 文本内容
   * @returns {Promise<Object|null>} 新建的素材
   */
  async function addTextMaterial(folderId, name, content = '') {
    const f = getFolder(folderId)
    if (!f) return null
    const m = await materialsApi.createMaterial(folderId, { type: 'text', name: name || '新建文本', content })
    const mat = {
      id: m.id,
      type: 'text',
      name: m.name,
      content: m.content || '',
      url: '',
      createdAt: m.createdAt || ''
    }
    f.materials.push(mat)
    f.materialsCount = f.materials.length
    return mat
  }

  /**
   * 上传图片或视频素材（后端持久化）
   * @param {string|number} folderId 文件夹 ID
   * @param {string} type 'image' | 'video'
   * @param {string} name 素材名称
   * @param {File} file 上传文件
   * @returns {Promise<Object|null>} 新建的素材
   */
  async function addMediaMaterial(folderId, type, name, file) {
    const f = getFolder(folderId)
    if (!f) return null
    const m = await materialsApi.uploadMaterial(folderId, type, name, file)
    const mat = {
      id: m.id,
      type: m.type,
      name: m.name,
      content: '',
      url: m.url || '',
      createdAt: m.createdAt || ''
    }
    f.materials.push(mat)
    f.materialsCount = f.materials.length
    return mat
  }

  /**
   * 重命名素材（后端持久化）
   * @param {string|number} folderId 文件夹 ID
   * @param {string|number} materialId 素材 ID
   * @param {string} name 新名称
   */
  async function renameMaterial(folderId, materialId, name) {
    const m = getMaterial(folderId, materialId)
    const newName = (name || '').trim()
    if (!m || !newName) return
    await materialsApi.renameMaterial(materialId, newName)
    m.name = newName
  }

  /**
   * 更新文本素材内容（后端持久化）
   * @param {string|number} folderId 文件夹 ID
   * @param {string|number} materialId 素材 ID
   * @param {string} content 文本内容
   */
  async function updateTextMaterial(folderId, materialId, content) {
    const m = getMaterial(folderId, materialId)
    if (!m || m.type !== 'text') return
    await materialsApi.updateMaterialContent(materialId, content)
    m.content = content
  }

  /**
   * 删除单个素材（后端持久化）
   * @param {string|number} folderId 文件夹 ID
   * @param {string|number} materialId 素材 ID
   */
  async function removeMaterial(folderId, materialId) {
    await materialsApi.deleteMaterials([materialId])
    const f = getFolder(folderId)
    if (!f) return
    f.materials = f.materials.filter((m) => String(m.id) !== String(materialId))
    f.materialsCount = f.materials.length
  }

  /**
   * 批量删除素材（后端持久化）
   * @param {string|number} folderId 文件夹 ID
   * @param {Array} materialIds 素材 ID 数组
   */
  async function removeMaterials(folderId, materialIds) {
    await materialsApi.deleteMaterials(materialIds)
    const f = getFolder(folderId)
    if (!f) return
    const set = new Set(materialIds.map(String))
    f.materials = f.materials.filter((m) => !set.has(String(m.id)))
    f.materialsCount = f.materials.length
  }

  /**
   * 批量移动素材到目标文件夹（后端持久化）
   * @param {string|number} fromFolderId 源文件夹 ID
   * @param {Array} materialIds 待移动素材 ID 数组
   * @param {string|number} toFolderId 目标文件夹 ID
   */
  async function moveMaterials(fromFolderId, materialIds, toFolderId) {
    await materialsApi.moveMaterials(materialIds, toFolderId)
    const from = getFolder(fromFolderId)
    const to = getFolder(toFolderId)
    if (!from || !to || String(from.id) === String(to.id)) return
    const set = new Set(materialIds.map(String))
    const moving = from.materials.filter((m) => set.has(String(m.id)))
    to.materials.push(...moving)
    from.materials = from.materials.filter((m) => !set.has(String(m.id)))
    from.materialsCount = from.materials.length
    to.materialsCount = to.materials.length
  }

  return {
    folders,
    getFolder,
    load,
    ensureMaterials,
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
