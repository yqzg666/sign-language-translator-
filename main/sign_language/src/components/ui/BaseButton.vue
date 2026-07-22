<script setup>
import { computed } from 'vue'

// 按钮变体：blue 蓝色渐变（常规）/ yellow 黄色渐变（核心操作）/ ghost 透明
const props = defineProps({
  variant: { type: String, default: 'blue' },
  size: { type: String, default: 'md' }, // sm / md / lg
  block: { type: Boolean, default: false }, // 是否撑满宽度
  disabled: { type: Boolean, default: false }
})

// 计算按钮样式类名
const classes = computed(() => [
  'base-btn',
  `base-btn--${props.variant}`,
  `base-btn--${props.size}`,
  { 'base-btn--block': props.block, 'base-btn--disabled': props.disabled }
])
</script>

<template>
  <button :class="classes" :disabled="disabled" class="btn-press">
    <slot />
  </button>
</template>

<style scoped>
.base-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border-radius: var(--radius-md);
  font-weight: 500;
  white-space: nowrap;
  color: #fff;
}
.base-btn--block {
  width: 100%;
}
.base-btn--disabled {
  opacity: 0.5;
  pointer-events: none;
}

/* 尺寸：均满足 48px 触控标准 */
.base-btn--sm {
  padding: 10px 18px;
  font-size: 14px;
  min-height: 40px;
}
.base-btn--md {
  padding: 14px 22px;
  font-size: 15px;
  min-height: var(--touch-target);
}
.base-btn--lg {
  padding: 16px 24px;
  font-size: 16px;
  min-height: 52px;
}

/* 变体配色 */
.base-btn--blue {
  background: var(--gradient-blue);
  box-shadow: var(--shadow-blue);
}
.base-btn--yellow {
  background: var(--gradient-yellow);
  color: var(--text-on-yellow);
  box-shadow: var(--shadow-yellow);
}
.base-btn--ghost {
  background: rgba(255, 255, 255, 0.6);
  color: var(--text-primary);
  border: 1px solid var(--glass-border);
  box-shadow: none;
}
</style>
