<script setup>
import { ref, computed } from 'vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { useMaterialsStore } from '@/store/materials'

const emit = defineEmits(['open']) // 打开某文件夹的素材列表

const store = useMaterialsStore()

// 管理模式：批量勾选与删除
const manageMode = ref(false)
const selectedIds = ref([]) // 勾选的文件夹 ID

// 输入弹窗：create 新建 / rename 重命名
const inputVisible = ref(false)
const inputMode = ref('create') // create | rename
const inputName = ref('')
const inputTargetId = ref(null) // 重命名目标 ID
const inputError = ref('')

// 删除确认弹窗
const confirmVisible = ref(false)
const confirmCount = ref(0)
const confirmAction = ref('batch') // batch | single
const confirmTargetId = ref(null)

// 是否全选
const isAllSelected = computed(
  () => store.folders.value.length > 0 && selectedIds.value.length === store.folders.value.length
)

// 进入文件夹素材列表
function openFolder(id) {
  if (manageMode.value) return
  emit('open', id)
}

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
 * 切换单个文件夹勾选
 * @param {string} id 文件夹 ID
 */
function toggleSelect(id) {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(id)
}

// 全选 / 取消全选
function toggleSelectAll() {
  if (isAllSelected.value) selectedIds.value = []
  else selectedIds.value = store.folders.value.map((f) => f.id)
}

// 打开新建文件夹弹窗
function openCreate() {
  inputMode.value = 'create'
  inputName.value = ''
  inputError.value = ''
  inputVisible.value = true
}

/**
 * 打开重命名弹窗
 * @param {string} id 文件夹 ID
 * @param {string} name 当前名称
 */
function openRename(id, name) {
  inputMode.value = 'rename'
  inputTargetId.value = id
  inputName.value = name
  inputError.value = ''
  inputVisible.value = true
}

// 提交新建/重命名
function submitInput() {
  if (!inputName.value.trim()) {
    inputError.value = '名称不能为空'
    return
  }
  if (inputMode.value === 'create') {
    store.addFolder(inputName.value)
  } else {
    store.renameFolder(inputTargetId.value, inputName.value)
  }
  inputVisible.value = false
}

/**
 * 打开单个删除确认
 * @param {string} id 文件夹 ID
 * @param {string} name 文件夹名称
 */
function openDeleteSingle(id, name) {
  confirmAction.value = 'single'
  confirmTargetId.value = id
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
    store.removeFolder(confirmTargetId.value)
  } else {
    store.removeFolders(selectedIds.value)
    exitManage()
  }
  confirmVisible.value = false
}
</script>

