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
  <skeleton-loading
    fullscreen
    :loading="controlLoading || tagLoading"
    name="createStrategy">
    <smart-action
      class="create-strategy-page"
      :offset-target="getSmartActionOffsetTarget">
      <div class="create-strategy-main">
        <audit-form
          ref="formRef"
          class="strategt-form"
          form-type="vertical"
          :model="formData"
          :rules="rules">
          <card-part-vue :title="t('基础配置')">
            <template #content>
              <div class="flex-center">
                <bk-form-item
                  class="is-required mr16"
                  :label="t('策略名称')"
                  label-width="160"
                  property="strategy_name"
                  style="flex: 1;">
                  <bk-input
                    v-model.trim="formData.strategy_name"
                    :maxlength="32"
                    :placeholder="t('请输入策略名称')"
                    show-word-limit
                    style="width: 100%;" />
                </bk-form-item>
                <bk-form-item
                  :label="t('标签')"
                  label-width="160"
                  property="tags"
                  style="flex: 1;">
                  <bk-loading
                    :loading="tagLoading"
                    style="width: 100%;">
                    <bk-select
                      v-model="formData.tags"
                      allow-create
                      class="bk-select"
                      filterable
                      :input-search="false"
                      multiple
                      multiple-mode="tag"
                      :placeholder="t('请选择')"
                      :search-placeholder="t('请输入关键字')">
                      <bk-option
                        v-for="(item, index) in tagData"
                        :key="index"
                        :label="item.name"
                        :value="item.id" />
                    </bk-select>
                  </bk-loading>
                </bk-form-item>
              </div>
              <bk-form-item
                class="is-required"
                :label="t('风险等级')"
                label-width="160"
                property="risk_level">
                <bk-button-group>
                  <bk-button
                    v-for="item in riskLevelList"
                    :key="item.value"
                    :disabled="canEditRiskLevel"
                    :loading="commonLoading"
                    :selected="formData.risk_level === item.value"
                    @click="handleLevel(item.value)">
                    {{ item.label }}
                  </bk-button>
                </bk-button-group>
              </bk-form-item>
              <div class="flex">
                <bk-form-item
                  class="mr16"
                  :label="t('风险危害')"
                  label-width="160"
                  property="risk_hazard"
                  style="flex: 1;">
                  <bk-input
                    v-model.trim="formData.risk_hazard"
                    autosize
                    :maxlength="100"
                    :placeholder="t('请输入描述')"
                    show-word-limit
                    style="width: 100%;"
                    type="textarea" />
                </bk-form-item>
                <bk-form-item
                  :label="t('处理指引')"
                  label-width="160"
                  property="risk_guidance"
                  style="flex: 1;">
                  <bk-input
                    v-model.trim="formData.risk_guidance"
                    autosize
                    :maxlength="100"
                    :placeholder="t('请输入描述')"
                    show-word-limit
                    style="width: 100%;"
                    type="textarea" />
                </bk-form-item>
              </div>
              <bk-form-item
                :label="t('描述')"
                label-width="160"
                property="description">
                <bk-input
                  v-model.trim="formData.description"
                  autosize
                  :maxlength="1000"
                  :placeholder="t('请输入描述')"
                  show-word-limit
                  style="width: 100%;"
                  type="textarea" />
              </bk-form-item>
            </template>
          </card-part-vue>
          <card-part-vue
            :show-content="!!formData.control_id"
            :show-icon="!!formData.control_id">
            <template #title>
              <div
                class="flex-center"
                style="position: relative; width: 100%;">
                <span>
                  {{ t('方案') }}：
                </span>
                <plan-select
                  ref="planSelectRef"
                  :control-list="controlList"
                  :cur-version="(formData.control_version as number)"
                  :default-value="formData.control_id"
                  :disabled="isEditMode || isCloneMode"
                  style="width: 46%;"
                  @change="onControlIdChange">
                  <p
                    v-if="controlTypeId === 'BKM'"
                    class="inset-tip">
                    {{ t('内置') }}
                  </p>
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
            </template>
            <template #content>
              <component
                :is="comMap[controlTypeId]"
                ref="comRef"
                :control-detail="controlDetail"
                :data="formData"
                @update-aiops-config="handleUpdateAiopsConfig"
                @update-config-type="handleUpdateConfigType"
                @update-configs="handleUpdateConfigs"
                @update-data-source="handleUpdateDataSource" />
            </template>
          </card-part-vue>
        </audit-form>

        <!-- 算法说明 -->
        <control-description-vue
          v-if="formData.control_id"
          :data="controlDetail" />
      </div>
      <template #action>
        <bk-button
          :disabled="tagLoading"
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
  </skeleton-loading>
