<template>
  <div class="report-source">
    <div class="source-label">
      引用来源：
    </div>
    <bk-popover
      ext-cls="source-popover"
      :offset="{ mainAxis: 8 }"
      placement="top"
      theme="light">
      <div class="source-tag">
        <span class="source-text">[1] 安全运营-行为查询</span>
      </div>
      <template #content>
        <div class="source-popover-content">
          <div class="popover-title">
            安全运营-行为查询
          </div>
          <div class="popover-desc">
            安全运营 → 风险列表页面，可查看全部未处理风险告警
          </div>
          <a
            class="popover-link"
            href="javascript:void(0)">
            跳转至详情页
            <share />
          </a>
        </div>
      </template>
    </bk-popover>
  </div>
</template>

<script lang="ts" setup>
  import { Share } from 'bkui-vue/lib/icon';
</script>

<style lang="postcss" scoped>
.report-source {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 0;
  border-top: 1px solid #dcdee5;

  .source-label {
    font-size: 13px;
    color: #63656e;
  }

  .source-tag {
    display: inline-flex;
    width: fit-content;
    padding: 6px 12px;
    font-size: 13px;
    background: #f5f7fa;
    border-radius: 4px;
    align-items: center;

    .source-text {
      color: #63656e;
    }
  }
}
</style>

<style lang="postcss">
.source-popover {
  .source-popover-content {
    .popover-title {
      margin-bottom: 8px;
      font-size: 14px;
      font-weight: 600;
      color: #313238;
    }

    .popover-desc {
      margin-bottom: 12px;
      font-size: 12px;
      line-height: 1.6;
      color: #979ba5;
    }

    .popover-link {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-size: 13px;
      color: #3a84ff;
      text-decoration: none;
      cursor: pointer;

      &:hover {
        color: #2673e6;
      }
    }
  }
}
</style>
