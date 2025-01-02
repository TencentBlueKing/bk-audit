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
  <div class="strategy-reference-model">
    <bk-form-item
      class="is-required"
      :label="t('模型方案')"
      label-width="160"
      property="control_id">
      <div
        class="flex-center"
        style="position: relative; width: 100%;">
        <plan-select
          ref="planSelectRef"
          :control-list="controlList"
          :cur-version="(formData.control_version as number)"
          :default-value="formData.control_id"
          :disabled="isEditMode || isCloneMode"
          style="width: 46%;"
          @change="onControlIdChange">
          <span
            v-if="controlTypeId === 'BKM'"
            class="inset-tip">
            {{ t('内置') }}
          </span>
        </plan-select>

        <p
          v-if="isShowUpgradeTip"
          class="upgrade-tip">
          <span class="block" />
          <span class="content">
            {{ `${t('该方案存在新版本')} V${maxVersionMap[formData.control_id]}.0，${t('升级版本可能要重新配置')}` }}
          </span>
          <span
            class="btn"
            @click="handleShowUpgradeDetail">，{{ t('查看升级详情') }}</span>
        </p>
      </div>
    </bk-form-item>
    <component
      :is="comMap[controlTypeId]"
      ref="comRef"
      :control-detail="controlDetail"
      :data="formData"
      @update-aiops-config="handleUpdateAiopsConfig"
      @update-config-type="handleUpdateConfigType"
      @update-configs="handleUpdateConfigs"
      @update-data-source="handleUpdateDataSource" />
  </div>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import { computed, nextTick, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import ControlManageService from '@service/control-manage';
  import StrategyManageService from '@service/strategy-manage';

  import type ControlModel from '@model/control/control';
  import StrategyModel from '@model/strategy/strategy';

  import AiopsCondition from './components/aiops/index.vue';
  import NormalCondition from './components/normal/index.vue';
  import PlanSelect from './components/plan-select.vue';

  import useRequest from '@/hooks/use-request';

  interface ControlType {
    control_type_id: string;
    control_id: string;
    control_name: string;
    versions: Array<{
      control_id: string;
      control_version: number
    }>
  }
  interface IFormData {
    strategy_id?: number,
    control_id: string,
    control_version?: number,
    configs: Record<string, any>,
  }
  interface Expose {
    getValue: () => void,
    getFields: () => IFormData
  }
  interface Emits {
    (e: 'updateControlDetail', value: ControlModel | null): void;
    (e: 'updateFormData', value: IFormData): void;
  }
  interface Props {
    editData: StrategyModel
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const route = useRoute();
  const router = useRouter();

  const comRef = ref();
  const planSelectRef = ref();

  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';
  const comMap: Record<string, any> = {
    BKM: NormalCondition,
    AIOps: AiopsCondition,
  };

  const controlTypeId = ref(''); // 方案类型id
  const formData = ref<IFormData>({
    control_id: '',
    configs: {
    },
  });
  const controlMap = ref<Record<string, ControlType>>({});
  const maxVersionMap = ref<Record<string, number>>({});
  const timeType = ref('minute');

  const isShowUpgradeTip = computed(() => isEditMode
    && maxVersionMap.value[formData.value.control_id] > (formData.value.control_version as number));
  const aggInterval = computed(() => {
    switch (timeType.value) {
    case 'minute':
      return Number(formData.value.configs.agg_interval) * 60;
    case 'hour':
      return Number(formData.value.configs.agg_interval) * 60 * 60;
    case 'day':
      return Number(formData.value.configs.agg_interval) * 60 * 60 * 24;
    }
    return formData.value.configs.agg_interval;
  });

  // 编辑
  const  setFormdata = (editData: StrategyModel) => {
    formData.value.control_id = editData.control_id;
    formData.value.control_version = editData.control_version;
    const controlItem = controlMap.value[editData.control_id];
    if (controlItem) {
      controlTypeId.value = controlItem.control_type_id;

      fetchControlDetail({
        control_id: controlItem.control_id,
        control_version: formData.value.control_version,
      });
      // 基础策略
      if (controlTypeId.value === 'BKM') {
        formData.value.configs = {
          ...editData.configs,
        };
        [formData.value.configs.algorithms] = editData.configs.algorithms;
      } else {
        // AI策略
        formData.value.configs.config_type = editData.configs.config_type;
        formData.value.configs.data_source = {
          ...editData.configs.data_source,
        };
        // 操作记录部分
        if (formData.value.configs.config_type === 'EventLog') {
          formData.value.configs.data_source.system_id = Object.keys(formData.value.configs.data_source.fields);
        }
        if (editData.configs.aiops_config) {
          formData.value.configs.aiops_config = {
            ...editData.configs.aiops_config,
          };
        }
        // 方案配置参数部分
        formData.value.configs.variable_config = editData.configs.variable_config || [];
      }
    }
    nextTick(() => {
      comRef.value?.setConfigs(formData.value.configs);
      if (controlTypeId.value === 'BKM') {
        comRef.value?.handleValueDicts(formData.value.configs.agg_condition);
      }
    });
  };

  // 获取版本信息
  useRequest(ControlManageService.fetchControlTypes, {
    defaultValue: [],
    defaultParams: {
      control_type_id: 'AIOps',
    },
    manual: true,
    onSuccess(data) {
      maxVersionMap.value = data.reduce((res, item) => {
        res[item.control_id] = item.versions[0].control_version;
        return res;
      }, {} as Record<string, number>);
    },
  });

  // 获取方案详情
  const {
    run: fetchControlDetail,
    data: controlDetail,
  } = useRequest(ControlManageService.fetchControlDetail, {
    defaultValue: null,
    onSuccess: () => {
      emits('updateControlDetail', controlDetail.value);
    },
  });

  // 获取方案列表
  const {
    data: controlList,
  } = useRequest(StrategyManageService.fetchControlList, {
    defaultValue: [],
    manual: true,
    onSuccess() {
      controlList.value.forEach((item) => {
        controlMap.value[item.control_id] = item;
      });
      if (isEditMode || isCloneMode) {
        setFormdata(props.editData);
      }
    },
  });

  // 切换方案
  const onControlIdChange = (id: string) => {
    formData.value.control_id = id;
    if (id) {
      const controlItem = controlMap.value[id];
      formData.value.control_version = controlItem.versions[0].control_version;
      controlTypeId.value = controlItem.control_type_id;
      fetchControlDetail({
        control_id: id,
      });
      // 清除系统选择
      nextTick(() => {
        comRef.value.clearData && comRef.value.clearData();
      });
    } else {
      controlTypeId.value = '';
      controlDetail.value = null;
      emits('updateControlDetail', controlDetail.value);
    }
    // 重置数据
    formData.value.configs = {};
  };

  // 查看升级详情
  const handleShowUpgradeDetail = () => {
    router.push({
      name: 'strategyUpgrade',
      params: {
        controlId: formData.value.control_id,
        strategyId: formData.value.strategy_id as number,
      },
      query: {
        version: formData.value.control_version as number,
      },
    });
  };

  // 更新内置模型config参数
  const handleUpdateConfigs = (configs: Record<string, any>) => {
    formData.value.configs = {
      ...formData.value.configs,
      ...configs,
    };
  };

  // 切换AI模型数据源类型
  const handleUpdateConfigType = (configType: string) => {
    formData.value.configs.config_type = configType;
  };

  // 更新AI模型config参数
  const handleUpdateDataSource = (dataSource: Record<string, any>) => {
    formData.value.configs.data_source = {
      ...formData.value.configs.data_source,
      ...dataSource,
    };
  };

  // 更新AI模型config.aiops_config，调度周期
  const handleUpdateAiopsConfig = (aiopsConfig: Record<string, any>) => {
    if (aiopsConfig) {
      formData.value.configs.aiops_config = {
        ...formData.value.configs.aiops_config,
        ...aiopsConfig,
      };
    } else {
      delete formData.value.configs.aiops_config;
    }
  };

  watch(() => formData.value, (data) => {
    emits('updateFormData', data);
  }, {
    deep: true,
  });

  defineExpose<Expose>({
    getValue() {
      const tastQueue = [planSelectRef.value.getValue()];
      if (controlTypeId.value && controlTypeId.value !== 'BKM') {
        tastQueue.push(comRef.value.getValue());
      }
      return Promise.all(tastQueue).then(() => Promise.resolve());
    },
    // 获取提交参数
    getFields() {
      const params = { ...formData.value };
      params.configs = Object.assign({}, formData.value.configs);
      // 内置模型
      if (controlTypeId.value !== 'BKM') {
        const fields = comRef.value.getFields();
        const tableIdList = params.configs.data_source.result_table_id;
        if (params.configs.config_type !== 'EventLog') {
          params.configs.data_source = {
            ...params.configs.data_source,
            fields,
            result_table_id: _.isArray(tableIdList) ?  _.last(tableIdList)  : tableIdList,
          };
        } else {
          params.configs.data_source = {
            ...params.configs.data_source,
            fields,
          };
        }
        // 添加方案配置参数
        params.configs.variable_config = comRef.value.getParamenterFields();
      } else {
        params.configs.algorithms = [formData.value.configs.algorithms];
        params.configs.agg_interval = aggInterval.value;
      }
      return params;
    },
  });
</script>
<style lang="postcss" scoped>
.inset-tip {
  position: absolute;
  top: 50%;
  right: 30px;
  padding: 3px 10px;
  font-size: 12px;
  font-weight: normal;
  line-height: normal;
  color: #3a84ff;
  background: #edf4ff;
  border-radius: 2px;
  transform: translateY(-50%);
}
</style>
