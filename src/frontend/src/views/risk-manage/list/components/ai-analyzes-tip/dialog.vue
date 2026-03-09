<template>
  <bk-dialog
    class="ai-analyzes-dialog"
    dialog-type="show"
    :is-show="isShow"
    :title="t('智能分析')"
    width="680"
    @closed="() => isShow = false"
    @confirm="() => isShow = false">
    <div class="ai-analyzes-dialog-content">
      <div class="subtitle">
        {{ t('基于当前') }} <span class="highlight">{{ total }}</span> {{ t('条风险数据，为您推荐以下分析报告：') }}
      </div>

      <div
        v-for="(item, index) in recommendReports"
        :key="`recommend-${index}`"
        class="report-card recommend"
        @click="handleReport(item.title)">
        <div class="report-info">
          <div class="report-title">
            {{ item.title }}
          </div>
          <div class="report-desc">
            {{ item.desc }}
          </div>
        </div>
        <img
          v-if="item.icon"
          class="report-icon"
          :src="item.icon">
      </div>

      <div class="section-title">
        {{ t('其他可用报告') }}
      </div>

      <div
        v-for="(item, index) in otherReports"
        :key="`other-${index}`"
        class="report-card"
        @click="handleReport(item.title)">
        <div class="report-info">
          <div class="report-title">
            {{ item.title }}
          </div>
          <div class="report-desc">
            {{ item.desc }}
          </div>
        </div>
        <img
          v-if="item.icon"
          class="report-icon"
          :src="item.icon">
      </div>

      <div class="divider-wrapper">
        <div class="divider-line" />
        <div class="divider-text">
          {{ t('以上报告不满足需求？') }}
        </div>
        <div class="divider-line" />
      </div>

      <div class="custom-analysis">
        <div
          class="custom-header"
          @click="toggleCustom">
          <audit-icon
            class="collapse-icon"
            :type="isCustomExpanded ? 'angle-fill-down' : 'angle-fill-rignt'" />
          <span class="custom-title">{{ t('自定义分析') }}</span>
          <span class="custom-desc">{{ t('（输入任意分析需求，AI为您定制报告）') }}</span>
        </div>
        <div
          v-show="isCustomExpanded"
          class="custom-content">
          <div class="custom-input-wrapper">
            <bk-input
              v-model="customRequirement"
              class="custom-input"
              :placeholder="t('输入你想分析的内容，例如：分析张三在英雄联盟业务的资产转移报告')"
              :rows="3"
              type="textarea" />
            <bk-button
              class="custom-analysis-btn"
              theme="primary"
              @click="handleCustomReport">
              {{ t('分析') }}
            </bk-button>
          </div>
        </div>
      </div>
    </div>
  </bk-dialog>

  <!-- 分析中加载弹窗 -->
  <bk-dialog
    class="ai-analyzing-dialog"
    dialog-type="show"
    :esc-close="false"
    :is-show="isAnalyzing"
    :show-header="false"
    width="450"
    @closed="() => isAnalyzing = false"
    @confirm="() => isAnalyzing = false">
    <div class="analyzing-content">
      <div class="loading-icon-wrapper">
        <bk-loading
          loading
          mode="spin"
          size="large"
          theme="primary" />
      </div>
      <div class="analyzing-title">
        {{ t('AI 正在分析中...') }}
      </div>
      <div class="analyzing-desc">
        {{ t('正在对') }} {{ total }} {{ t('条风险数据进行深度分析，请稍等片刻') }}
      </div>
    </div>
  </bk-dialog>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import iconUnion from '@images/Union.svg';
  import iconZonghe from '@images/zonghe.svg';
  import iconZrren from '@images/zrren.svg';

  interface Props {
    total?: number;
  }
  withDefaults(defineProps<Props>(), {
    total: 0,
  });

  const { t } = useI18n();

  const isShow = ref(false);
  const isCustomExpanded = ref(true);
  const customRequirement = ref('');
  const isAnalyzing = ref(false);

  // 模拟后台返回的数据
  const recommendReports = ref([
    {
      title: t('责任人行为调查分析报告'),
      desc: t('分析 张三 的行为链分析、风险关联分析、意图判断、关联人员挖掘、建议下一步调查、风险影响评估'),
      icon: iconZrren,
    },
  ]);

  const otherReports = ref([
    {
      title: t('风险综合分析报告'),
      desc: t('根因归纳、风险聚类、异常识别、趋势解读、关联分析、治理建议'),
      icon: iconZonghe,
    },
    {
      title: t('风险态势总结报告'),
      desc: t('自然语言总结、重点事件提炼、风险预判'),
      icon: iconUnion,
    },
  ]);

  const show = () => {
    isShow.value = true;
    isCustomExpanded.value = false;
    customRequirement.value = '';
  };

  const handleReport = (title: string) => {
    isAnalyzing.value = true;
    console.log('Selected report:', title);
    // 模拟分析完成
    // setTimeout(() => {
    //   isAnalyzing.value = false;
    // }, 2000);
  };

  const toggleCustom = () => {
    isCustomExpanded.value = !isCustomExpanded.value;
  };

  const handleCustomReport = () => {
    if (!customRequirement.value.trim()) return;
    isAnalyzing.value = true;

    // // 模拟分析完成
    // setTimeout(() => {
    //   isAnalyzing.value = false;
    // }, 2000);
  };

  defineExpose({
    show,
  });
