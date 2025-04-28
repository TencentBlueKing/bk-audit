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
  <div class="risk-detection">
    <collapse-panel
      class="collapse-card-title"
      :label="t('基础配置')"
      style="margin-top: 14px;">
      <render-info-block class="mt16">
        <render-info-item :label="t('策略名称')">
          {{ data.strategy_name }}
        </render-info-item>
      </render-info-block>
      <render-info-block>
        <render-info-item :label="t('策略标签')">
          <edit-tag :data="data.tags?.map(item=> strategyMap[item] || item) || ''" />
        </render-info-item>
      </render-info-block>
      <render-info-block>
        <render-info-item :label="t('风险等级')">
          <span
            v-if="data.risk_level"
            :style="{
              'background-color': riskLevelMap[data.risk_level].color,
              padding: '3px 8px',
              'border-radius': '3px',
              color: 'white'
            }">
            {{ riskLevelMap[data.risk_level].label }}
          </span>
          <span v-else>--</span>
        </render-info-item>
      </render-info-block>
      <render-info-block
        class="flex "
        style="margin-bottom: 12px;">
        <render-info-item
          :label="t('风险危害')">
          {{ data.risk_hazard || '--' }}
        </render-info-item>
      </render-info-block>
      <render-info-block
        class="flex "
        style="margin-bottom: 12px;">
        <render-info-item
          :label="t('处理指引')">
          {{ data.risk_guidance || '--' }}
        </render-info-item>
      </render-info-block>
    </collapse-panel>
    <collapse-panel
      class="collapse-card-title"
      :label="t('方案')"
      style="margin-top: 24px;">
      <render-info-block class="mt16">
        <render-info-item :label="t('配置方式')">
          <span
            :style="{
              padding: '4px 6px',
              color: data.strategy_type === 'rule' ? '#299E56' : '#E38B02',
              background: data.strategy_type === 'rule' ? '#DAF6E5' : '#FDEED8',
              borderRadius: '2px',
            }">
            {{ strategyTypeTextMap[data.strategy_type] }}
          </span>
        </render-info-item>
      </render-info-block>
      <render-info-block
        v-if="data.strategy_type === 'model'"
        class="mt16">
        <render-info-item :label="t('方案名称')">
          {{ currentControl?.control_name || '--' }} - V{{ data.control_version }}
        </render-info-item>
      </render-info-block>
      <!-- 自定义规则审计 -->
      <template v-if="data.strategy_type === 'rule'">
        <render-info-block class="mt16">
          <render-info-item :label="t('数据源')">
            <span>{{ commonData.rule_audit_config_type.
              find(item => item.value === data.configs.config_type)?.label }}/</span>
            <template v-if="data.configs.config_type === 'LinkTable'">
              {{ LinkDataDetail.name }}
            </template>
            <template v-else>
              {{ getDataSourceText(data.configs) }}
            </template>
          </render-info-item>
        </render-info-block>
        <render-info-block class="mt16">
          <render-info-item :label="t('预期结果')">
            <template v-if="data.configs.select.length">
              <div class="panel-edit flex">
                <div
                  v-for="element in data.configs.select"
                  :key="element.raw_name + element.aggregate + element.display_name"
                  class="query-field flex-center-wrap">
                  {{ getMetricName(element) }}
                </div>
              </div>
            </template>
            <div v-else>
              --
            </div>
          </render-info-item>
        </render-info-block>
        <render-info-block>
          <render-info-item :label="t('风险发现规则')">
            <div class="condition-render-item">
              <div
                v-if="data.configs.where.conditions.length > 1"
                class="condition-equation-wrap">
                <span class="condition-equation first-equation">
                  {{ data.configs.where.connector }}
                </span>
              </div>
              <div style="flex: 1; margin-bottom: 20px;">
                <template
                  v-for="(item, index) in data.configs.where.conditions"
                  :key="index">
                  <div
                    v-for="(childItem, childIndex) in item.conditions"
                    :key="childIndex"
                    class="condition-item"
                    :style="{ marginTop: index ? '12px' : '0px' }">
                    <div
                      v-if="childIndex"
                      class="condition-equation mr4 mb4">
                      {{ item.connector }}
                    </div>
                    <template v-if="childItem.condition.field">
                      <div class="condition-key mr4 mb4">
                        {{ childItem.condition.field.display_name }}
                      </div>
                      <div class="condition-method mr4 mb4">
                        {{ commonData.rule_audit_condition_operator.
                          find(item => item.value === childItem.condition.operator)?.label }}
                      </div>
                    </template>
                    <template v-if="childItem.condition.filters.length">
                      <div
                        v-for="(value, valIndex) in childItem.condition.filters"
                        :key="valIndex"
                        class="condition-value mr4 mb4">
                        {{ value }}
                      </div>
                    </template>
                    <template v-else-if="childItem.condition.filter">
                      <div class="condition-value mr4 mb4">
                        {{ childItem.condition.filter }}
                      </div>
                    </template>
                  </div>
                </template>
              </div>
            </div>
          </render-info-item>
        </render-info-block>
        <render-info-block>
          <render-info-item :label="t('调度周期')">
            <template v-if="data.configs.schedule_config">
              <span>
                {{ data?.configs.schedule_config.count_freq }}
              </span>
              <span>
                {{ commonData.offset_unit
                  .find((item) =>
                    item.value === data.configs.schedule_config.schedule_period)?.label }}
              </span>
            </template>
            <span v-else>
              --
            </span>
          </render-info-item>
        </render-info-block>
      </template>

      <bk-loading :loading="controlLoading">
        <component
          :is="comMap[currentControl?.control_type_id || '--']"
          ref="comRef"
          :data="data" />
      </bk-loading>
    </collapse-panel>
  </div>