</template>
<script lang="ts">
  export interface ControlType {
    control_type_id: string;
    control_id: string;
    control_name: string;
    versions: Array<{
      control_id: string;
      control_version: number
    }>
  }
</script>
<script setup lang="ts">
  import _ from 'lodash';
  import {
    computed,
    nextTick,
    onBeforeUnmount,
    onMounted,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    onBeforeRouteLeave,
    useRoute,
    useRouter,
  } from 'vue-router';

  import ControlManageService from '@service/control-manage';
  import StrategyManageService from '@service/strategy-manage';

  import CommonDataModel from '@model/strategy/common-data';
  import StrategyModel from '@model/strategy/strategy';

  import useRecordPage from '@hooks/use-record-page';
  import useRequest from '@hooks/use-request';
  import useRouterBack from '@hooks/use-router-back';

  import AiopsCondition from './components/aiops/index.vue';
  import CardPartVue from './components/card-part.vue';
  import ControlDescriptionVue from './components/control-description.vue';
  import NormalCondition from './components/normal/index.vue';
  import PlanSelect from './components/plan-select.vue';

  interface Emits {
    (e: 'nextStep', step: number, params: IFormData): void;
    (e: 'fetchEditData'): void;
  }

  interface Props {
    data: StrategyModel
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const getSmartActionOffsetTarget = () => document.querySelector('.create-strategy-page');

  const router = useRouter();
  const route = useRoute();

  const { removePageParams } = useRecordPage;
  const { t } = useI18n();

  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';

  const comMap: Record<string, any> = {
    BKM: NormalCondition,
    AIOps: AiopsCondition,
  };
  interface IFormData {
    strategy_id?: number,
    strategy_name: string,
    tags: Array<string>,
    description: string,
    control_id: string,
    control_version?: number,
    configs: Record<string, any>,
    status: string,
    risk_level: string,
    risk_hazard: string,
    risk_guidance: string,
  }
  const comRef = ref();
  const formRef = ref();
  const planSelectRef = ref();
  const maxVersionMap = ref<Record<string, number>>({});
  const timeType = ref('minute');
  const tagData = ref<Array<{
    id: string;
    name: string
  }>>([]);
  const controlTypeId = ref('');// 方案类型id
  const canEditRiskLevel = ref(false);
  const formData = ref<IFormData>({
    strategy_name: '',
    tags: [],
    description: '',
    control_id: '',
    configs: {
    },
    status: '',
    risk_level: '',
    risk_hazard: '',
    risk_guidance: '',
  });
  const rules = {
    strategy_name: [
      {
        validator: (value: string) => !!value,
        message: t('策略名称不能为空'),
        trigger: 'blur',
      },
      {
        validator: (value: string) => value.length <= 32,
        message: t('策略名称不超过 32 个字符'),
        trigger: 'blur',
      },
      {
        validator: (value: string) => {
          // eslint-disable-next-line no-useless-escape
          const reg = /[\\\\\|\/\:\*\<\>\"\?]+/;
          return !reg.test(value);
        },
        message: `${t('不允许出现特殊字符')} * : > < " ? \\ / |`,
        trigger: 'blur',
      },
    ],
    tags: [
      // 因为校验的是name，但value是id的数组；将item转为name，自定义输入id = name，直接使用item即可
      {
        validator: (value: Array<string>) => {
          const reg = /^[\w\u4e00-\u9fa5-_]+$/;
          return value.every(item => reg.test(strategyTagMap.value[item] ? strategyTagMap.value[item] : item));
        },
        message: t('标签只允许中文、字母、数字、中划线或下划线组成'),
        trigger: 'change',
      },
      {
        validator: (value: Array<string>) => {
          const reg = /\D+/;
          return value.every(item => reg.test(strategyTagMap.value[item] ? strategyTagMap.value[item] : item));
        },
        message: t('标签不能为纯数字'),
        trigger: 'change',
      },
    ],
    risk_level: [
      {
        validator: (value: string) => !!value,
        message: t('风险等级不能为空'),
        trigger: 'change',
      },
    ],
    'configs.data_source.system_id': [
      {
        validator: (value: Array<string>) => !!value && value.length > 0,
        message: t('系统不能为空'),
        trigger: 'change',
      }],
    'configs.data_source.result_table_id': [
      {
        validator: (value: Array<string>) => !!value && value.length > 0,
        message: t('不能为空'),
        trigger: 'change',
      }],
    'configs.data_source.bk_biz_id': [
      {
        validator: (value: string) => !!value,
        message: t('所属业务不能为空'),
        trigger: 'change',
      }],
    // 检测条件
    'configs.agg_condition': [
      {
        validator: (val: Array<Record<string, any>>) => val.length > 0,
        message: t('检测条件不能为空'),
        trigger: 'none',
      },
    ],
    // 统计字段
    'configs.agg_dimension': [
      {
        validator: (value: Array<string>) => value.length > 0,
        message: t('统计字段不能为空'),
        trigger: 'change',
      },
    ],
    'configs.user_groups': [
      {
        validator: (value: Array<string>) => value.length > 0,
        message: t('通知组不能为空'),
        trigger: 'change',
      },
    ],
    'configs.agg_interval': [
      {
        validator: (value: Array<string>) => !!value,
        message: t('不能为空'),
        trigger: 'change',
      },
    ],
    'configs.algorithms.method': [
      {
        validator: (value: string) => !!value,
        message: t('不能为空'),
        trigger: 'change',
      },
    ],
    'configs.algorithms.threshold': [
      {
        validator: (value: number) => value || value === 0,
        message: t('不能为空'),
        trigger: 'change',
      },
    ],
    // 调度周期
    'configs.aiops_config.count_freq': [
      {
        validator: (value: number) => !!value,
        message: t('调度周期不能为空'),
        trigger: ['change', 'blur'],
      },
    ],
    'configs.aiops_config.schedule_period': [
      {
        validator: (value: string) => !!value,
        message: t('不能为空'),
        trigger: 'change',
      },
    ],
  };

  const controlMap = ref<Record<string, ControlType>>({});
  const strategyTagMap = ref<Record<string, string>>({});

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
  const isShowUpgradeTip = computed(() => isEditMode
    && maxVersionMap.value[formData.value.control_id] > (formData.value.control_version as number));

  const riskLevelList = ref<Array<{
    label: string,
    value: string
  }>>([]);
  const {
    loading: commonLoading,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: new CommonDataModel(),
    manual: true,
    onSuccess: (data) => {
      riskLevelList.value = data.risk_level;
    },
  });

  // 设置风险等级
  const handleLevel = (level: string) => {
    formData.value.risk_level = level;
    formRef.value.validate('risk_level');
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

  // 获取标签列表
  const {
    loading: tagLoading,
  } = useRequest(StrategyManageService.fetchStrategyTags, {
    defaultValue: [],
    manual: true,
    onSuccess(data) {
      tagData.value = data.reduce((res, item) => {
        if (item.tag_id !== '-1') {
          res.push({
            id: item.tag_id,
            name: item.tag_name,
          });
        }
        return res;
      }, [] as Array<{
        id: string;
        name: string
      }>);
      data.forEach((item) => {
        strategyTagMap.value[item.tag_id] = item.tag_name;
      });
    },
  });

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
      if (isEditMode || isCloneMode) {
        emits('fetchEditData');
      }
    },
  });

  // 获取方案详情
  const {
    run: fetchControlDetail,
    data: controlDetail,
  } = useRequest(ControlManageService.fetchControlDetail, {
    defaultValue: null,
  });

  // 编辑反显
  const setEditData = (editData: StrategyModel) => {
    formData.value.status = editData.status;
    formData.value.strategy_id = editData.strategy_id;
    formData.value.strategy_name = isCloneMode ? `${editData.strategy_name}_copy` : editData.strategy_name;
    formData.value.tags = editData.tags ? editData.tags.map(item => item.toString()) : [];
    formData.value.control_id = editData.control_id;
    formData.value.control_version = editData.control_version;
    formData.value.description = editData.description;
    formData.value.risk_hazard = editData.risk_hazard;
    formData.value.risk_guidance = editData.risk_guidance;
    formData.value.risk_level = editData.risk_level;

    // 是否允许编辑风险等级
    canEditRiskLevel.value = !!editData.risk_level;

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
    }
    // 重置数据
    formData.value.configs = {};
  };
  const handleUpdateConfigType = (configType: string) => {
    formData.value.configs.config_type = configType;
  };
  const handleUpdateConfigs = (configs: Record<string, any>) => {
    formData.value.configs = {
      ...formData.value.configs,
      ...configs,
    };
  };
  const handleUpdateDataSource = (dataSource: Record<string, any>) => {
    if (dataSource.result_table_id && dataSource.result_table_id.length) {
      formRef.value.clearValidate('configs.data_source.result_table_id');
    }
    formData.value.configs.data_source = {
      ...formData.value.configs.data_source,
      ...dataSource,
    };
  };
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
  // 提交
  const handleNext = () => {
    const tastQueue = [formRef.value.validate(), planSelectRef.value.getValue()];
    if (controlTypeId.value && controlTypeId.value !== 'BKM') {
      tastQueue.push(comRef.value.getValue());
    }
    Promise.all(tastQueue).then(() => {
      if (!isEditMode) {
        delete formData.value.strategy_id;
      }
      const params = { ...formData.value };
      params.configs = Object.assign({}, formData.value.configs);
      if (params.tags) {
        params.tags = params.tags.map(item => (strategyTagMap.value[item] ? strategyTagMap.value[item] : item));
      }
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
      emits('nextStep', 2, params);
    });
  };

  const handleCancel = () => {
    router.push({
      name: 'strategyList',
    });
  };
  const handleBeforeUnload = (evt: any) => {
    const event = window.event || evt;
    event.preventDefault();
    event.returnValue = false;
  // window.changeConfirm = false;
  };

  useRouterBack(() => {
    router.push({
      name: 'strategyList',
    });
  });
  onMounted(() => {
    window.addEventListener('beforeunload', handleBeforeUnload);
  });
  onBeforeUnmount(() => {
    window.removeEventListener('beforeunload', handleBeforeUnload);
  });
  onBeforeRouteLeave((to) => {
    if (to.name !== 'strategyList' && to.name !== 'strategyUpgrade') {
      removePageParams();
    }
  });
  // 编辑
  watch(() => props.data, (data) => {
    setEditData(data);
  });
