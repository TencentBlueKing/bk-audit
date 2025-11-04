<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
  Copyright (C) 2023 THL A29 Limited,
  a Tencent company. All rights reserved.
  Licensed under the MIT License (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at http://opensource.org/licenses/MIT
  Unless required by applicable law or agreed to in writing,
  software distributed under the License is distributed on
  an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
  either express or implied. See the License for the
  specific language governing permissions and limitations under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
-->
<template>
  <bk-popover
    placement="bottom"
    theme="light"
    trigger="click">
    <template #default>
      <audit-icon
        v-bk-tooltips="{
          content: t('查看该字段数据统计'),
        }"
        style=" padding-left: 6px;color: #3a84ff"
        type="shujutongji"
        @click="handleClick" />
    </template>
    <template #content>
      <bk-loading :loading="loading">
        <div
          v-if="statisticData.results"
          class="statistic-content">
          <div class="statistic-title">
            <span>
              {{ t('总行数') }}:
              <span class="statistic-title-value">{{ statisticData.results.total_rows[0].total_rows }}</span>
            </span>
            <span style="margin: 0 32px;">
              {{ t('出现行数') }}:
              <span class="statistic-title-value">{{ statisticData.results.non_empty_rows[0].non_empty_rows }}</span>
            </span>
            <span>
              {{ t('日志条数') }}:
              <span class="statistic-title-value">
                {{ ((statisticData.results.non_empty_rows[0].non_empty_rows
                  /statisticData.results.total_rows[0].total_rows) * 100).toFixed(2) }}%
              </span>
            </span>
          </div>
          <template v-if="statisticData.results.max_value">
            <div class="values-container">
              <div class="item">
                {{ t('最大值') }} <span class="item-count">{{ statisticData.results.max_value[0].max_value }}</span>
              </div>
              <div class="item">
                {{ t('最小值') }} <span class="item-count">{{ statisticData.results.min_value[0].min_value }}</span>
              </div>
              <div class="item">
                {{ t('平均值') }} <span class="item-count">{{ statisticData.results.avg_value[0].avg_value }}</span>
              </div>
              <div class="item">
                {{ t('中位数') }} <span class="item-count">{{ statisticData.results.median_value[0].median_value }}</span>
              </div>
            </div>
          </template>
          <template v-else>
            <div class="statistic-stack">
              <div
                id="main"
                style="height: 200px;" />
              <ul class="legend">
                <li
                  v-for="(item, index) in statisticData.results.top_5_echarts_time_series.series"
                  :key="item.name"
                  class="legend-item">
                  <div style="display: flex; align-items: center;">
                    <div
                      :style="{
                        background: option.color[index],
                        width: '12px',
                        height: '12px',
                        marginRight: '6px',
                      }" />
                    {{ item.name }}
                  </div>
                </li>
              </ul>
            </div>
            <div class="statistic-field">
              <div class="title">
                {{ t('去重后字段统计') }}
                <span class="values-number">{{ statisticData.results.top_5_values.length }}</span>
              </div>
              <ul class="field-list">
                <li
                  v-for="(item, index) in statisticData.results.top_5_values"
                  :key="index"
                  class="field-list-item">
                  <div style="display: flex; align-items: center; justify-content: space-between;">
                    <span>{{ item[props.fieldName] }}</span>
                    <div style="color: #2dcb56;">
                      <span>{{ item.count }}{{ t('条') }}</span>
                      <span style="margin-left: 4px;">
                        {{ ((item.count / statisticData.results.total_rows[0].total_rows) * 100).toFixed(2) }}%
                      </span>
                    </div>
                  </div>
                  <bk-progress
                    :percent="(item.count / statisticData.results.total_rows[0].total_rows) * 100"
                    :show-text="false"
                    size="small"
                    theme="success" />
                </li>
              </ul>
            </div>
          </template>
        </div>
        <bk-exception
          v-else
          class="exception-part"
          scene="part"
          type="search-empty">
          {{ t('暂无数据') }}
        </bk-exception>
      </bk-loading>
    </template>
  </bk-popover>
