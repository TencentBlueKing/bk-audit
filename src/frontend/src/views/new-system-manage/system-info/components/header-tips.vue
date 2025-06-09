<template>
  <div class="header-tips">
    <span class="tips-text">
      当前系统未完成配置：1.<span class="tips-link">
        注册系统信息</span>
      -> 2.<span class="tips-link">注册权限模型
      </span>-> 3.<span class="tips-link">上报日志数据</span>
    </span>
  </div>
</template>

<script setup lang="ts">

</script>

<style scoped lang="postcss">
.header-tips {
  width: 100%;
  height: 32px;
  font-size: 12px;
  line-height: 32px;
  letter-spacing: 0;
  color: #4d4f56;
  background: #fdf4e8;
  border: 1px solid #f9d090;

  .tips-text {
    .tips-link {
      color: #77a8f8;
    }
  }

}
</style>
