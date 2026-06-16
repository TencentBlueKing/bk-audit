<template>
  <bk-dialog
    class="ai-analyzes-dialog"
    dialog-type="show"
    :is-show="isShow"
    :quick-close="false"
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
        @click="handleReport(item)">
        <div class="report-info">
          <div class="report-title">
            {{ item.name }}
          </div>
          <div class="report-desc">
            {{ item.description }}
          </div>
        </div>
        <img
          v-if="item.icon"
          class="report-icon"
          :src="item.icon">
      </div>

      <div
        v-if="otherReports.length"
        class="section-title">
        {{ t('其他可用报告') }}
      </div>

      <div
        v-for="(item, index) in otherReports"
        :key="`other-${index}`"
        class="report-card"
        @click="handleReport(item)">
        <div class="report-info">
          <div class="report-title">
            {{ item.name }}
          </div>
          <div class="report-desc">
            {{ item.description }}
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
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import dayjs from 'dayjs';

  import RiskManageService from '@service/risk-manage';
  import StrategyManageService from '@service/strategy-manage';

  import useRequest from '@hooks/use-request';

  import iconUnion from '@images/Union.svg';
  import iconZonghe from '@images/zonghe.svg';
  import iconZrren from '@images/zrren.svg';

  interface Props {
    total?: number;
    conditionTags?: any[];
    searchParams?: Record<string, any>;
  }
  interface reportsItem {
    description: string;
    is_builtin: boolean;
    name: string;
    priority:  number;
    report_type:  string;
    scenario_id:  number;
    scenario_key:   string;
    icon: string;
  }

  export interface AnalyzeStartPayload {
    title: string;
  }

  const props = withDefaults(
    defineProps<Props>(),
    {
      total: 0,
      conditionTags: () => [],
      searchParams: () => ({}),
    },
  );

  const emit = defineEmits<{
    'analyze-started': [payload: AnalyzeStartPayload];
    'analyze-failed': [payload: { title: string }];
  }>();
  const { t } = useI18n();
  const strategyTagMap = ref<Record<string, string>>({});
  const isShow = ref(false);
  const isCustomExpanded = ref(true);
  const customRequirement = ref('');
  const recommendReports = ref<reportsItem[]>([]);

  const otherReports = ref<reportsItem[]>([]);

  const {
    run: getAiAnalyseList,
  } = useRequest(RiskManageService.getAiAnalyseList, {
    defaultValue: [],
    onSuccess(analyseList) {
      // 根据搜索条件智能推荐报告
      const sortedReports = sortReportsByCondition(analyseList, props.conditionTags);
      // 设置推荐报告和其他报告
      recommendReports.value = sortedReports.recommend;
      otherReports.value = sortedReports.other;
    },
  });

  const hasOperatorCondition = (conditionTags: any[]) => conditionTags.some((tag) => {
    if (tag.fieldName !== 'operator') {
      return false;
    }
    const { value } = tag;
    if (value === undefined || value === null || value === '') {
      return false;
    }
    if (Array.isArray(value)) {
      return value.some(item => item !== undefined && item !== null && item !== '');
    }
    return true;
  });

  // 根据搜索条件推荐报告
  const sortReportsByCondition = (analyseList: any[], conditionTags: any[]) => {
    if (!analyseList || analyseList.length === 0) {
      return { recommend: [], other: [] };
    }

    const iconMap: Record<string, string> = {
      person_investigation: iconZrren,
      trend_summary: iconZonghe,
    };

    const reportsWithIcons = analyseList.map(report => ({
      ...report,
      icon: iconMap[report.scenario_key] || iconUnion,
    }));

    const findReport = (scenarioKey: string) => (
      reportsWithIcons.find(report => report.scenario_key === scenarioKey)
    );

    if (hasOperatorCondition(conditionTags)) {
      const recommend = findReport('person_investigation');
      const other = findReport('trend_summary');
      return {
        recommend: recommend ? [recommend] : [],
        other: other ? [other] : [],
      };
    }

    const recommend = findReport('trend_summary');
    return {
      recommend: recommend ? [recommend] : [],
      other: [],
    };
  };

  const show = () => {
    isShow.value = true;
    isCustomExpanded.value = false;
    customRequirement.value = '';
    getAiAnalyseList();
  };

  // 提交生成分析报告
  const {
    run: getAiAnalyseReport,
  } = useRequest(RiskManageService.getAiAnalyseReport, {
    defaultValue: [],
  });

  // 构建分析范围描述信息
  const buildAnalysisScope = () => props.conditionTags.map((tag) => {
    // 策略id：从策略列表中匹配对应的策略名称
    if (tag.fieldName === 'strategy_id') {
      return {
        label: tag.label,
        value: strategyList.value.find((strategy: any) => tag.value.includes(strategy.value.toString()))?.label,
      };
    }
    // 标签：从标签映射中获取标签名称
    if (tag.fieldName === 'tags') {
      return {
        label: tag.label,
        value: strategyTagMap.value[tag.value],
      };
    }
    return {
      label: tag.label,
      value: tag.value,
    };
  });

  // 提交分析报告请求
  const submitAnalyseReport = (params: Record<string, any>) => {
    const analysisScope = JSON.stringify(buildAnalysisScope());
    const startPayload: AnalyzeStartPayload = {
      title: params.title,
    };
    isShow.value = false;
    emit('analyze-started', startPayload);
    getAiAnalyseReport({
      ...params,
      analysis_scope: analysisScope,
      target_risks_filter: props.searchParams,
    }).catch(() => {
      emit('analyze-failed', { title: params.title });
    });
  };

  const getReportDateSuffix = () => dayjs().format('YYYYMMDD');

  const getOperatorNameFromTags = (conditionTags: any[]) => {
    const operatorTag = conditionTags.find(tag => tag.fieldName === 'operator');
    if (!operatorTag?.value) {
      return '';
    }
    const { value } = operatorTag;
    if (Array.isArray(value)) {
      return value.filter(item => item !== undefined && item !== null && item !== '').join(',');
    }
    return String(value);
  };

  const buildReportTitle = (item: reportsItem) => {
    const dateStr = getReportDateSuffix();
    if (item.scenario_key === 'person_investigation') {
      const operatorName = getOperatorNameFromTags(props.conditionTags);
      return `${operatorName}-${item.name}-${dateStr}`;
    }
    return `${item.name}-${dateStr}`;
  };

  const handleReport = (item: reportsItem) => {
    submitAnalyseReport({
      scenario_key: item.scenario_key,
      report_type: item.report_type,
      title: buildReportTitle(item),
      custom_prompt: '',
    });
  };

  const handleCustomReport = () => {
    if (!customRequirement.value.trim()) return;
    submitAnalyseReport({
      scenario_key: '',
      report_type: 'custom',
      title: '自定义报告',
      custom_prompt: customRequirement.value,
    });
  };
  // 获取标签列表
  useRequest(RiskManageService.fetchRiskTags, {
    defaultParams: {
      noNeedSceneParams: true,
    },
    defaultValue: [],
    manual: true,
    onSuccess: (data) => {
      data.forEach((item) => {
        strategyTagMap.value[item.id] = item.name;
      });
    },
  });
  // 获取策略列表
  const {
    data: strategyList,
  } = useRequest(StrategyManageService.fetchAllStrategyList, {
    manual: true,
    defaultValue: [],
  });
  const toggleCustom = () => {
    isCustomExpanded.value = !isCustomExpanded.value;
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
</style>

<style lang="postcss">
.ai-analyzes-dialog {
  .bk-dialog-footer {
    display: none;
  }
}
</style>
