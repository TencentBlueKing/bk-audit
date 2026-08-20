<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
-->
<template>
  <div class="user-with-me">
    <audit-user-selector-tenant
      v-model="localValue"
      allow-create
      class="user-selector"
      :multiple="multiple"
      :placeholder="placeholder" />
    <bk-button
      class="me-btn"
      size="small"
      @click="handleSelectMe">
      {{ t('我') }}
    </bk-button>
  </div>
</template>
<script setup lang="ts">
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Props {
    modelValue: string | string[];
    multiple?: boolean;
    placeholder?: string;
    currentUsername?: string;
  }

  interface Emits {
    (e: 'update:modelValue', value: string | string[]): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    multiple: true,
    placeholder: '',
    currentUsername: '',
  });
  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  const localValue = computed({
    get: () => props.modelValue,
    set: (value: string | string[]) => emits('update:modelValue', value),
  });

  const handleSelectMe = () => {
    if (!props.currentUsername) return;
    if (props.multiple) {
      const list = Array.isArray(props.modelValue) ? [...props.modelValue] : [];
      if (!list.includes(props.currentUsername)) {
        list.push(props.currentUsername);
      }
      emits('update:modelValue', list);
      return;
    }
    emits('update:modelValue', props.currentUsername);
  };
</script>
<style lang="postcss" scoped>
.user-with-me {
  display: flex;
  align-items: stretch;
  width: 100%;

  .user-selector {
    flex: 1;
    min-width: 0;
  }

  .me-btn {
    margin-left: -1px;
    border-radius: 0 2px 2px 0;
    flex-shrink: 0;
  }

  :deep(.bk-user-selector),
  :deep(.bk-select) {
    .bk-select-trigger,
    .bk-tag-input-trigger {
      border-top-right-radius: 0;
      border-bottom-right-radius: 0;
    }
  }
}
</style>
