<script setup>
import { ref, computed } from 'vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { useMaterialsStore } from '@/store/materials'

const props = defineProps({
  folderId: { type: String, required: true }
})

const store = useMaterialsStore()

// 当前文件夹及其素材（响应式）
const currentFolder = computed(() => store.getFolder(props.folderId))
const materials = computed(() => currentFolder.value?.materials || [])

// 管理模式：批量勾选
const manageMode = ref(false)
const selectedIds = ref([])

// 重命名弹窗
const renameVisible = ref(false)
const renameTarget = ref(null) // 待重命名的素材对象
const renameName = ref('')

// 删除确认弹窗
const confirmVisible = ref(false)
const confirmCount = ref(0)
const confirmAction = ref('batch') // batch | single
const confirmTargetId = ref(null)

// 文本编辑器弹窗（实时保存：直接双向绑定 store 中的素材对象）
const editorVisible = ref(false)
const editorMaterial = ref(null)

// 媒体预览弹窗
const previewVisible = ref(false)
const previewMaterial = ref(null)

// 移动目标选择弹窗
const moveVisible = ref(false)
const otherFolders = computed(() => store.folders.value.filter((f) => f.id !== props.folderId))

// 是否全选
const isAllSelected = computed(
  () => materials.value.length > 0 && selectedIds.value.length === materials.value.length
)

// 进入管理模式
function enterManage() {
  selectedIds.value = []
  manageMode.value = true
}

// 退出管理模式
function exitManage() {
  manageMode.value = false
  selectedIds.value = []
}

/**
 * 切换单个素材勾选
 * @param {string} id 素材 ID
 */
function toggleSelect(id) {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(id)
}

// 全选 / 取消全选
function toggleSelectAll() {
  if (isAllSelected.value) selectedIds.value = []
  else selectedIds.value = materials.value.map((m) => m.id)
}

/**
 * 点击素材卡片：文本→编辑器，图片/视频→预览
 * @param {Object} m 素材对象
 */
function onMaterialClick(m) {
  if (manageMode.value) {
    toggleSelect(m.id)
    return
  }
  if (m.type === 'text') {
    editorMaterial.value = m
    editorVisible.value = true
  } else {
    previewMaterial.value = m
    previewVisible.value = true
  }
}

// 关闭文本编辑器
function closeEditor() {
  editorVisible.value = false
  editorMaterial.value = null
}

/**
 * 打开重命名弹窗
 * @param {Object} m 素材对象
 */
function openRename(m) {
  renameTarget.value = m
  renameName.value = m.name
  renameVisible.value = true
}

// 提交重命名
function submitRename() {
  if (renameTarget.value && renameName.value.trim()) {
    store.renameMaterial(props.folderId, renameTarget.value.id, renameName.value)
  }
  renameVisible.value = false
}

/**
 * 打开单个删除确认
 * @param {Object} m 素材对象
 */
function openDeleteSingle(m) {
  confirmAction.value = 'single'
  confirmTargetId.value = m.id
  confirmCount.value = 1
  confirmVisible.value = true
}

// 打开批量删除确认
function openDeleteBatch() {
  if (!selectedIds.value.length) return
  confirmAction.value = 'batch'
  confirmCount.value = selectedIds.value.length
  confirmVisible.value = true
}

// 执行删除
function doDelete() {
  if (confirmAction.value === 'single') {
    store.removeMaterial(props.folderId, confirmTargetId.value)
  } else {
    store.removeMaterials(props.folderId, selectedIds.value)
    exitManage()
  }
  confirmVisible.value = false
}

// 打开批量移动弹窗
function openMove() {
  if (!selectedIds.value.length) return
  moveVisible.value = true
}

/**
 * 选择目标文件夹执行移动
 * @param {string} toId 目标文件夹 ID
 */
function doMove(toId) {
  store.moveMaterials(props.folderId, selectedIds.value, toId)
  moveVisible.value = false
  exitManage()
}

// 新建文本素材并直接打开编辑器
function createText() {
  const m = store.addTextMaterial(props.folderId, '新建文本', '')
  if (m) {
    editorMaterial.value = m
    editorVisible.value = true
  }
}

/**
 * 触发图片/视频上传
 * @param {string} type 'image' | 'video'
 */
function triggerUpload(type) {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = type === 'image' ? 'image/*' : 'video/*'
  input.onchange = (e) => {
    const file = e.target.files[0]
    if (!file) return
    const url = URL.createObjectURL(file)
    store.addMediaMaterial(props.folderId, type, file.name.replace(/\.[^.]+$/, ''), url)
  }
  input.click()
}

// 素材类型图标
function typeIcon(type) {
  return { text: '📝', image: '🖼️', video: '🎞️' }[type] || '📄'
}
</script>

