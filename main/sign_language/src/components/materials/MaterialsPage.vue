<script setup>
import { ref } from 'vue'
import FolderList from './FolderList.vue'
import MaterialList from './MaterialList.vue'
import { useMaterialsStore } from '@/store/materials'

const emit = defineEmits(['title'])

const store = useMaterialsStore()

// 当前层级：folders 文件夹列表 / materials 素材列表
const level = ref('folders')
const currentFolderId = ref(null)

/**
 * 进入某文件夹的素材列表，同步顶部标题为文件夹名
 * @param {string} id 文件夹 ID
 */
function openFolder(id) {
  currentFolderId.value = id
  level.value = 'materials'
  const f = store.getFolder(id)
  emit('title', f ? f.name : '素材列表')
}

// 从素材列表返回文件夹列表
function backToFolders() {
  level.value = 'folders'
  currentFolderId.value = null
  emit('title', '我的素材')
}

/**
 * 顶部返回键上下文处理
 * 素材列表 → 文件夹列表（内部处理）；文件夹列表 → 关闭素材页（交由父级）
 * @returns {boolean} 是否已在内部处理
 */
function goBack() {
  if (level.value === 'materials') {
    backToFolders()
    return true
  }
  return false
}
defineExpose({ goBack })
</script>

<template>
  <div class="materials-page">
    <FolderList v-show="level === 'folders'" @open="openFolder" />
    <MaterialList v-if="level === 'materials'" :folder-id="currentFolderId" :key="currentFolderId" />
  </div>
</template>

<style scoped>
.materials-page {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}
</style>
