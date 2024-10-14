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
  <div class="diff-condition">
    <bk-form-item
      label=""
      label-width="0"
      required>
      <collapse-panel
        :is-active="isActive"
        :label="t('方案输入')"
        style="margin-bottom: 14px;">
        <div style="padding: 16px 32px 24px;">
          <bk-form-item
            :label="t('数据源类型')"
            label-width="160"
            property="configs.data_source.source_type"
            required>
            <bk-radio-group
              v-model="formData.configs.config_type"
              class="strategy-radio-group"
              :disabled="isEditMode || isCloneMode || isUpgradeMode"
              @change="handleDataSourceType">
              <bk-radio-button
                v-for="item in commonData.table_type"
                :key="item.value"
                v-bk-tooltips="tableTypeTip[item.value]"
                class="form-raido-common"
                :label="item.value"
                style="min-width: 181px;">
                {{ t(item.label) }}
              </bk-radio-button>
            </bk-radio-group>
          </bk-form-item>

          <component
            :is="comMap[formData.configs.config_type]"
            ref="comRef"
            :control-detail="controlDetail"
            :input-fields="inputFields"
            :loading="tableLoading"
            :source-type="formData.configs.config_type"
            :table-data="tableData"
            :trigger-error="triggerError"
            @update-data-source="handleUpdateDataSource" />
        </div>
      </collapse-panel>

      <collapse-panel
        :is-active="isActive"
        :label="t('方案参数')"
        style="margin-bottom: 14px;">
        <!-- <model-empty /> -->
        <div style="padding: 16px 32px 24px;">
          <scheme-paramenters
            ref="paramenterRef"
            :control-detail="controlDetail" />
        </div>
      </collapse-panel>

      <collapse-panel
        :is-active="isActive"
        :label="t('调度配置')"
        style="margin-bottom: 12px;">
        <div class="dispatch-wrap">
          <bk-form-item
            :label="t('调度方式')"
            property="source_type"
            style="margin-bottom: 12px;">
            <bk-radio-group
              v-model="formData.configs.data_source.source_type"
              @change="handleSourceTypeChange">
              <bk-radio label="batch_join_source">
                {{ t('固定周期调度') }}
              </bk-radio>
              <bk-radio label="stream_source">
                <span
                  v-bk-tooltips="t('策略实时运行')"
                  style="color: #63656e; cursor: pointer; border-bottom: 1px dashed #979ba5;">
                  {{ t('实时调度') }}
                </span>
              </bk-radio>
            </bk-radio-group>
          </bk-form-item>
          <template v-if="formData.configs.data_source.source_type !== 'stream_source'">
            <span
              v-bk-tooltips="t('策略运行的周期')"
              class="label-is-required"
              style="color: #63656e; cursor: pointer; border-bottom: 1px dashed #979ba5;">
              {{ t('调度周期') }}
            </span>
            <div class="flex-center">
              <bk-form-item
                class="is-required no-label"
                label-width="0"
                property="configs.aiops_config.count_freq"
                style="margin-bottom: 12px;">
                <bk-input
                  v-model="formData.configs.aiops_config.count_freq"
                  class="schedule-input"
                  :min="1"
                  onkeypress="return( /[\d]/.test(String.fromCharCode(event.keyCode) ) )"
                  :placeholder="t('请输入')"
                  type="number"
                  @change="handleAiopsConfig" />
              </bk-form-item>
              <bk-form-item
                class="is-required no-label"
                label-width="0"
                property="configs.aiops_config.schedule_period"
                style="margin-bottom: 12px;">
                <bk-select
                  v-model="formData.configs.aiops_config.schedule_period"
                  class="schedule-select"
                  :clearable="false"
                  style="width: 68px;"
                  @change="handleAiopsConfig">
                  <bk-option
                    v-for="(item, index) in commonData.offset_unit"
                    :key="index"
                    :label="item.label"
                    :value="item.value" />
                </bk-select>
              </bk-form-item>
            </div>
          </template>
        </div>
      </collapse-panel>
    </bk-form-item>
  </div>
