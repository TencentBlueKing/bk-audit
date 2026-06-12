<template>
  <bk-form-item property="users">
    <template #label>
      <bk-popover
        placement="top"
        theme="dark">
        <span class="label-tips">{{ t('可见范围') }}</span>
        <template #content>
          <div>{{ t('选择可使用该工具的人员；不选择时默认当前范围内全部可见') }}</div>
        </template>
      </bk-popover>
    </template>
    <audit-user-selector-tenant
      :auto-focus="false"
      :collapse-tags="false"
      :model-value="formData.users"
      multiple
      @update:model-value="handleUsersChange" />
  </bk-form-item>
</template>

<script setup lang="ts">
  import { useI18n } from 'vue-i18n';

  import type { FormData } from '@views/platform-manage/tool-manage/create-tool/types';

  const props = defineProps<{
    formData: FormData;
  }>();

  const emit = defineEmits<{(e: 'update:formData', value: FormData): void}>();

  const handleUsersChange = (value: any) => {
    emit('update:formData', { ...props.formData, users: value });
  };

  const { t } = useI18n();
</script>
