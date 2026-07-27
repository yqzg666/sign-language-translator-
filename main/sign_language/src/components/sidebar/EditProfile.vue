<script setup>
import { ref, onMounted } from 'vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { useAppStore } from '@/store/app'
import { userApi } from '@/api'
import { showToast } from '@/composables/useToast'

const store = useAppStore()

const nickname = ref(store.state.user.nickname)
const saving = ref(false)

/** 加载后端资料 */
onMounted(async () => {
  try {
    const data = await userApi.getProfile()
    if (data.nickname) {
      nickname.value = data.nickname
      store.updateProfile({ nickname: data.nickname })
    }
  } catch {
    // 离线时使用本地 store 值
  }
})

/**
 * 选择本地图片作为头像
 * 使用 FileReader 转 dataURL(base64)，便于在 localStorage 中持久化
 */
function chooseAvatar() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*'
  input.onchange = (e) => {
    const file = e.target.files[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      store.updateProfile({ avatar: reader.result })
      showToast('头像已更换')
    }
    reader.readAsDataURL(file)
  }
  input.click()
}

/**
 * 保存昵称：调用后端接口，成功后更新 store
 */
async function saveNickname() {
  const name = nickname.value.trim()
  if (!name) {
    showToast('昵称不能为空')
    return
  }
  saving.value = true
  try {
    await userApi.updateProfile(name)
    store.updateProfile({ nickname: name })
    showToast('资料已保存')
  } catch (e) {
    showToast(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="profile-page scroll-area">
    <section class="avatar-card glass">
      <button class="avatar-wrap btn-press" @click="chooseAvatar" aria-label="更换头像">
        <img v-if="store.state.user.avatar" :src="store.state.user.avatar" alt="头像" />
        <span v-else>😊</span>
        <span class="avatar-mask">更换</span>
      </button>
      <p class="avatar-tip">点击头像更换</p>
    </section>

    <section class="form-card glass">
      <label class="form-label">昵称</label>
      <input v-model="nickname" class="form-input" placeholder="请输入昵称" maxlength="20" />
      <BaseButton variant="yellow" block :disabled="saving" @click="saveNickname">
        {{ saving ? '保存中...' : '保存资料' }}
      </BaseButton>
    </section>
  </div>
</template>

<style scoped>
.profile-page {
  flex: 1;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  position: relative;
}
.avatar-card {
  padding: 28px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.avatar-wrap {
  position: relative;
  width: 96px;
  height: 96px;
  border-radius: 50%;
  background: var(--gradient-blue);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 44px;
  overflow: hidden;
  box-shadow: var(--shadow-blue);
}
.avatar-wrap img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.avatar-mask {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 4px 0;
  background: rgba(0, 0, 0, 0.42);
  color: #fff;
  font-size: 12px;
  text-align: center;
  opacity: 0;
  transition: opacity 0.2s ease;
}
.avatar-wrap:active .avatar-mask {
  opacity: 1;
}
.avatar-tip {
  font-size: 13px;
  color: var(--text-secondary);
}
.form-card {
  padding: 18px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.form-label {
  font-size: 14px;
  color: var(--text-secondary);
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
</style>