<template>
  <div class="material-list scroll-area">
    <!-- 顶部操作栏 -->
    <div class="top-bar">
      <div class="add-group">
        <BaseButton variant="yellow" size="sm" @click="createText">＋ 文本</BaseButton>
        <BaseButton variant="ghost" size="sm" @click="triggerUpload('image')">🖼️ 图片</BaseButton>
        <BaseButton variant="ghost" size="sm" @click="triggerUpload('video')">🎞️ 视频</BaseButton>
      </div>
      <button
        v-if="materials.length && !manageMode"
        class="link-btn btn-press"
        @click="enterManage"
      >
        管理
      </button>
      <button v-else-if="manageMode" class="link-btn btn-press" @click="exitManage">完成</button>
    </div>

    <!-- 管理模式批量操作栏 -->
    <div v-if="manageMode" class="manage-bar">
      <button class="link-btn btn-press" @click="toggleSelectAll">
        {{ isAllSelected ? '取消全选' : '全选' }}
      </button>
      <span class="manage-count">已选 {{ selectedIds.length }} 项</span>
    </div>

    <!-- 素材卡片列表 -->
    <div v-if="materials.length" class="material-grid">
      <div
        v-for="m in materials"
        :key="m.id"
        class="material-card glass btn-press"
        :class="{ checked: manageMode && selectedIds.includes(m.id) }"
        @click="onMaterialClick(m)"
      >
        <span v-if="manageMode" class="check" :class="{ filled: selectedIds.includes(m.id) }">
          <span v-if="selectedIds.includes(m.id)" class="check-mark">✓</span>
        </span>
        <div class="m-icon">{{ typeIcon(m.type) }}</div>
        <div class="m-info">
          <p class="m-name">{{ m.name }}</p>
          <p class="m-meta">{{ m.createdAt }}</p>
        </div>
        <div v-if="!manageMode" class="card-actions" @click.stop>
          <button class="icon-op btn-press" @click="openRename(m)" aria-label="重命名">✏️</button>
          <button class="icon-op btn-press" @click="openDeleteSingle(m)" aria-label="删除">🗑️</button>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <span class="empty-icon">📦</span>
      <p class="empty-title">文件夹内还没有素材</p>
      <p class="empty-desc">点击上方按钮新建文本或上传图片/视频</p>
    </div>

    <!-- 管理模式底部批量操作 -->
    <div v-if="manageMode" class="bottom-bar">
      <div class="batch-actions">
        <BaseButton variant="blue" size="sm" :disabled="!selectedIds.length" @click="openMove">
          移动至
        </BaseButton>
        <BaseButton variant="yellow" size="sm" :disabled="!selectedIds.length" @click="openDeleteBatch">
          删除 ({{ selectedIds.length }})
        </BaseButton>
      </div>
    </div>

    <!-- 文本编辑器弹窗（实时保存） -->
    <transition name="modal">
      <div v-if="editorVisible && editorMaterial" class="modal-mask" @click.self="closeEditor">
        <div class="editor-modal glass">
          <div class="editor-head">
            <p class="modal-title">编辑文本</p>
            <button class="icon-op btn-press" @click="closeEditor" aria-label="关闭">✕</button>
          </div>
          <!-- 直接双向绑定 store 素材对象，实现实时保存 -->
          <input v-model="editorMaterial.name" class="modal-input" placeholder="素材名称" />
          <textarea
            v-model="editorMaterial.content"
            class="editor-textarea"
            placeholder="在此输入内容，自动保存..."
            rows="8"
          ></textarea>
          <p class="save-tip">✓ 已自动保存</p>
        </div>
      </div>
    </transition>

    <!-- 媒体预览弹窗 -->
    <transition name="modal">
      <div v-if="previewVisible && previewMaterial" class="modal-mask" @click.self="previewVisible = false">
        <div class="preview-modal glass">
          <div class="editor-head">
            <p class="modal-title">{{ previewMaterial.name }}</p>
            <button class="icon-op btn-press" @click="previewVisible = false" aria-label="关闭">✕</button>
          </div>
          <img v-if="previewMaterial.type === 'image'" :src="previewMaterial.url" class="preview-media" />
          <video v-else :src="previewMaterial.url" class="preview-media" controls></video>
        </div>
      </div>
    </transition>

    <!-- 重命名弹窗 -->
    <transition name="modal">
      <div v-if="renameVisible" class="modal-mask" @click.self="renameVisible = false">
        <div class="input-modal glass">
          <p class="modal-title">重命名素材</p>
          <input v-model="renameName" class="modal-input" placeholder="请输入名称" />
          <div class="modal-actions">
            <BaseButton variant="ghost" size="sm" @click="renameVisible = false">取消</BaseButton>
            <BaseButton variant="yellow" size="sm" @click="submitRename">确定</BaseButton>
          </div>
        </div>
      </div>
    </transition>

    <!-- 删除确认弹窗 -->
    <transition name="modal">
      <div v-if="confirmVisible" class="modal-mask" @click.self="confirmVisible = false">
        <div class="confirm-modal glass">
          <p class="modal-title">确认删除</p>
          <p class="confirm-desc">确定删除选中的 {{ confirmCount }} 个素材？删除后不可恢复。</p>
          <div class="modal-actions">
            <BaseButton variant="ghost" size="sm" @click="confirmVisible = false">取消</BaseButton>
            <BaseButton variant="yellow" size="sm" @click="doDelete">确认删除</BaseButton>
          </div>
        </div>
      </div>
    </transition>

    <!-- 移动目标选择弹窗 -->
    <transition name="modal">
      <div v-if="moveVisible" class="modal-mask" @click.self="moveVisible = false">
        <div class="move-modal glass">
          <p class="modal-title">移动至文件夹</p>
          <div v-if="otherFolders.length" class="move-list scroll-area">
            <button
              v-for="f in otherFolders"
              :key="f.id"
              class="move-item btn-press"
              @click="doMove(f.id)"
            >
              📁 {{ f.name }}
              <span class="move-count">{{ f.materials.length }}</span>
            </button>
          </div>
          <p v-else class="confirm-desc">没有其他可移动的文件夹，请先新建。</p>
          <div class="modal-actions">
            <BaseButton variant="ghost" size="sm" @click="moveVisible = false">取消</BaseButton>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.material-list {
  flex: 1;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  position: relative;
}
.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.add-group {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.link-btn {
  padding: 4px 10px;
  font-size: 14px;
  color: #4a8fe0;
  min-height: 36px;
}
.manage-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 4px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.6);
}
.manage-count {
  font-size: 13px;
  color: var(--text-secondary);
}

