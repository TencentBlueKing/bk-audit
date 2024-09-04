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
  <smart-action>
    <bk-loading
      :loading="controlLoading || isSystemListLoading || loading
        || commonLoading || detailLoading || tableLoading">
      <bk-tab
        v-model:active="panelActive"
        class="card-tab"
        style="position: fixed;right: 40px;"
        tab-position="right"
        type="unborder-card"
        @change="handleTabChange">
        <bk-tab-panel
          v-for="(item) in panels"
          :key="item.name"
          :label="item.label"
          :name="item.name" />
      </bk-tab>
      <div class="flex-center top-title-wrap">
        <p class="top-title">
          <span class="block">before</span>
          <span class="content">{{ `${controlTitle} - V${oldControlData.control_version}.0` }}</span>
        </p>
        <p class="top-title">
          <span class="block">after</span>
          <span class="content">{{ `${controlTitle} - V${newControlData.control_version}.0` }}</span>
        </p>
      </div>
      <!-- 版本信息 -->
      <div
        id="strategyUpgradeInfo"
        class="flex-center"
        style="margin-top: 40px;">
        <card
          class="mr16"
          :column="oldInfoColumn"
          title="版本信息" />
        <card
          :column="newInfoColumn"
          title="版本信息" />
      </div>
      <!-- 方案输入 -->
      <div
        id="strategyUpgradeInput"
        class="flex-center mb16">
        <card
          class="mr16"
          :column="inputFieldsColumn"
          :input-fields-map="oldInputFieldsMap"
          title="方案输入" />
        <card
          :column="inputFieldsColumn"
          :input-fields-map="newInputFieldsMap"
          title="方案输入" />
      </div>

      <!-- 方案输出 -->
      <div
        id="strategyUpgradeOutput"
        class="flex-center mb16">
        <card
          class="mr16"
          :column="oldOutputsFields"
          title="方案输出" />
        <card
          :column="newOutputsFields"
          title="方案输出" />
      </div>
    </bk-loading>
    <template #action>
      <bk-button
        class="w88"
        theme="primary"
        @click="handleNext">
        {{ t('下一步') }}
      </bk-button>
      <bk-button
        class="ml8"
        @click="handleCancel">
        {{ t('取消') }}
      </bk-button>
    </template>
  </smart-action>
</template>
<script lang="ts">
  export interface ColumnType {
    label: string;
    value: string;
    field?: string | string[];
    type?: string;
    disabled?: boolean;
    new?: boolean;
    highlight?: boolean;
  }
