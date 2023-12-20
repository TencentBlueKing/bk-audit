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
  <div class="risk-manage-detail-linkevent-part">
    <bk-loading :loading="listLoading">
      <render-list
        ref="listRef"
        :border="['row']"
        :columns="column"
        :data-source="dataSource"
        is-need-hide-clear-search-tip />
    </bk-loading>
  </div>

  <!-- 事件证据 -->
  <audit-sideslider
    ref="sidesliderRef"
    v-model:isShow="showEventEvidenceSlider"
    :show-footer="false"
    show-header-slot
    title=""
    :width="960">
    <template #header>
      <div>
        <span> {{ t('事件证据') }}</span>
        <span style="padding-left: 8px;margin-left: 8px;font-size: 12px;color: #979ba5;border-left: 1px solid #dcdee5;">
          {{ t('事件ID：') }}{{ eventItem.event_id || `${eventItem.strategy_id}-${eventItem.raw_event_id }` }}
        </span>
      </div>
    </template>
    <div style="padding: 24px 40px;">
      <bk-table
        :border="['row']"
        class="evidence-table"
        :columns="evidenceColumn"
        :data="evidenceData" />
    </div>
  </audit-sideslider>
  <audit-sideslider
    ref="sidesliderRef"
    v-model:isShow="showEventDataSlider"
    :show-footer="false"
    show-header-slot
    title=""
    :width="960">
    <template #header>
      {{ t('事件数据字段') }}
    </template>
    <div style="padding: 24px 40px;">
      <bk-table
        :border="['row']"
        class="evidence-table"
        :columns="eventDataColumn"
        :data="eventDataList" />
    </div>
  </audit-sideslider>
</template>