</script>

<style lang="postcss" scoped>
.ai-analyzes-dialog-content {
  padding-bottom: 8px;
  font-size: 12px;
  color: #63656e;

  .subtitle {
    margin-bottom: 16px;
    font-size: 12px;

    .highlight {
      margin: 0 2px;
      font-weight: bold;
      color: #3a84ff;
    }
  }

  .report-card {
    position: relative;
    padding: 16px 20px;
    margin-bottom: 12px;
    overflow: hidden;
    cursor: pointer;
    background: linear-gradient(90deg, #f0f1f5 0%, #fafbfd 100%);
    background-color: #fff;
    border: 1px solid #dcdee5;
    border-radius: 2px;
    transition: all .2s;

    &:hover {
      background: linear-gradient(90deg, #eaf3ff 0%, #fafdff 100%);
      border-color: #3a84ff;
      box-shadow: 0 2px 4px 0 rgb(0 0 0 / 10%);

    }

    &.recommend {
      border-color: #c4d9ff;

      .report-title {
        font-weight: bold;
      }
    }

    .report-title {
      margin-bottom: 8px;
      font-size: 14px;
      font-weight: 700;
      color: #313238;
    }

    .report-desc {
      padding-right: 60px; /* 留出图标位置 */
      line-height: 18px;
      color: #979ba5;
    }

    .report-icon {
      position: absolute;
      top: 50%;
      right: 20px;
      width: 60px;
      height: 60px;
      pointer-events: none;
      transform: translateY(-50%);
    }
  }

  .section-title {
    margin: 24px 0 16px;
    font-size: 12px;
    color: #63656e;
  }

  .divider-wrapper {
    display: flex;
    align-items: center;
    margin: 24px 0 16px;

    .divider-line {
      flex: 1;
      height: 1px;
      background-color: #dcdee5;
    }

    .divider-text {
      padding: 0 16px;
      color: #979ba5;
    }
  }

  .custom-analysis {
    .custom-header {
      display: flex;
      align-items: center;
      cursor: pointer;
      user-select: none;

      .collapse-icon {
        margin-right: 6px;
        font-size: 16px;
        color: #979ba5;
        transition: transform .2s;
      }

      .custom-title {
        font-size: 14px;
        font-weight: 700;
        color: #313238;
      }

      .custom-desc {
        color: #979ba5;
      }
    }

    .custom-content {
      margin-top: 16px;

      .custom-input-wrapper {
        position: relative;
        display: flex;
        align-items: flex-end; /* 改为底部对齐 */
        width: 100%;
        border: 1px solid #dcdee5;
        border-radius: 2px;
        transition: all .2s;

        &:focus-within {
          background: linear-gradient(white, white) padding-box,
            linear-gradient(90deg, #a469ff 0%, #1cc2fe 100%) border-box;
          border-color: transparent;
        }

        .custom-input {
          background: transparent;
          border: none;
          box-shadow: none;
          flex: 1;

          :deep(.bk-textarea) {
            min-height: 80px;
            padding-right: 80px; /* 留出按钮位置 */
            padding-bottom: 40px; /* 给底部留出空间，避免文字与按钮重叠 */
            background: transparent;
            border: none;
            resize: none;
          }
        }

        .custom-analysis-btn {
          position: absolute;
          right: 8px;
          bottom: 8px; /* 固定在右下角 */
          height: 32px;
          min-width: 64px;
        }
      }
    }
  }
}

/* 分析中弹窗样式 */
.ai-analyzing-dialog {
  :deep(.bk-modal-content) {
    height: 180px;
    padding: 40px 24px;
  }

  :deep(.bk-dialog-footer) {
    display: none;
  }

  .analyzing-content {
    position: absolute;
    top: -50px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;

    .loading-icon-wrapper {
      margin-bottom: 24px;

      .loading-icon {
        font-size: 60px;
        color: #6ba3ff;
        animation: spin 1.5s linear infinite;
      }
    }

    .analyzing-title {
      margin-bottom: 16px;
      font-size: 20px;
      font-weight: 500;
      color: #313238;
    }

    .analyzing-desc {
      font-size: 14px;
      color: #63656e;
    }
  }
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>

<style lang="postcss">
.ai-analyzes-dialog {
  .bk-dialog-footer {
    display: none;
  }
}
</style>