</template>
<script setup lang="tsx">
  import {
    ref,
    shallowRef,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
  } from 'vue-router';

  import StrategyManageService from '@service/strategy-manage';

  import type ControlModel from '@model/control/control';
  import type AiopPlanModel from '@model/strategy/aiops-plan';
  import CommonDataModel from '@model/strategy/common-data';

  import useRequest from '@hooks/use-request';

  import CollapsePanel from './components/components/collapse-panel.vue';
  // import ModelEmpty from './components/components/model-empty.vue';
  import EventLogComponent from './components/scheme-input/event-log.vue';
  import ResourceDataComponent from './components/scheme-input/resource-data.vue';
  import SchemeParamenters from './components/scheme-paramenters/index.vue';

  type GetFieldsType = ReturnType<InstanceType<typeof EventLogComponent>['getFields']> | ReturnType<InstanceType<typeof ResourceDataComponent>['getFields']>;

  interface Props {
    controlDetail: ControlModel;
    triggerError?: boolean,
  }
  interface Emits {
    (e: 'updateDataSource', value: Record<string, any>): void,
    (e: 'updateConfigType', value: string): void,
    (e: 'updateAiopsConfig', value: IFormData['configs']['aiops_config'] | undefined): void,
  }
  interface Exposes {
    getValue: () => Promise<any>;
    getFields: () => GetFieldsType;
    getParamenterFields: () => ReturnType<InstanceType<typeof SchemeParamenters>['getFields']>;
    setConfigs: (data: IFormData['configs']) => void;
    clearData: () => void;
  }

  interface IFormData {
    configs: {
      data_source: {
        source_type: string,
      },
      aiops_config: {
        count_freq: string,
        schedule_period: string,
      },
      config_type: string,
      variable_config: Array<Record<string, any>>
    },
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const comMap: Record<string, any> = {
    EventLog: EventLogComponent,
    BuildIn: ResourceDataComponent,
    BizAsset: ResourceDataComponent,
  };
  const route = useRoute();
  let isInit = false;
  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';
  const isUpgradeMode = route.name === 'strategyUpgrade';
  const { t } = useI18n();
  const tableTypeTip: Record<string, string> = {
    EventLog: t('各应用系统按照审计中心规范上报的系统操作日志'),
    BuildIn: t('各应用系统接入审计中心时上报的系统资源数据'),
    BizAsset: t('未事先在审计中心上报的资源数据'),
  };


  const comRef = ref();
  const paramenterRef = ref();
  const inputFields = shallowRef<ValueOf<AiopPlanModel['input_fields']>>([]);
  const isActive = ref(true);
  const formData = ref<IFormData>({
    configs: {
      data_source: {
        source_type: 'batch_join_source',
      },
      config_type: 'EventLog',
      aiops_config: {
        count_freq: '',
        schedule_period: 'hour',
      },
      variable_config: [],
    },
  });
  const sourceTypeMap = ref<Record<string, string>>({});

  if (!isEditMode && !isCloneMode && !isUpgradeMode) {
    isInit = true;
    emits('updateDataSource', formData.value.configs.data_source);
    emits('updateConfigType', formData.value.configs.config_type);
    emits('updateAiopsConfig', formData.value.configs.aiops_config);
  }


  const {
    data: commonData,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: new CommonDataModel(),
    manual: true,
    onSuccess(data) {
      sourceTypeMap.value = commonData.value.table_type.reduce((
        res: Record<string, string>,
        item,
      ) => {
        res[item.value] = item.config.source_type;
        return res;
      }, {});
      if (!isEditMode && !isCloneMode && !isUpgradeMode) {
        formData.value.configs.config_type = data.table_type[0].value;
        fetchTable({
          table_type: formData.value.configs.config_type,
        });
      }
    },
  });
  // 获取tableid
  const {
    data: tableData,
    run: fetchTable,
    loading: tableLoading,
  } = useRequest(StrategyManageService.fetchTable, {
    defaultValue: [],
  });


  // 切换数据源类型： 默认使用离线模式batch_join_source，不切换类型
  const handleDataSourceType = (item: boolean | string | number) => {
    fetchTable({
      table_type: item,
    });
    if (isInit) {
      emits('updateDataSource', formData.value.configs.data_source);
      emits('updateConfigType', formData.value.configs.config_type);
      emits('updateAiopsConfig', formData.value.configs.data_source.source_type !== 'stream_source'
        ? formData.value.configs.aiops_config
        : undefined);
    }
  };
  const handleAiopsConfig = () => {
    if (!isInit) return;
    emits('updateAiopsConfig', formData.value.configs.aiops_config);
  };
  const handleUpdateDataSource = (dataSource: Record<string, any>) => {
    if (!isInit) return;
    emits('updateDataSource', dataSource);
  };
  const handleSourceTypeChange = (type: string) => {
    if (type === 'stream_source') {
      formData.value.configs.aiops_config = {
        count_freq: '',
        schedule_period: 'hour',
      };
    }
    emits('updateAiopsConfig', formData.value.configs.data_source.source_type !== 'stream_source'
      ? formData.value.configs.aiops_config
      : undefined);
    emits('updateDataSource', formData.value.configs.data_source);
  };

  watch(() => props.controlDetail, (data) => {
    if (data && data.input_config) {
      inputFields.value = data.input_config[0]?.require_fields;
    }
  }, {
    deep: true,
    immediate: true,
  });

  defineExpose<Exposes>({
    getValue() {
      if (!props.controlDetail.variable_config.parameter.length) {
        return Promise.resolve();
      }
      return comRef.value.getValue().then(() => paramenterRef.value.getValue());
    },
    setConfigs(configs: IFormData['configs']) {
      formData.value.configs.config_type = configs.config_type;
      formData.value.configs.data_source.source_type = configs.data_source.source_type;
      if (configs.aiops_config && configs.aiops_config.count_freq) {
        formData.value.configs.aiops_config.count_freq = configs.aiops_config.count_freq;
        formData.value.configs.aiops_config.schedule_period = configs.aiops_config.schedule_period;
      }

      fetchTable({
        table_type: formData.value.configs.config_type,
      }).then(() => {
        comRef.value.setConfigs(configs);
      });
      paramenterRef.value.setConfigs(configs.variable_config);
      isInit = true;
    },
    getFields() {
      return comRef.value.getFields();
    },
    getParamenterFields() {
      if (!props.controlDetail.variable_config.parameter.length) {
        return [];
      }
      return paramenterRef.value.getFields();
    },
    clearData() {
      comRef.value.clearData && comRef.value.clearData();
      if (commonData.value.table_type && commonData.value.table_type.length) {
        formData.value.configs.config_type = commonData.value.table_type[0].value;
        handleDataSourceType(formData.value.configs.config_type);
      }
    },
  });
</script>


<style lang="postcss">

.schedule-input {
  /* display: block; */
  width: 340px;
  border-right: 0;
  border-radius: 2px 0 0 2px;

  .bk-input--text {
    display: flex;
    align-items: center;
    height: 100%;
  }
}

.schedule-select .bk-input {
  display: block;
  border-radius: 0 2px 2px 0;

  .bk-input--text {
    display: flex;
    align-items: center;
    height: 100%;
  }
}

.diff-condition {
  .label-is-required::after {
    position: absolute;
    width: 14px;
    line-height: 32px;
    color: #ea3636;
    text-align: center;
    content: '*';
  }

  .no-label .bk-form-label::after {
    content: '';
  }

  .no-label .bk-form-label {
    padding-right: 0;
  }

  .dispatch-wrap {
    padding: 16px 24px;

    .flex-center {
      display: flex;
      align-items: center;
    }
  }
}
</style>