<template>
  <div class="folder-list scroll-area">
    <!-- 顶部操作栏 -->
    <div class="top-bar">
      <BaseButton variant="yellow" size="sm" @click="openCreate">＋ 新建文件夹</BaseButton>
      <button
        v-if="store.folders.value.length && !manageMode"
        class="link-btn btn-press"
        @click="enterManage"
      >
        管理
      </button>
      <button v-else-if="manageMode" class="link-btn btn-press" @click="exitManage">完成</button>
    </div>

    <!-- 管理模式下的批量操作栏 -->
    <div v-if="manageMode" class="manage-bar">
      <button class="link-btn btn-press" @click="toggleSelectAll">
        {{ isAllSelected ? '取消全选' : '全选' }}
      </button>
      <span class="manage-count">已选 {{ selectedIds.length }} 项</span>
    </div>

    <!-- 文件夹卡片列表 -->
    <div v-if="store.folders.value.length" class="folder-grid">
      <div
        v-for="f in store.folders.value"
        :key="f.id"
        class="folder-card glass btn-press"
        :class="{ checked: manageMode && selectedIds.includes(f.id) }"
        @click="manageMode ? toggleSelect(f.id) : openFolder(f.id)"
      >
        <!-- 管理模式勾选圆圈 -->
        <span v-if="manageMode" class="check" :class="{ filled: selectedIds.includes(f.id) }">
          <span v-if="selectedIds.includes(f.id)" class="check-mark">✓</span>
        </span>
        <div class="folder-icon">📁</div>
        <div class="folder-info">
          <p class="folder-name">{{ f.name }}</p>
          <p class="folder-meta">{{ f.createdAt }}</p>
          <p class="folder-meta">{{ f.materials.length }} 个素材</p>
        </div>
        <!-- 非管理模式下的单卡操作 -->
        <div v-if="!manageMode" class="card-actions" @click.stop>
          <button class="icon-op btn-press" @click="openRename(f.id, f.name)" aria-label="重命名">✏️</button>
          <button class="icon-op btn-press" @click="openDeleteSingle(f.id, f.name)" aria-label="删除">🗑️</button>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <span class="empty-icon">🗂️</span>
      <p class="empty-title">还没有文件夹</p>
      <p class="empty-desc">点击上方「新建文件夹」开始整理你的素材</p>
    </div>

    <!-- 管理模式底部批量删除按钮 -->
    <div v-if="manageMode" class="bottom-bar">
      <BaseButton variant="yellow" block :disabled="!selectedIds.length" @click="openDeleteBatch">
        删除 ({{ selectedIds.length }})
      </BaseButton>
    </div>

    <!-- 新建/重命名输入弹窗 -->
    <transition name="modal">
      <div v-if="inputVisible" class="modal-mask" @click.self="inputVisible = false">
        <div class="input-modal glass">
          <p class="modal-title">{{ inputMode === 'create' ? '新建文件夹' : '重命名文件夹' }}</p>
          <input v-model="inputName" class="modal-input" placeholder="请输入名称" autofocus />
          <p v-if="inputError" class="modal-error">{{ inputError }}</p>
          <div class="modal-actions">
            <BaseButton variant="ghost" size="sm" @click="inputVisible = false">取消</BaseButton>
            <BaseButton variant="yellow" size="sm" @click="submitInput">确定</BaseButton>
          </div>
        </div>
      </div>
    </transition>

    <!-- 删除确认弹窗 -->
    <transition name="modal">
      <div v-if="confirmVisible" class="modal-mask" @click.self="confirmVisible = false">
        <div class="confirm-modal glass">
          <p class="modal-title">确认删除</p>
          <p class="confirm-desc">
            确定删除选中的 {{ confirmCount }} 个文件夹？文件夹内素材将一并删除，且不可恢复。
          </p>
          <div class="modal-actions">
            <BaseButton variant="ghost" size="sm" @click="confirmVisible = false">取消</BaseButton>
            <BaseButton variant="yellow" size="sm" @click="doDelete">确认删除</BaseButton>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.folder-list {
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

/* 文件夹卡片 */
.folder-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 80px;
}
.folder-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  border: 2px solid transparent;
}
.folder-card.checked {
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
.folder-icon {
  font-size: 30px;
  flex-shrink: 0;
}
.folder-info {
  flex: 1;
  min-width: 0;
}
.folder-name {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.folder-meta {
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
  font-size: 15px;
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

/* 底部批量删除 */
.bottom-bar {
  position: absolute;
  left: 16px;
  right: 16px;
  bottom: calc(16px + var(--safe-bottom));
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
  padding: 24px;
  z-index: 70;
}
.input-modal,
.confirm-modal {
  width: 100%;
  max-width: 320px;
  padding: 24px 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.modal-title {
  text-align: center;
  font-size: 18px;
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
.modal-error {
  color: #e06a78;
  font-size: 13px;
  text-align: center;
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
  margin-top: 4px;
}
.modal-actions > * {
  flex: 1;
}
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.24s ease;
}
.modal-enter-active .input-modal,
.modal-leave-active .input-modal,
.modal-enter-active .confirm-modal,
.modal-leave-active .confirm-modal {
  transition: transform 0.28s cubic-bezier(0.2, 0, 0.2, 1), opacity 0.28s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-from .input-modal,
.modal-leave-to .input-modal,
.modal-enter-from .confirm-modal,
.modal-leave-to .confirm-modal {
  transform: scale(0.92);
  opacity: 0;
}
</style>
