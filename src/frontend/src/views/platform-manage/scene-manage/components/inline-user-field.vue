<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
-->
<template>
  <div class="inline-user-field">
    <div
      v-if="isEditing"
      class="editor-wrapper"
      @click.stop>
      <audit-user-selector-tenant
        v-model="editValue"
        allow-create
        auto-focus
        multiple />
      <div class="edit-actions">
        <audit-icon
          v-bk-tooltips="{ content: t('确定'), placement: 'top' }"
          class="confirm-icon"
          svg
          type="check-line"
          @click.stop="handleConfirm"
          @mousedown.prevent />
        <audit-icon
          v-bk-tooltips="{ content: t('取消'), placement: 'top' }"
          class="cancel-icon"
          svg
          type="close"
          @click.stop="handleCancel"
          @mousedown.prevent />
      </div>
    </div>
    <span
      v-else
      class="user-info">
      <edit-tag :data="users">
        <template #suffix>
          <audit-icon
            v-if="!saving"
            class="edit-icon"
            type="edit-fill"
            @click.stop="handleEdit" />
          <audit-icon
            v-else
            class="edit-loading"
            type="loading" />
        </template>
      </edit-tag>
    </span>
  </div>
</template>

<script setup lang="ts">
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import useMessage from '@hooks/use-message';

  import EditTag from '@components/edit-box/tag.vue';

  const props = withDefaults(defineProps<{
    users: string[];
    isEditing: boolean;
    saving?: boolean;
    minCount?: number;
  }>(), {
    users: () => [],
    saving: false,
    minCount: 0,
  });

  const emit = defineEmits<{
    edit: [];
    cancel: [];
    save: [value: string[]];
  }>();

  const { t } = useI18n();
  const { messageWarn } = useMessage();
  const editValue = ref<string[]>([]);

  watch(() => props.isEditing, (editing) => {
    if (editing) {
      editValue.value = [...(props.users || [])];
    }
  }, { immediate: true });

  const handleEdit = () => {
    editValue.value = [...(props.users || [])];
    emit('edit');
  };

  const handleCancel = () => {
    emit('cancel');
  };

  const handleConfirm = () => {
    if (props.minCount > 0 && editValue.value.length < props.minCount) {
      messageWarn(t('场景管理员至少保留一个'));
      return;
    }
    const original = props.users || [];
    const isSame = original.length === editValue.value.length
      && original.every((item, index) => item === editValue.value[index]);
    if (isSame) {
      emit('cancel');
      return;
    }
    emit('save', [...editValue.value]);
  };
</script>

<style lang="postcss" scoped>
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }

  .inline-user-field {
    width: 100%;
    min-width: 0;
  }

  .user-info {
    display: flex;
    align-items: center;
    width: 100%;
    min-width: 0;

    :deep(.audit-edit-tag) {
      flex: 1;
      min-width: 0;
      overflow: hidden;

      .edit-icon {
        opacity: 0;
      }

      &:hover .edit-icon {
        opacity: 1;
      }
    }
  }

  .edit-icon {
    flex-shrink: 0;
    font-size: 14px;
    color: #4d4f56;
    cursor: pointer;

    &:hover {
      color: #3a84ff;
    }
  }

  .edit-loading {
    flex-shrink: 0;
    font-size: 14px;
    color: #3a84ff;
    animation: spin 1s linear infinite;
  }

  .editor-wrapper {
    display: flex;
    width: 100%;
    max-width: 480px;
    gap: 8px;
    align-items: flex-start;

    :deep(.audit-user-selector),
    :deep(.bk-select),
    :deep(.bk-user-selector) {
      flex: 1;
      min-width: 0;
      height: auto !important;
      min-height: 32px;
    }

    :deep(.bk-user-selector .tags-container) {
      height: auto;
    }
  }

  .edit-actions {
    display: inline-flex;
    flex-shrink: 0;
    gap: 4px;
    align-items: center;
    height: 32px;
  }

  .confirm-icon {
    font-size: 18px;
    color: #2dcb56;
    cursor: pointer;

    &:hover {
      color: #45e06f;
    }
  }

  .cancel-icon {
    font-size: 18px;
    color: #ea3636;
    cursor: pointer;

    &:hover {
      color: #ff5656;
    }
  }
</style>