</script>
<style lang="postcss" scoped>
.create-strategy-page {
  .upgrade-tip {
    margin-left: 13px;
    font-size: 12px;
    font-weight: 400;

    .block {
      display: inline-block;
      width: 8px;
      height: 8px;
      margin-right: 6px;
      background: #ea3636;
      border-radius: 50%;
    }

    .content {
      color: #ea3636;
    }

    .btn {
      color: #3a84ff;
      cursor: pointer;
    }
  }

  .flex-center {
    display: flex;
    align-items: center;
  }


  .strategy-radio-group {
    :deep(.bk-radio-button .bk-radio-button-label) {
      padding: 0;
    }
  }


  .create-strategy-main {
    display: flex;
    padding-top: 4px;
    padding-bottom: 1px;
    margin-bottom: 24px;

    .strategt-form {
      flex: 1;
      max-width: 1280px;

      :deep(.bk-button-group) {
        .bk-button {
          padding: 0 35px;
          font-size: 12px;

          &:first-child:hover:not(.is-disabled, .is-selected) {
            color: #ea3636;
            border-color: #ea3636;
          }

          &:first-child.is-selected {
            color: #fff;
            background-color: #ea3636;
            border-color: #ea3636;
          }

          &:nth-child(2):hover:not(.is-disabled, .is-selected) {
            color: #ff9c01;
            border-color: #ff9c01;
          }

          &:nth-child(2).is-selected {
            color: #fff;
            background-color: #ff9c01;
            border-color: #ff9c01;
          }

          &:hover:not(.is-disabled, .is-selected) {
            color: #979ba5;
            border-color: #979ba5;
          }

          &.is-selected {
            color: #fff;
            background-color: #979ba5;
            border-color: #979ba5;
          }
        }
      }
    }
  }

  .form-item-common {
    width: 480px;
  }

  .form-raido-common {
    width: 120px;
  }

  :deep(.tag-list .remove-tag) {
    color: #63656e;
  }

  .content {
    :deep(.bk-form-label::after) {
      width: 0;
      content: '';
    }
  }
}

.create_notice_group {
  color: #63656e;
}

.refresh {
  padding: 0 12px;
  color: #979ba5;
  cursor: pointer;
  border-left: 1px solid #dcdee5;
}

.is-disabled {
  cursor: not-allowed;
}

.inset-tip {
  position: absolute;
  top: 50%;
  right: 30px;
  padding: 3px 10px;
  font-size: 12px;
  font-weight: normal;
  color: #3a84ff;
  background: #edf4ff;
  border-radius: 2px;
  transform: translateY(-50%);
}
</style>
