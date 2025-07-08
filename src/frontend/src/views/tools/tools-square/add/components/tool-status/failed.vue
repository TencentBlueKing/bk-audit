<template>
  <div class="tool-status-failed">
    <div class="tool-status-failed-icon">
      <audit-icon
        type="delete-fill" />
    </div>
    <div class="tool-status-failed-text">
      <h1 style="margin-bottom: 16px;">
        <span>{{ name }}</span>
        {{ isEditMode ? t('工具编辑失败') : t('工具创建失败') }}
      </h1>
      <span>{{ t('接下来你可以重新修改工具，或返回工具广场') }}</span>
      <div style="margin-top: 16px;">
        <bk-button
          theme="primary"
          @click="handleModifyAgain">
          {{ t('重新修改') }}
        </bk-button>
        <bk-button
          class="ml8"
          @click="handleBack">
          {{ t('返回工具广场') }}
        </bk-button>
      </div>
    </div>
  </div>
</template>
<script setup lang='ts'>
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  interface Emits {
    (e: 'modifyAgain'): void;
  }
  interface Props {
    isEditMode: boolean;
    name: string;
  }

  defineProps<Props>();
  const emits = defineEmits<Emits>();
  const router = useRouter();
  const { t } = useI18n();

  const handleModifyAgain = () => {
    emits('modifyAgain');
  };

  const handleBack = () => {
    window.changeConfirm = false;
    router.push({
      name: 'toolsSquare',
    });
  };
</script>
<style lang="postcss" scoped>
.tool-status-failed {
  display: flex;
  height: 360px;
  text-align: center;
  background-color: #fff;
  flex-direction: column;
  justify-content: center;
  align-items: center;

  .tool-status-failed-icon {
    margin-bottom: 10px;
    font-size: 64px;
    color: red;
  }
}
</style>
