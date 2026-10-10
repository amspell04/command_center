<script setup lang="ts">
import BaseModal from './BaseModal.vue'

defineProps<{ title: string; message: string; confirmLabel?: string; error?: string | null }>()
const emit = defineEmits<{ close: []; confirm: [] }>()
</script>

<template>
  <BaseModal :title="title" @close="emit('close')">
    <p>{{ message }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div class="actions">
      <button type="button" @click="emit('close')">Cancel</button>
      <button type="button" @click="emit('confirm')">{{ confirmLabel ?? 'Delete' }}</button>
    </div>
  </BaseModal>
</template>

<style scoped>
.actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}
.error {
  color: #c33;
}
</style>
