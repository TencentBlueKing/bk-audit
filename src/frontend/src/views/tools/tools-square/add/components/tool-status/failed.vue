<template>
  <div class="tool-status-failed">
    <div class="tool-status-failed-icon">
      <audit-icon
        type="delete-fill" />
    </div>
    <div class="tool-status-failed-text">
      <h1 style="margin-bottom: 16px;">
        {{ t('工具创建失败') }}
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

  const { t } = useI18n();

  const handleModifyAgain = () => {
    console.log('重新修改');
  };

  const handleBack = () => {
    console.log('返回工具广场');
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