</template>

<script setup lang="ts">
  // import { ref } from 'vue';
  import { LineChart } from 'echarts/charts';
  import {
    GridComponent,
    LegendComponent,
    TitleComponent,
    ToolboxComponent,
    TooltipComponent } from 'echarts/components';
  import * as echarts from 'echarts/core';
  import { UniversalTransition } from 'echarts/features';
  import { CanvasRenderer } from 'echarts/renderers';
  import { nextTick, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import EsQueryService from '@service/es-query';

  import SearchStatisticModel from '@model/es-query/search_statistic';

  import useRequest from '@hooks/use-request';

  interface Props {
    fieldName: string;
    params: Record<string, any>;
  }

  const props = defineProps<Props>();
  const { t } = useI18n();

  echarts.use([
    TitleComponent,
    ToolboxComponent,
    TooltipComponent,
    GridComponent,
    LegendComponent,
    LineChart,
    CanvasRenderer,
    UniversalTransition,
  ]);

  const option = ref({
    title: {
      text: t('TOP5时序图'),
    },
    tooltip: {
      trigger: 'axis',
    },
    grid: {
      left: '5%',
      right: '5%',
      bottom: '5%',
      containLabel: true,
    },
    color: ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de'],
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: [] as string[],
    },
    yAxis: {
      type: 'value',
    },
    series: [] as echarts.EChartsCoreOption['series'],
  });

  const setChart = () => {
    const chart = document.getElementById('main');
    const myChart = echarts.init(chart);
    option.value.xAxis.data = statisticData.value.results.top_5_echarts_time_series.times.map((timestamp) => {
      const date = new Date(timestamp);
      return `${date.getHours().toString()
        .padStart(2, '0')}:${date.getMinutes().toString()
        .padStart(2, '0')}`;
    });
    option.value.series = statisticData.value.results.top_5_echarts_time_series.series.map(value => ({
      name: value.name,
      type: 'line',
      data: value.data,
    }));
    option.value && myChart.setOption(option.value);
  };

  // 获取统计数据
  const {
    data: statisticData,
    run: fetchSearchStatistic,
    loading,
  } = useRequest(EsQueryService.fetchSearchStatistic, {
    defaultValue: new SearchStatisticModel(),
    onSuccess: () => {
      nextTick(() => {
        setChart();
      });
    },
  });

  // 处理点击事件
  const handleClick = () => {
    const params = {
      ...props.params,
      field_name: props.fieldName,
    };
    fetchSearchStatistic(params);
  };
</script>

<style lang="postcss" scoped>
.statistic-content {
  .statistic-title {
    padding-bottom: 10px;
    border-bottom: 1px solid #dcdee5;

    .statistic-title-value {
      font-weight: 700;
    }
  }

  .values-container {
    display: flex;
    margin-top: 12px;
    flex-wrap: wrap;
    gap: 10px;

    .item {
      height: 32px;
      line-height: 32px;
      text-align: center;
      background: #f0f0f0;
      box-sizing: border-box;
      flex: 0 0 calc(50% - 5px);

      .item-count {
        font-weight: 700;
      }
    }
  }

  .statistic-stack {
    margin-top: 12px;
    border-bottom: 1px solid #dcdee5;

    .legend {
      padding: 0 10px;
      padding-bottom: 10px;

      .legend-item {
        padding: 2px 0;
        font-weight: 700;
      }
    }
  }

  .statistic-field {
    margin-top: 12px;

    .title {
      margin-bottom: 12px;
      font-weight: 700;

      .values-number {
        padding: 0 10px;
        color: #979ba5;
        background-color: #f0f1f5;
        border-radius: 10px;
      }
    }
  }
}

.statistic-empty {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100px;
  color: #979ba5;
}
</style>
