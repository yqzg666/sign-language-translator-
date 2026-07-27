<script setup>
import { ref, computed } from 'vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { useMaterialsStore } from '@/store/materials'

const props = defineProps({
  open: { type: Boolean, default: false }
})
const emit = defineEmits(['close', 'select'])

const store = useMaterialsStore()

// 快速新建文件夹输入
const creating = ref(false)
const newName = ref('')

// 文件夹列表
const folders = computed(() => store.folders.value)

// 打开新建输入
function startCreate() {
  newName.value = ''
  creating.value = true
}

// 确认新建文件夹
function confirmCreate() {
  if (!newName.value.trim()) return
  store.addFolder(newName.value)
  creating.value = false
}

/**
 * 选择目标文件夹
 * @param {string} id 文件夹 ID
 */
function pick(id) {
  emit('select', id)
  creating.value = false
}
</script>

<template>
  <transition name="modal">
    <div v-if="open" class="picker-mask" @click.self="emit('close')">
      <div class="picker-modal glass">
        <div class="picker-head">
          <p class="picker-title">保存到文件夹</p>
          <button class="icon-op btn-press" @click="emit('close')" aria-label="关闭">✕</button>
        </div>

        <!-- 文件夹列表 -->
        <div v-if="folders.length" class="picker-list scroll-area">
          <button
            v-for="f in folders"
            :key="f.id"
            class="picker-item btn-press"
            @click="pick(f.id)"
          >
            📁 {{ f.name }}
            <span class="picker-count">{{ f.materials.length }}</span>
          </button>
        </div>

        <!-- 空状态 -->
        <div v-else class="picker-empty">还没有文件夹，请先新建</div>

        <!-- 新建文件夹区域 -->
        <div class="create-zone">
          <div v-if="creating" class="create-row">
            <input v-model="newName" class="create-input" placeholder="文件夹名称" />
            <BaseButton variant="yellow" size="sm" @click="confirmCreate">新建</BaseButton>
          </div>
          <BaseButton v-else variant="blue" size="sm" block @click="startCreate">
            ＋ 新建文件夹
          </BaseButton>
        </div>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.picker-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(3px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  z-index: 80;
}
.picker-modal {
  width: 100%;
  max-width: 340px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 80dvh;
}
.picker-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.picker-title {
  font-size: 17px;
  font-weight: 500;
  color: var(--text-primary);
}
.icon-op {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.6);
  font-size: 14px;
}
.picker-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 44dvh;
}
.picker-item {
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
.picker-count {
  font-size: 12px;
  color: var(--text-secondary);
}
.picker-empty {
  text-align: center;
  font-size: 13px;
  color: var(--text-secondary);
  padding: 20px 0;
}
.create-zone {
  border-top: 1px solid rgba(255, 255, 255, 0.6);
  padding-top: 12px;
}
.create-row {
  display: flex;
  gap: 8px;
}
.create-input {
  flex: 1;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid var(--glass-border);
  font-size: 14px;
  color: var(--text-primary);
  min-width: 0;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.24s ease;
}
.modal-enter-active .picker-modal,
.modal-leave-active .picker-modal {
  transition: transform 0.28s cubic-bezier(0.2, 0, 0.2, 1), opacity 0.28s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-from .picker-modal,
.modal-leave-to .picker-modal {
  transform: scale(0.92);
  opacity: 0;
}
</style>
