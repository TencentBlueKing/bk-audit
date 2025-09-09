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
  <div class="risk-display">
    <collapse-panel
      class="collapse-card-title"
      :label="t('风险单信息')"
      style="margin-top: 14px;">
      <render-info-block class="mt16">
        <render-info-item :label="t('风险单标题')">
          {{ data.risk_title || '--' }}
        </render-info-item>
      </render-info-block>
    </collapse-panel>
    <collapse-panel
      class="collapse-card-title"
      :label="t('事件信息')"
      style="margin-top: 24px;">
      <render-info-block class="mt16">
        <render-info-item :label="t('事件信息')">
          <div class="event-table">
            <div class="head">
              <div
                v-for="(item, index) in columns"
                :key="index"
                class="header-cell"
                :class="getHeaderClass(item.key)"
                :style="{
                  minWidth: (locale === 'en-US' && index === 0) ? '140px' : '80px',
                  borderRight: index === 0 ? '1px solid #dcdee5' : ''
                }">
                {{ item.label }}
              </div>
            </div>
            <template
              v-for="(item, key) in tableData"
              :key="key">
              <!-- strategyType === 'rule'时不显示 event_evidence_field_configs -->
              <template
                v-if="(data.strategy_type === 'rule' && key === 'event_evidence_field_configs')
                  || key === 'risk_meta_field_config'" />
              <div
                v-else
                class="table-section">
                <div
                  class="group-cell"
                  :style="{minWidth: locale === 'en-US' ? '140px' : '80px'}">
                  <span>{{ groupMap[key] }}</span>
                </div>
                <div class="rows-container">
                  <value-item
                    :all-tools-data="allToolsData"
                    :data="data"
                    :item="item" />
                </div>
              </div>
            </template>
          </div>
        </render-info-item>
      </render-info-block>
    </collapse-panel>
  </div>
</template>
<script setup lang="ts">
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ToolManageService from '@service/tool-manage';

  import type StrategyModel from '@model/strategy/strategy';
  import StrategyFieldEvent from '@model/strategy/strategy-field-event';

  import collapsePanel from './collapse-panel.vue';
  import RenderInfoBlock from './render-info-block.vue';
  import RenderInfoItem from './render-info-item.vue';
  import ValueItem from './valueItem.vue';

  import useRequest from '@/hooks/use-request';

  interface Props {
    data: StrategyModel,
  }

  const props = defineProps<Props>();
  const { t, locale } = useI18n();

  //  strategyType === 'rule'时显示全部列，否则排除 “字段映射”
  const columns = computed(() => {
    const initColumns = [
      { label: t('事件分组') },
      { key: 'field_name', label: t('字段名称') },
      { key: 'display_name', label: t('字段显示名') },
      { key: 'is_show', label: t('在单据中展示') },
      { key: 'is_priority', label: t('重点展示'), tips: t('设为重点展示的字段将在风险单据中直接显示，其他字段将被折叠收起') },
      { key: 'map_config', label: t('字段关联'), tips: t('系统字段需要关联到策略，默认按照规则自动从结果字段内获取填充，可修改') },
      { key: 'enum_mappings', label: t('字段值映射'), tips: t('为储存值配置可读的展示文本') },
      { key: 'drill_config', label: t('字段下钻'), tips: t('为字段配置下钻工具后，可以在风险单据中点击该字段，查询其关联信息') },
      { key: 'description', label: t('字段说明'), tips: t('在单据页，鼠标移入label，即可显示字段说明') },
    ];

    return props.data.strategy_type === 'rule'
      ? initColumns
      : initColumns.filter((_, index) => index !== 4);
  });

  //  strategyType === 'rule'时不显示 event_evidence_field_configs
  const groupMap = computed(() => (props.data.strategy_type === 'rule'
    ? {
      event_basic_field_configs: t('基本信息'),
      event_data_field_configs: t('事件结果'),
    } : {
      event_basic_field_configs: t('基本信息'),
      event_data_field_configs: t('事件结果'),
      event_evidence_field_configs: t('事件证据'),
    }));

  const tableData = computed(() => {
    const data = {
      event_basic_field_configs: props.data.event_basic_field_configs,
      event_data_field_configs: props.data.event_data_field_configs,
      event_evidence_field_configs: props.data.event_evidence_field_configs,
      risk_meta_field_config: props.data.risk_meta_field_config,
    };
    return new StrategyFieldEvent(data);
  });

  const getHeaderClass = (valueKey: string | undefined) => ({
    'field-name': valueKey === 'field_name',
    'display-name': valueKey === 'display_name',
    'is-priority': valueKey === 'is_priority' || valueKey === 'is_show'  || valueKey === 'enum_mappings',
    'map-config': valueKey === 'map_config',
    'drill-config': valueKey === 'drill_config',
    description: valueKey === 'description',
  });

  const {
    data: allToolsData,
  } = useRequest(ToolManageService.fetchAllTools, {
    defaultValue: [],
    manual: true,
  });
</script>
<style lang="postcss" scoped>
.risk-display {
  .event-table {
    @mixin cell-base {
      display: flex;
      padding: 0 12px;
      border-right: 1px solid #dcdee5;
      border-bottom: 1px solid #dcdee5;
      align-items: center;
    }

    display: flex;
    margin-bottom: 10px;
    color: #63656e;
    border-top: 1px solid #dcdee5;
    border-right: 1px solid #dcdee5;
    border-left: 1px solid #dcdee5;
    flex-direction: column;

    .head {
      display: flex;
      height: 42px;
      background-color: #f5f7fa;

      .header-cell {
        @include cell-base;

        background-color: #f5f7fa;

        &.field-name {
          width: 100px;
          background-color: #f5f7fa;
        }

        &.display-name {
          width: 100px;
          background-color: #f5f7fa;
        }

        &.is-priority {
          width: 80px;
        }

        &.map-config {
          width: 110px;
        }

        &.drill-config {
          width: 110px;
        }

        &:last-child {
          flex: 1;
        }
      }
    }

    .table-section {
      display: flex;
      min-height: 42px;

      .group-cell {
        @include cell-base;

        display: flex;
        background-color: #f5f7fa;
        align-items: center;
        justify-content: center;
      }

      .rows-container {
        width: calc(100% - 80px);
      }
    }
  }
}
</style>