</script>
<script setup lang='ts'>
  import {
    computed,
    onMounted,
    onUnmounted,
    ref,
    shallowRef,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
    useRouter,
  } from 'vue-router';

  import ControlManageService from '@service/control-manage';
  import MetaManageService from '@service/meta-manage';
  import StrategyManageService from '@service/strategy-manage';

  import ControlModel from '@model/control/control';
  import AiopPlanModel from '@model/strategy/aiops-plan';
  import CommonDataModel from '@model/strategy/common-data';

  import useRequest from '@hooks/use-request';

  import Card from './components/card.vue';

  import type { ControlType } from '@/views/strategy-manage/strategy-create/components/step1/index.vue';

  interface Emits {
    (e: 'change', step: number): void,
  }


  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const router = useRouter();
  const route = useRoute();

  const oldInputFields = shallowRef<ValueOf<AiopPlanModel['input_fields']>>([]);
  const newInputFields = shallowRef<ValueOf<AiopPlanModel['input_fields']>>([]);
  const systemMap = ref<Record<string, string>>({});
  const panels = ref([
    { name: 'strategyUpgradeInfo', label: t('版本信息'), count: 10 },
    { name: 'strategyUpgradeInput', label: t('方案输入'), count: 20 },
    { name: 'strategyUpgradeOutput', label: t('方案输出'), count: 30 },
  ]);
  const panelActive = ref('strategyUpgradeInfo');
  const formData = ref<Record<string, any>>({});
  const loading = ref(true);
  const tableNameList  = ref<string[]>([]);
  const newControlData = ref(new ControlModel());
  const oldControlData = ref(new ControlModel());
  const controlMap = ref<Record<string, ControlType>>({});
  const inputSystemIds = ref<string[]>([]);

  // 方案输出
  const oldOutputsFields = ref<Array<ColumnType>>([]);
  const newOutputsFields = ref<Array<ColumnType>>([]);
  const isEventLog = ref(true);

  const scrollElement = ref<HTMLElement>();
  let scrollTimeout = 0;
  const controlTitle = computed(() => {
    if (!controlList.value.length || !oldControlData.value) return '';
    const data = controlMap.value[oldControlData.value.control_id];
    if (!data) return '';
    return `${data.control_name}`;
  });
  // 版本信息
  const oldInfoColumn = computed(() => {
    if (!oldControlData.value) return [];
    const data = oldControlData.value || {};
    return [
      {
        label: '版本号',
        value: `V${data.control_version}.0`,
      },
      {
        label: '发布标签',
        value: data.extra_config?.tags.join(',') || '--',
      },
      {
        label: '发布人',
        value: data.extra_config?.developer.join(',') || '--',
      },
      {
        label: '发布时间',
        value: data.extra_config?.updated_at || '--',
      },
    ];
  });
  const newInfoColumn = computed(() => {
    if (!newControlData.value) return [];
    const data = newControlData.value || {};
    return [
      {
        label: '版本号',
        value: `V${data.control_version}.0`,
      },
      {
        label: '发布标签',
        value: data.extra_config?.tags.join(',') || '--',
      },
      {
        label: '发布人',
        value: data.extra_config?.developer.join(',') || '--',
      },
      {
        label: '发布时间',
        value: data.extra_config?.updated_at || '--',
      },
    ];
  });
  // 方案输入
  const inputFieldsColumn = computed(() => {
    if (formData.value.configs) {
      return [
        {
          label: '数据源类型',
          value: commonData.value.table_type
            .find((item: Record<string, string>) => item.value === formData.value.configs.config_type)?.label || '--',
        },
        {
          label: isEventLog.value ? '系统' : '资产',
          value: isEventLog.value
            ? inputSystemIds.value.map(item => systemMap.value[item] || item).join('、') || '--'
            : tableNameList.value.join(' / ') || '--',
        },
      ];
    }
    return [];
  });
  // 方案输入字段映射
  const newInputFieldsMap = computed(() => {
    if (loading.value || !formData.value.configs) return [];
    if (formData.value.configs.config_type === 'EventLog') {
      return inputSystemIds.value.reduce((result, systemId) => {
        const res =  newInputFields.value.reduce((res, item) => {
          const fItem = formData.value.configs.data_source.fields[systemId]
            .find(({ field_name: fieldName }: { field_name: string }) => fieldName === item.field_name);
          const findItem = oldInputFields.value.find(o => o.field_name === item.field_name);
          if (AiopPlanModel.checkHideInputField(item)) {
            res.push({
              type: item.field_type,
              label: item.field_name,
              value: item.value,
              new: !findItem || item.field_type !== findItem.field_type || !fItem,
            });
          }
          return res;
        }, [] as [] as Array<ColumnType>);
        sortColumnArray(res, 'new');
        result.push({
          title: systemMap.value[systemId] || systemId,
          column: res,
        });
        return result;
      }, [] as Array<{
        title: string,
        column: Array<ColumnType>
      }>);
    }
    const newFields =  newInputFields.value.reduce((res, item) => {
      if (AiopPlanModel.checkHideInputField(item)) {
        const sourceField = formData.value.configs.data_source.fields
          .find((field: {
            field_name: string;
            source_field: string
          }) => field.field_name === item.field_name)?.source_field || '';
        const findItem = oldInputFields.value.find(o => o.field_name === item.field_name);
        res.push({
          type: item.field_type,
          label: item.field_name,
          value: sourceField,
          new: !findItem || findItem.field_type !== item.field_type,
        });
      }
      return res;
    }, [] as  Array<ColumnType>);
    sortColumnArray(newFields, 'new');
    return [{
      column: newFields,
    }];
  });
  // 方案输入字段映射
  const oldInputFieldsMap = computed(() => {
    if (loading.value || !formData.value.configs) return [];
    if (formData.value.configs.config_type === 'EventLog') {
      return inputSystemIds.value.reduce((result, systemId) => {
        const res = oldInputFields.value.reduce((res, item) => {
          const fItem = formData.value.configs.data_source.fields[systemId]
            .find(({ field_name: fieldName }: { field_name: string }) => fieldName === item.field_name);
          if (AiopPlanModel.checkHideInputField(item) && fItem) {
            const findItem = newInputFields.value.find(o => o.field_name === item.field_name);
            res.push({
              type: item.field_type,
              label: item.field_name,
              value: fItem.source_field.map(({ source_field: field }: {source_field: string}) => field).join(','),
              disabled: !findItem || item.field_type !== findItem.field_type,
            });
          }
          return res;
        }, [] as [] as Array<ColumnType>);
        sortColumnArray(res, 'disabled');
        result.push({
          title: systemMap.value[systemId] || systemId,
          column: res,
        });
        return result;
      }, [] as Array<{
        title: string,
        column: Array<ColumnType>
      }>);
    }
    const oldFields =  oldInputFields.value.reduce((res, item) => {
      if (AiopPlanModel.checkHideInputField(item)) {
        const sourceField = formData.value.configs.data_source.fields
          .find((field: {
            field_name: string;
            source_field: string
          }) => field.field_name === item.field_name)?.source_field || '';
        const findItem = newInputFields.value.find(o => o.field_name === item.field_name);
        res.push({
          type: item.field_type,
          label: item.field_name,
          value: sourceField,
          disabled: !findItem || item.field_type !== findItem.field_type,
        });
      }
      return res;
    }, [] as Array<ColumnType>);
    sortColumnArray(oldFields, 'disabled');
    return [{
      column: oldFields,
    }];
  });

  // 获取tableid
  const {
    run: fetchTable,
    loading: tableLoading,
  } = useRequest(StrategyManageService.fetchTable, {
    defaultValue: [],
    onSuccess(data) {
      const tableId = formData.value.configs.data_source?.result_table_id;
      data.forEach((item) => {
        if (item.children && item.children.length) {
          item.children.forEach((cItem) => {
            if (cItem.value === tableId) {
              tableNameList.value =  [item.label, cItem.label];
            }
          });
        }
      });
    },
  });
  // 获取系统
  const {
    loading: isSystemListLoading,
  } = useRequest(MetaManageService.fetchSystemWithAction, {
    defaultValue: [],
    manual: true,
    onSuccess(data) {
      data.forEach((item) => {
        systemMap.value[item.id] = item.name;
      });
    },
  });
  // 编辑状态获取数据
  const {
    loading: detailLoading,
  } = useRequest(StrategyManageService.fetchStrategyList, {
    defaultValue: {
      results: [],
      page: 1,
      num_pages: 1,
      total: 1,
    },
    defaultParams: {
      page: 1,
      page_size: 1,
      strategy_id: route.params.strategyId,
    },
    manual: true,
    onSuccess: (data) => {
      [formData.value] = data.results;
      if (formData.value.configs.config_type === 'EventLog') {
        inputSystemIds.value = Object.keys(formData.value.configs.data_source.fields);
      } else {
        isEventLog.value = false;
        // 解析resulttableid
        fetchTable({
          table_type: formData.value.configs.config_type,
        });
      }
    },
  });

  // 获取方案详情
  const {
    run: fetchControlDetail,
  } = useRequest(ControlManageService.fetchControlDetail);


  // 获取方案列表
  const {
    data: controlList,
    loading: controlLoading,
  } = useRequest(StrategyManageService.fetchControlList, {
    defaultValue: [],
    manual: true,
    onSuccess() {
      controlList.value.forEach((item) => {
        controlMap.value[item.control_id] = item;
      });
    },
  });
  // 获取公共参数
  const {
    data: commonData,
    loading: commonLoading,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: new CommonDataModel(),
    manual: true,
  });

  const handleScroll = () => {
    const inputEle = document.querySelector('#strategyUpgradeInput') as HTMLElement;
    const outputEle = document.querySelector('#strategyUpgradeOutput') as HTMLElement;
    if (!scrollElement.value || !inputEle || !outputEle) return;
    const input = inputEle.offsetTop;
    const output = outputEle.offsetTop;
    const { scrollTop } = scrollElement.value;
    const offset = 50;
    if (Math.abs(scrollTop - output) <= offset) {
      panelActive.value = 'strategyUpgradeOutput';
    } else if (Math.abs(scrollTop - input) <= offset) {
      panelActive.value = 'strategyUpgradeInput';
    } else {
      panelActive.value = 'strategyUpgradeInfo';
    }
  };
  const handleNext = () => {
    emits('change', 2);
  };
  // 排序
  const sortColumnArray = (arr: Array<ColumnType>, sortField: string) => {
    const k = sortField as keyof ColumnType;
    arr.sort((a, b) => {
      if (a[k] && !b[k]) {
        return 1;
      } if (!a[k] && b[k]) {
        return -1;
      }
      return 0;
    });
  };
  const handleCancel = () => {
    router.push({
      name: 'strategyEdit',
      params: {
        id: route.params.strategyId,
      },
    });
  };
  const handleTabChange = (tab: string) => {
    if (tab) {
      const pos = document.getElementById(tab);
      pos?.scrollIntoView();
    }
  };
  const setOutputFields = () => {
    // 旧版本方案输出
    if (!oldControlData.value.output_config || !newControlData.value.output_config) return;
    const { fields: oldFields } = oldControlData.value.output_config[0];
    const { fields: newFields } = newControlData.value.output_config[0];
    oldOutputsFields.value =  oldFields.map((item: Record<string, any>) => {
      const findItem = newFields.find((o: Record<string, any>) => o.field_name === item.field_name);
      return {
        label: `${item.field_name}(${item.field_alias})`,
        value: `${item.field_name}(${item.field_alias})`,
        type: item.field_type,
        disabled: !findItem || findItem.field_type !== item.field_type,
      };
    }) as Array<ColumnType>;
    sortColumnArray(oldOutputsFields.value, 'disabled');

    // 新版本方案输出
    newOutputsFields.value = newFields.map((item: Record<string, any>) => {
      const findItem = oldFields.find((o: Record<string, any>) => o.field_name === item.field_name);
      return {
        label: `${item.field_name}(${item.field_alias})`,
        value: `${item.field_name}(${item.field_alias})`,
        type: item.field_type,
        highlight: !findItem || findItem.field_type !== item.field_type,
      };
    }) as Array<ColumnType>;
    sortColumnArray(newOutputsFields.value, 'highlight');
  };
  const findScrollElement = () => {
    clearTimeout(scrollTimeout);
    if (!scrollElement.value) {
      scrollTimeout = setTimeout(() => {
        scrollElement.value = document.querySelector('.scrollbar-vertical') as HTMLElement;
        if (!scrollElement.value) {
          findScrollElement();
        } else {
          scrollElement.value.addEventListener('scroll', handleScroll);
        }
      }, 300);
    }
  };
  onMounted(() => {
    Promise.all([fetchControlDetail({
                   control_id: route.params.controlId,
                   control_version: route.query.version,
                 }),
                 fetchControlDetail({
                   control_id: route.params.controlId,
                 })]).then((data) => {
      [oldControlData.value, newControlData.value] = data;
      oldInputFields.value = data[0].input_config[0]?.require_fields;
      newInputFields.value = data[1].input_config[0]?.require_fields;
      loading.value = false;

      setOutputFields();
      findScrollElement();
    });
  });
  onUnmounted(() => {
    if (scrollElement.value) {
      scrollElement.value.removeEventListener('scroll', handleScroll);
    }
  });
</script>
<style scoped lang="postcss">
.card-tab {
  :deep(.bk-tab-header) {
    .bk-tab-header-active-bar {
      height: 20px;
    }

    .bk-tab-header-item {
      line-height: 20px;
    }

    .bk-tab-header-item+.bk-tab-header-item {
      margin-top: 16px;
    }
  }
}

.flex-center {
  display: flex;
  padding-right: 110px;
  margin-top: 16px;

  .strategy-upgrade-card {
    flex: 1;
  }
}


.top-title-wrap {
  position: absolute;
  top: -15px;
  left: 0;
  width: 100%;
  padding-left: 24px;
  background: #dcdee5;

  .top-title {
    flex: 1;
    width: 491px;
    height: 40px;
    margin-right: 16px;
    font-size: 14px;
    line-height: 40px;
    color: #000;

    >.block {
      display: inline-block;
      height: 22px;
      padding: 0 8px;
      margin-right: 8px;
      font-size: 12px;
      font-weight: 700;
      line-height: 22px;
      color: #fff;
      text-align: center;
      background: #979ba5;
      border-radius: 2px;
    }
  }
}
</style>
