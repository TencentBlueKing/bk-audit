<template>
  <div class="tool-status-successful">
    <div class="tool-status-successful-icon">
      <audit-icon
        type="completed" />
    </div>
    <div class="tool-status-successful-text">
      <h1 style="margin-bottom: 16px;">
        {{ t('工具创建成功') }}
      </h1>
      <span>{{ t('接下来你可以返回工具广场使用该工具，或前往策略中配置该工具') }}</span>
      <div style="margin-top: 16px;">
        <bk-button
          theme="primary"
          @click="handleBack">
          {{ t('返回工具广场') }}
        </bk-button>
        <bk-button
          class="ml8"
          @click="handleStrategy">
          {{ t('配置策略') }}
        </bk-button>
      </div>
    </div>
  </div>
</template>
<script setup lang='ts'>
  import { useI18n } from 'vue-i18n';

  const { t } = useI18n();

  const handleStrategy = () => {
    console.log('配置策略');
  };

  const handleBack = () => {
    console.log('返回工具广场');
  };
</script>
<style lang="postcss" scoped>
.tool-status-successful {
  display: flex;
  height: 360px;
  text-align: center;
  background-color: #fff;
  flex-direction: column;
  justify-content: center;
  align-items: center;

  .tool-status-successful-icon {
    margin-bottom: 10px;
    font-size: 64px;
    color: #2caf5e;
  }
}
</style>