</template>
<script setup lang="ts">
  import {
    computed,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import LinkDataManageService from '@service/link-data-manage';
  import MetaManageService from '@service/meta-manage';
  import StrategyManageService from '@service/strategy-manage';

  import LinkDataDetailModel from '@model/link-data/link-data-detail';
  import CommonDataModel from '@model/strategy/common-data';
  import DatabaseTableFieldModel from '@model/strategy/database-table-field';
  import type StrategyModel from '@model/strategy/strategy';

  import useRequest from '@hooks/use-request';

  import EditTag from '@components/edit-box/tag.vue';

  import RenderAiops from './aiops/index.vue';
  import collapsePanel from './collapse-panel.vue';
  import FilterCondition from './normal/filter-condition.vue';
  import RenderInfoBlock from './render-info-block.vue';
  import RenderInfoItem from './render-info-item.vue';

  interface Props {
    data: StrategyModel,
    strategyMap: Record<string, string>
  }

  const props = defineProps<Props>();
  const { t } = useI18n();
  const currentControl = computed(() => controlList.value
    .find(item => item.control_id === props.data.control_id));// 当前方案
  const comMap: Record<string, any> = {
    BKM: FilterCondition,
    AIOps: RenderAiops,
  };

  const riskLevelMap: Record<string, {
    label: string,
    color: string,
  }> =  {
    HIGH: {
      label: t('高'),
      color: '#ea3636',
    },
    MIDDLE: {
      label: t('中'),
      color: '#ff9c01',
    },
    LOW: {
      label: t('低'),
      color: '#979ba5',
    },
  };

  const strategyTypeTextMap = {
    rule: t('自定义规则审计'),
    model: t('引入模型审计'),
  } as Record<string, string>;

  const {
    data: commonData,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: new CommonDataModel(),
    manual: true,
  });

  const getMetricName = (element: DatabaseTableFieldModel) => {
    const item = commonData.value.rule_audit_aggregate_type.find(item => item.value === element.aggregate);
    return `[${item?.label || t('不聚合')}] ${element.display_name}`;
  };

  const findLabelByValue = (data: Array<{
    label: string,
    value: string,
    children?: Array<{
      label: string,
      value: string,
    }>
  }>, searchValue = '', parentLabel = '') => {
    for (const item of data) {
      // 如果当前项的值匹配，返回当前项的标签
      if (item.value === searchValue) {
        return parentLabel ? `${parentLabel}/${item.label}` : item.label;
      }

      // 如果有子项，递归搜索
      if (item.children && item.children.length) {
        const result: string = findLabelByValue(item.children, searchValue, item.label);
        if (result) {
          return result;
        }
      }
    }
    return '';
  };

  const getDataSourceText = (config: StrategyModel['configs']) => {
    if (!tableData.value.length) return;
    if (config.config_type === 'BuildIn' || config.config_type === 'BizRt') {
      return findLabelByValue(tableData.value, config.data_source?.rt_id);
    }
    const names = systemList.value
      .filter(item => config.data_source?.system_ids.includes(item.id))
      .map(item => item.name);
    // 使用 ' + ' 连接名称
    return names.join(' + ');
  };

  // 获取方案列表
  const {
    data: controlList,
    loading: controlLoading,
  } = useRequest(StrategyManageService.fetchControlList, {
    defaultValue: [],
    manual: true,
  });

  // 获取tableid
  const {
    data: tableData,
    run: fetchTable,
  } = useRequest(StrategyManageService.fetchTable, {
    defaultValue: [],
  });

  // 获取系统
  const {
    data: systemList,
    run: fetchSystemWithAction,
  } = useRequest(MetaManageService.fetchSystemWithAction, {
    defaultValue: [],
  });

  // 获取关联表详情
  const {
    data: LinkDataDetail,
    run: fetchLinkDataSheetDetail,
  } = useRequest(LinkDataManageService.fetchLinkDataDetail, {
    defaultValue: new LinkDataDetailModel(),
  });

  watch(() => props.data, (data) => {
    if (data.strategy_type !== 'rule') return;
    if (data.configs.config_type !== 'LinkTable') {
      fetchTable({
        table_type: data.configs.config_type,
      });
    } else {
      fetchLinkDataSheetDetail({
        uid: data.link_table_uid,
      });
    }
    if (data.configs.config_type === 'EventLog') {
      fetchSystemWithAction();
    }
    if (data.configs.having && data.configs.having.conditions.length > 0) {
      // 将having条件合并到where条件中, conditions根据item.index进行排序合并
      // eslint-disable-next-line no-param-reassign
      data.configs.where.conditions = data.configs.where.conditions.concat(data.configs.having.conditions);
      data.configs.where.conditions.sort((a, b) => a.index - b.index);
      // eslint-disable-next-line no-param-reassign
      data.configs.having.conditions = [];
    }
  }, {
    immediate: true,
  });

