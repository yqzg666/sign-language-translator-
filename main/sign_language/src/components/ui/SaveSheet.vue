<script setup>
defineProps({
  open: { type: Boolean, default: false }
})
const emit = defineEmits(['close', 'album', 'materials'])
</script>

<template>
  <transition name="sheet">
    <div v-if="open" class="sheet-mask" @click.self="emit('close')">
      <div class="sheet glass">
        <p class="sheet-title">保存到</p>
        <button class="sheet-item btn-press" @click="emit('album')">
          <span class="item-icon">📷</span> 保存到相册
        </button>
        <button class="sheet-item btn-press" @click="emit('materials')">
          <span class="item-icon">📁</span> 保存到素材
        </button>
        <button class="sheet-cancel btn-press" @click="emit('close')">取消</button>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.sheet-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(3px);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  z-index: 85;
}
.sheet {
  width: 100%;
  max-width: 430px;
  padding: 12px 14px calc(14px + var(--safe-bottom));
  border-radius: 26px 26px 0 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sheet-title {
  text-align: center;
  font-size: 14px;
  color: var(--text-secondary);
  padding: 6px 0 8px;
}
.sheet-item {
  width: 100%;
  padding: 14px 16px;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid var(--glass-border);
  font-size: 15px;
  color: var(--text-primary);
  text-align: left;
  min-height: var(--touch-target);
  display: flex;
  align-items: center;
  gap: 10px;
}
.item-icon {
  font-size: 18px;
}
.sheet-cancel {
  width: 100%;
  padding: 14px;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid var(--glass-border);
  font-size: 15px;
  color: var(--text-secondary);
  min-height: var(--touch-target);
  margin-top: 4px;
}

/* 底部弹层过渡：从底部滑入 */
.sheet-enter-active,
.sheet-leave-active {
  transition: opacity 0.24s ease;
}
.sheet-enter-active .sheet,
.sheet-leave-active .sheet {
  transition: transform 0.28s cubic-bezier(0.2, 0, 0.2, 1);
}
.sheet-enter-from,
.sheet-leave-to {
  opacity: 0;
}
.sheet-enter-from .sheet,
.sheet-leave-to .sheet {
  transform: translateY(100%);
}
</style>
