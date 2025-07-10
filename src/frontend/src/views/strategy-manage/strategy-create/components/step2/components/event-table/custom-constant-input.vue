<template>
  <div
    v-if="!showAddCount"
    class="custom-constant-trigger"
    @click="() => showAddCount = true">
    <audit-icon
      class="plus-icon"
      type="plus-circle" />
    <span>{{ t('自定义常量') }}</span>
  </div>
  <div
    v-else
    class="custom-constant-input">
    <bk-input
      v-model="inputValue"
      autofocus
      :placeholder="t('请输入')"
      @enter="confirmValue" />
    <audit-icon
      class="confirm-icon"
      type="check-line"
      @click="confirmValue" />
    <audit-icon
      class="cancel-icon"
      type="close"
      @click="() => showAddCount = false" />
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Props {
    onConfirm: (value: string) => void;
  }

  const props = defineProps<Props>();
  const { t } = useI18n();

  const showAddCount = ref(false);
  const inputValue = ref('');

  const confirmValue = () => {
    if (inputValue.value.trim()) {
      props.onConfirm(inputValue.value.trim());
    }
    showAddCount.value = false;
    inputValue.value = '';
  };
</script>

<style lang="postcss" scoped>
.custom-constant-trigger {
  color: #63656e;
  text-align: center;
  flex: 1;
  cursor: pointer;

  .plus-icon {
    margin-right: 5px;
    font-size: 14px;
    color: #979ba5;
  }
}

.custom-constant-input {
  display: flex;
  width: 100%;
  padding: 0 5px;
  align-items: center;

  .confirm-icon {
    padding: 0 5px;
    font-size: 15px;
    color: #2caf5e;
    cursor: pointer;
  }

  .cancel-icon {
    font-size: 15px;
    color: #c4c6cc;
    cursor: pointer;
  }
}
</style>