</script>
<style scoped lang="postcss">
.risk-detection {
  .panel-edit {
    position: relative;
    min-height: 32px;
    padding: 0 3px;
    background: #f5f7fa;
    border-radius: 2px;
    flex-wrap: wrap;

    .query-field {
      position: relative;
      height: 26px;
      margin: 3px 4px 3px 0;
      line-height: 26px;
      color: #fff;
      white-space: nowrap;
      background: #1eab8b;
      border-radius: 2px;

      &:hover {
        .query-field-remove {
          visibility: visible;
        }
      }

      .dragging-handle {
        padding: 0 4px;
        cursor: move;
      }

      .query-field-remove {
        padding: 0 4px;
        text-align: center;
        visibility: hidden;
      }
    }

    .flex-center-wrap {
      display: flex;
      align-items: center;
      justify-content: center;
      flex-wrap: wrap;
    }
  }

  .condition-render-item {
    display: flex;

    .mb4 {
      margin-bottom: 4px;
    }

    .condition-equation-wrap {
      position: relative;
      width: 50px;
    }

    .condition-equation {
      padding: 2px 8px;
      color: #3a84ff;
      text-align: center;
      background: #edf4ff;
      border-radius: 2px;
    }

    .first-equation {
      position: absolute;
      top: calc(50% - 10px);
    }

    .condition-item {
      display: flex;
      flex-wrap: wrap;

      .condition-key {
        padding: 2px 8px;
        color: #788779;
        background: #dde9de;
        border-radius: 2px;
      }

      .condition-method {
        padding: 2px 8px;
        color: #fe9c00;
        background: #fff1db;
        border-radius: 2px;
      }

      .condition-value {
        padding: 2px 8px;
        color: #63656e;
        background: #f0f1f5;
        border-radius: 2px;
      }
    }
  }
}
</style>
