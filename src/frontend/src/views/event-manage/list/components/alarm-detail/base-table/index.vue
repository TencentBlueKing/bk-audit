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
  <render-list
    ref="listRef"
    :columns="tableColumn"
    :data-source="dataSource"
    is-need-hide-clear-search-tip />
</template>

<script setup lang='tsx'>
  import type { Column } from 'bkui-vue/lib/table/props';
  import dayjs from 'dayjs';
  import {
    onMounted,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import EventManageService from '@service/event-manage';
  import StrategyManageService from '@service/strategy-manage';

  import type EventModel from '@model/event/event';
  import type RiskModel from '@model/event/risk';

  import useRequest from '@hooks/use-request';

  interface Props{
    alarmData: RiskModel,
  }
  const props = defineProps<Props>();

  const tableColumn  = [
    {
      label: () => t('事件ID'),
      minWidth: 120,
      showOverflowTooltip: true,
      render: ({ data }: {data: EventModel}) => (data.event_id || `${data.strategy_id}-${data.raw_event_id}`),
    },
    {
      label: () => t('事件描述'),
      width: 160,
      showOverflowTooltip: true,
      render: ({ data }: { data: EventModel }) => (data.event_content || '--'),
    },
    {
      label: () => t('原始事件ID'),
      field: () => 'raw_event_id',
      width: 160,
      showOverflowTooltip: true,
    },
    {
      label: () => t('策略名称(策略ID)'),
      field: () => 'strategy_id',
      width: 200,
      showOverflowTooltip: true,
      render: ({ data }: { data: EventModel }) => {
        const label = strategyList.value.find(item => item.value === data.strategy_id)?.label;
        return (`${label}(${data.strategy_id})` || '--');
      },
    },
    {
      label: () => t('事件产生时间'),
      width: 170,
      render: ({ data }: { data: EventModel }) => {
        if (data.event_time) {
          return dayjs(data.event_time).format('YYYY-MM-DD HH:mm:ss');
        }
        return '--';
      },
    },
    {
      label: () => t('事件来源'),
      showOverflowTooltip: true,
      width: 150,
      render: ({ data }: { data: EventModel }) => (data.event_source || '--'),
    },
    {
      label: () => t('责任人'),
      width: 120,
      showOverflowTooltip: true,
      render: ({ data }: { data: EventModel }) => (data.operator || '--'),
    },
  ] as Column[];
  const dateTime = [
    dayjs(Date.now() - (86400000 * 14)).format('YYYY-MM-DD HH:mm:ss'),
    dayjs().format('YYYY-MM-DD HH:mm:ss'),
  ];

  const dataSource = EventManageService.fetchEventList;
  const { t } = useI18n();
  const listRef = ref();

  // 策略列表
  const {
    data: strategyList,
  } = useRequest(StrategyManageService.fetchAllStrategyList, {
    defaultValue: [],
    manual: true,
  });

  onMounted(() => {
    listRef.value.fetchData({
      page: 1,
      start_time: dateTime[0],
      end_time: dateTime[1],
      strategy_id: props.alarmData.strategy_id,
      raw_event_id: props.alarmData.raw_event_id,
    });
  });

</script>
<!-- <style scoped>

</style> -->
