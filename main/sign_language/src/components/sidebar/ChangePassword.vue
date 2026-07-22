<script setup>
import { ref } from 'vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { userApi } from '@/api'
import { showToast } from '@/composables/useToast'

// 表单数据
const oldPwd = ref('')
const newPwd = ref('')
const confirmPwd = ref('')
const error = ref('')
const submitting = ref(false) // 提交中状态

/**
 * 提交修改密码：校验非空与两次一致后调用后端接口
 * 后端对接：userApi.changePassword(oldPwd, newPwd)
 */
async function submit() {
  error.value = ''
  if (!oldPwd.value || !newPwd.value || !confirmPwd.value) {
    error.value = '请填写完整密码信息'
    return
  }
  if (newPwd.value !== confirmPwd.value) {
    error.value = '两次输入的新密码不一致'
    return
  }
  if (newPwd.value === oldPwd.value) {
    error.value = '新密码不能与旧密码相同'
    return
  }
  submitting.value = true
  try {
    // 调用后端：修改登录密码
    await userApi.changePassword(oldPwd.value, newPwd.value)
    showToast('密码修改成功')
    // 清空表单
    oldPwd.value = ''
    newPwd.value = ''
    confirmPwd.value = ''
  } catch (e) {
    error.value = e.message || '修改失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="pwd-page scroll-area">
    <section class="form-card glass">
      <p class="page-tip">为保障账号安全，请定期更换登录密码</p>

      <input
        v-model="oldPwd"
        type="password"
        class="form-input"
        placeholder="请输入当前密码"
      />
      <input
        v-model="newPwd"
        type="password"
        class="form-input"
        placeholder="请输入新密码"
      />
      <input
        v-model="confirmPwd"
        type="password"
        class="form-input"
        placeholder="请再次输入新密码"
        @keyup.enter="submit"
      />

      <p v-if="error" class="form-error">{{ error }}</p>

      <BaseButton variant="yellow" block :disabled="submitting" @click="submit">
        {{ submitting ? '提交中...' : '确认修改' }}
      </BaseButton>
    </section>
  </div>
</template>

<style scoped>
.pwd-page {
  flex: 1;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  position: relative;
}

.form-card {
  padding: 20px 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.page-tip {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}
.form-input {
  width: 100%;
  padding: 14px 16px;
  border-radius: var(--radius-md);
  background: var(--surface-bg-strong);
  border: 1px solid var(--glass-border);
  font-size: 15px;
  color: var(--text-primary);
}
.form-error {
  color: #e06a78;
  font-size: 13px;
  text-align: center;
}
</style>
