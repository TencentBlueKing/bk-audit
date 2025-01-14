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
  <div class="event-table">
    <div class="head">
      <div
        v-for="(item, index) in column"
        :key="index"
        class="item"
        :style="{minWidth: (locale === 'en-US' && index === 0) ? '140px' : '80px'}">
        <span
          v-bk-tooltips="{
            disabled: !item.tips,
            content: item.tips
          }"
          :class="[item.tips ? 'tips' : '']">
          {{ item.label }}
        </span>
      </div>
    </div>
    <template
      v-for="(item, key) in tableData"
      :key="key">
      <div class="body">
        <div
          class="group"
          :style="{minWidth: locale === 'en-US' ? '140px' : '80px'}">
          <span> {{ groupMap[key] }} </span>
        </div>
        <div class="value-row">
          <value-item
            ref="valueItemRef"
            :item="item"
            :select="select" />
        </div>
      </div>
    </template>
  </div>
</template>
<script setup lang='tsx'>
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import DatabaseTableFieldModel from '@model/strategy/database-table-field';
  import StrategyModel from '@model/strategy/strategy';
  import StrategyFieldEvent from '@model/strategy/strategy-field-event';

  import ValueItem from './valueItem.vue';

  import useRequest from '@/hooks/use-request';

  interface Exposes{
    getData: () => StrategyFieldEvent,
    getValue: () => Promise<any>;
  }

  interface Props {
    strategyId: number,
    data: StrategyModel,
    select: Array<DatabaseTableFieldModel>
  }

  const props = defineProps<Props>();

  const { t, locale } = useI18n();
  const valueItemRef = ref();

  const column = [
    { label: t('事件分组') },
    { label: t('字段名称') },
    { label: t('字段显示名') },
    { label: t('重点展示'), tips: t('开启后将在单据里优先展示') },
    { label: t('字段映射'), tips: t('系统字段需要关联到策略，默认按照规则自动从结果字段内获取填充，可修改') },
    { label: t('字段说明'), tips: t('在单据页，鼠标移入label，即可显示字段说明') },
  ];

  const groupMap = {
    event_basic_field_configs: t('基本信息'),
    event_data_field_configs: t('事件结果'),
    event_evidence_field_configs: t('事件证据'),
  };

  const setEditData = (key: 'event_basic_field_configs' | 'event_data_field_configs' | 'event_evidence_field_configs') => {
    if (props.data[key].length && tableData.value[key].length) {
      tableData.value[key] = tableData.value[key].map((item) => {
        const editItem = props.data[key].find(edItem => edItem.field_name === item.field_name);
        if (editItem) {
          return {
            field_name: item.field_name,
            display_name: item.display_name,
            is_priority: editItem.is_priority,
            map_config: item.map_config,
            description: editItem.description,
            example: item.example,
            prefix: '',
          };
        }
        return {
          ...item,
        };
      });
    }
  };

  const {
    data: tableData,
  } = useRequest(StrategyManageService.fetchStrategyEvent, {
    defaultValue: new StrategyFieldEvent(),
    defaultParams: {
      strategy_id: props.strategyId,
    },
    onSuccess: () => {
      // 编辑填充内容（是否重点展示、字段说明）
      setEditData('event_basic_field_configs');
      setEditData('event_data_field_configs');
      setEditData('event_evidence_field_configs');
    },
    manual: true,
  });

  defineExpose<Exposes>({
    getData() {
      return tableData.value;
    },
    getValue() {
      return Promise.all((valueItemRef.value as { getValue: () => any }[])?.map(item => item.getValue()));
    },
  });
</script>
<style lang="postcss" scoped>
.event-table {
  @mixin item-styles {
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
  border-left: 1px solid #dcdee5;
  flex-direction: column;

  .head {
    display: flex;
    height: 42px;
    background-color: #f5f7fa;

    .item {
      @include  item-styles;

      background-color: #f5f7fa;

      &:nth-child(2) {
        width: 190px;
      }

      &:nth-child(3) {
        width: 240px;
      }

      &:nth-child(4) {
        width: 120px;
      }

      &:nth-child(5) {
        width: 240px;
      }

      &:last-child {
        flex: 1;
      }
    }
  }

  .body {
    display: flex;
    min-height: 42px;

    .group {
      @include  item-styles;

      display: flex;
      background-color: #f5f7fa;
      align-items: center;
      justify-content: center;
    }

    .value-row {
      width: calc(100% - 80px);
    }
  }
}
</style>