<script setup lang='tsx'>
  import dayjs from 'dayjs';
  import {
    nextTick,
    ref,
    watch,
  } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';

  import EventManageService from '@service/event-manage';

  import EventModel from '@model/event/event';
  import type RiskManageModel from '@model/risk/risk';

  import Tooltips from '@components/show-tooltips-text/index.vue';

  interface Props{
    strategyList: Array<{
      label: string,
      value: number
    }>,
    data: RiskManageModel
  }
  const props = defineProps<Props>();
  const dataSource = EventManageService.fetchEventList;
  const { t } = useI18n();
  const column = [
    {
      label: () => t('事件 ID'),
      showOverflowTooltip: true,
      render: ({ data }: { data: EventModel }) => <span>
        {(data.event_id || `${data.strategy_id}-${data.raw_event_id}`)}
      </span>,
    },
    {
      label: () => t('事件描述'),
      showOverflowTooltip: true,
      render: ({ data }: { data: EventModel }) => (data.event_content || '--'),
    },
    {
      label: () => t('命中策略(ID)'),
      field: () => 'event_content',
      render: ({ data }: { data: EventModel }) => {
        const label = props.strategyList.find(item => item.value === data.strategy_id)?.label;
        const to = {
          name: 'strategyList',
          query: {
            strategy_id: data.strategy_id,
          },
        };
        return label ? (
          <router-link to={to} target='_blank'>
            <Tooltips data={(`${label}(${data.strategy_id})`)} />
          </router-link>
          ) : (
          <span>--</span>
        );
      },
    },
    {
      label: () => t('责任人'),
      field: () => 'event_content',
      showOverflowTooltip: true,
      render: ({ data }: { data: EventModel }) => (data.operator || '--'),
    },
    {
      label: () => t('事件数据字段'),
      field: () => 'event_content',
      showOverflowTooltip: true,
      render: ({ data }: { data: EventModel }) => {
        if (data.event_data) {
          return <a onClick={() => handleShowEventData(data)}>{getStrByObject(data.event_data)}</a>;
        }
        return '--';
      }
      ,
    },
    {
      label: () => t('事件证据'),
      field: () => 'event_evidence',
      // showOverflowTooltip: true,
      render: ({ data }: { data: EventModel }) => {
        if (data.event_evidence) {
          return <a onClick={() => handleShowEvidence(data)}>{data.event_evidence}</a>;
        }
        return (<a>--</a>);
      },
    },
    {
      label: () => t('发现时间'),
      width: 170,
      render: ({ data }: { data: EventModel }) => {
        if (data.event_time) {
          return dayjs(data.event_time).format('YYYY-MM-DD HH:mm:ss');
        }
        return '--';
      },
    },
  ];

  const initEvidenceColumn = [
    {
      label: () => t('账号名 (account_name)'),
      field: () => 'account_name',
    },
    {
      label: () => t('账号所属人 (account_owner)'),
      field: () => 'account_owner',
    },
    {
      label: () => t('账号创建事件 (create_time)'),
      field: () => 'create_time',
    },
  ] as any[];


  const evidenceColumn = ref(initEvidenceColumn);
  const evidenceData = ref<Record<string, any>[]>([]);

  const eventDataColumn = ref([
    {
      label: () => t('字段'),
      field: () => 'key',
      render: ({ data }: { data: {key: string} }) => <Tooltips data = { data.key} />,
    },
    {
      label: () => t('字段值'),
      field: () => 'val',
      render: ({ data }: { data: { val: string, hasTooltips: boolean } }) => (
        data.hasTooltips
          ? <div
            v-bk-tooltips={{
              content: data.val,
              placement: 'top',
              extCls: 'val-tooltips',
            }}
            class='val-tooltips-text'>
            { data.val || '--' }
          </div> : <div class='val-tooltips-text'> { data.val || '--' } </div>
      ),
    },
  ]);
  const eventDataList = ref<Record<string, any>[]>([]);

  const showEventEvidenceSlider = ref(false);
  const showEventDataSlider = ref(false);
  const listRef = ref();
  const listLoading = ref(false);
  const eventItem = ref(new EventModel());

  const getStrByObject = (data: Record<string, any>) => {
    const strList: string[] = [];
    Object.keys(data).forEach((key) => {
      strList.push(`${key} : ${data[key]}`);
    });
    return strList.join('\n');
  };
  // 事件数据字段
  const handleShowEventData = (data: EventModel) => {
    showEventDataSlider.value = true;
    const tableData = Object.keys(data.event_data).map((key) => {
      const val = data.event_data[key] ? JSON.stringify(data.event_data[key]) : '';
      return {
        key,
        val,
        hasTooltips: hasTooltips(val),
      };
    });
    eventDataList.value = tableData;
  };
  // 判断数据字段是否显示tooltips
  const hasTooltips = (text: string) => {
    const tempDiv = document.createElement('div');
    // 防止span影响页面布局
    tempDiv.style.position = 'absolute';
    tempDiv.style.whiteSpace = 'nowrap';
    tempDiv.style.visibility = 'hidden';
    tempDiv.textContent = text;
    document.body.appendChild(tempDiv);
    const width = tempDiv.offsetWidth;
    // 移除临时的span元素
    document.body.removeChild(tempDiv);
    return width > 300;
  };
  const handleShowEvidence = (data: EventModel) => {
    const evidenceList = JSON.parse(data.event_evidence) as Record<string, any>[];
    if (evidenceList && evidenceList.length) {
      evidenceColumn.value = [];
      Object.keys(evidenceList[0]).forEach((key, index) => {
        const params: Record<string, any> = {
          label: () => key,
          field: () => key,
          showOverflowTooltip: true,
          render: ({ data }: { data: Record<string, any> }) => JSON.stringify(data[key]) || '--',
        };
        if (index < 4) {
          params.minWidth = index === 0 ? 260 : 200;
        } else {
          params.minWidth = 100;
        }
        evidenceColumn.value.push(params);
      });
    } else {
      evidenceColumn.value = initEvidenceColumn;
    }
    evidenceData.value = evidenceList || [];
    eventItem.value = data;
    showEventEvidenceSlider.value = true;
  };
  watch(() => props.data, (data) => {
    if (data) {
      nextTick(() => {
        if (listRef.value) {
          listRef.value.fetchData({
            start_time: data.event_time,
            end_time: data.event_end_time,
            risk_id: data.risk_id,
          });
        }
      });
    }
  }, {
    immediate: true,
  });
</script>
<style  lang="postcss">
.risk-manage-detail-linkevent-part {
  padding: 6px 14px 14px;

  .linkevent-table :deep(thead th) {
    background-color: #f5f7fa;
  }

  .evidence-table :deep(thead th) {
    background-color: #f5f7fa;
  }

  .evidence-table :deep(.bk-table-body) {
    max-height: calc(100vh - 100px);
  }
}

.bk-popover {
  max-width: 750px;
  word-break: break-all;
}

.val-tooltips-text {
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.val-tooltips {
  max-width: 300px;
  word-break: break-all;
}
</style>