/* 素材卡片 */
.material-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 80px;
}
.material-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border: 2px solid transparent;
}
.material-card.checked {
  border-color: var(--gradient-blue);
  background: rgba(104, 174, 247, 0.14);
}
.check {
  position: absolute;
  top: 10px;
  right: 12px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 1.5px solid rgba(120, 150, 200, 0.6);
  background: rgba(255, 255, 255, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
}
.check.filled {
  background: var(--gradient-blue);
  border-color: transparent;
}
.check-mark {
  font-size: 13px;
  color: #fff;
}
.m-icon {
  font-size: 26px;
  flex-shrink: 0;
}
.m-info {
  flex: 1;
  min-width: 0;
}
.m-name {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-meta {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}
.card-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
.icon-op {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.6);
  font-size: 14px;
}

/* 空状态 */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-secondary);
}
.empty-icon {
  font-size: 56px;
}
.empty-title {
  font-size: 16px;
  color: var(--text-primary);
}
.empty-desc {
  font-size: 13px;
}

/* 底部批量操作 */
.bottom-bar {
  position: absolute;
  left: 16px;
  right: 16px;
  bottom: calc(16px + var(--safe-bottom));
}
.batch-actions {
  display: flex;
  gap: 12px;
}
.batch-actions > * {
  flex: 1;
}

/* 弹窗通用 */
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(3px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  z-index: 70;
}
.editor-modal,
.preview-modal,
.input-modal,
.confirm-modal,
.move-modal {
  width: 100%;
  max-width: 360px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 86dvh;
}
.editor-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.modal-title {
  font-size: 17px;
  font-weight: 500;
  color: var(--text-primary);
}
.modal-input {
  width: 100%;
  padding: 12px 14px;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid var(--glass-border);
  font-size: 14px;
  color: var(--text-primary);
}
.editor-textarea {
  width: 100%;
  padding: 12px 14px;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid var(--glass-border);
  font-size: 14px;
  color: var(--text-primary);
  resize: none;
  line-height: 1.6;
  min-height: 180px;
}
.save-tip {
  font-size: 12px;
  color: #5aa57a;
  text-align: right;
}
.preview-media {
  width: 100%;
  max-height: 60dvh;
  border-radius: var(--radius-md);
  object-fit: contain;
  background: #000;
}
.confirm-desc {
  font-size: 14px;
  color: var(--text-secondary);
  text-align: center;
  line-height: 1.5;
}
.modal-actions {
  display: flex;
  gap: 12px;
}
.modal-actions > * {
  flex: 1;
}
.move-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 50dvh;
}
.move-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid var(--glass-border);
  font-size: 14px;
  color: var(--text-primary);
  min-height: var(--touch-target);
}
.move-count {
  font-size: 12px;
  color: var(--text-secondary);
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.24s ease;
}
.modal-enter-active .editor-modal,
.modal-leave-active .editor-modal,
.modal-enter-active .preview-modal,
.modal-leave-active .preview-modal,
.modal-enter-active .input-modal,
.modal-leave-active .input-modal,
.modal-enter-active .confirm-modal,
.modal-leave-active .confirm-modal,
.modal-enter-active .move-modal,
.modal-leave-active .move-modal {
  transition: transform 0.28s cubic-bezier(0.2, 0, 0.2, 1), opacity 0.28s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-from .editor-modal,
.modal-leave-to .editor-modal,
.modal-enter-from .preview-modal,
.modal-leave-to .preview-modal,
.modal-enter-from .input-modal,
.modal-leave-to .input-modal,
.modal-enter-from .confirm-modal,
.modal-leave-to .confirm-modal,
.modal-enter-from .move-modal,
.modal-leave-to .move-modal {
  transform: scale(0.92);
  opacity: 0;
}
</style>
