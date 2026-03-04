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
    :loading="tagLoading"
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
                class="is-required risk-level-group"
                label=""
                label-width="160"
                property="risk_level">
                <template #label>
                  <span
                    v-bk-tooltips="{
                      content: t('创建策略人工定义，标识和方便风险单快捷筛选，指引后续处理的跟进'),
                      placement: 'top-start'
                    }"
                    style="
                      color: #63656e;
                      cursor: pointer;
                      border-bottom: 1px dashed #979ba5;
                    ">
                    {{ t('风险等级') }}
                  </span>
                </template>
                <bk-button-group>
                  <bk-button
                    v-for="item in riskLevelList"
                    :key="item.value"
                    :disabled="canEditRiskLevel"
                    :loading="commonLoading"
                    :selected="formData.risk_level === item.value"
                    @click="handleLevel(item.value)">
                    <span
                      v-bk-tooltips="{
                        content: item.config.tips,
                        extCls: 'strategy-way-tips',
                        placement: 'top-start'
                      }"
                      style="
                        line-height: 16px;
                        border-bottom: 1px dashed #979ba5;
                      ">
                      {{ item.label }}
                    </span>
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
                    :maxlength="1000"
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
                    :maxlength="1000"
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
          <card-part-vue :title="t('方案')">
            <template #content>
              <bk-form-item
                class="is-required"
                :label="t('配置方式')"
                label-width="160"
                property="strategy_type">
                <bk-button-group>
                  <bk-button
                    v-for="item in strategyWayList"
                    :key="item.value"
                    :disabled="isStockData || isEditMode"
                    :loading="commonLoading"
                    :selected="formData.strategy_type === item.value"
                    @click="handleStrategyWay(item.value)">
                    <span
                      v-bk-tooltips="{
                        content: item.config.tips,
                        extCls: 'strategy-way-tips',
                        placement: 'top-start'
                      }"
                      style="
                        line-height: 16px;
                        border-bottom: 1px dashed #979ba5;
                      ">
                      {{ item.label }}
                    </span>
                  </bk-button>
                </bk-button-group>
              </bk-form-item>
              <!-- 自定义规则审计、引入模型审计 -->
              <component
                :is="strategyWayComMap[formData.strategy_type]"
                ref="comRef"
                :edit-data="editData"
                @update-control-detail="updateControlDetail"
                @update-form-data="updateFormData" />
            </template>
          </card-part-vue>
        </audit-form>

        <!-- 算法说明 -->
        <control-description-vue
          v-if="controlDetail !== null"
          :data="controlDetail" />
      </div>
      <template #action>
        <bk-button
          v-bk-tooltips="{
            content: typeTableLoading ? t('数据加载中，请稍等') : '',
            disabled: !typeTableLoading,
          }"
          :disabled="typeTableLoading"
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
<script setup lang="ts">
  import { InfoBox } from 'bkui-vue';
  import {
    computed,
    h,
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

  import MetaManageService from '@service/meta-manage';
  import StrategyManageService from '@service/strategy-manage';

  import type ControlModel from '@model/control/control';
  import CommonDataModel from '@model/strategy/common-data';
  import StrategyModel from '@model/strategy/strategy';

  import useRecordPage from '@hooks/use-record-page';
  import useRequest from '@hooks/use-request';
  import useRouterBack from '@hooks/use-router-back';

  import CardPartVue from './components/card-part.vue';
  import ControlDescriptionVue from './components/control-description.vue';
  import Customize from './components/customize/index.vue';
  import ReferenceModel from './components/reference-model/index.vue';

  type ItemType = {
    label: string,
    value: string
    config?: any;
  }

  interface IFormData {
    strategy_id?: number,
    strategy_name: string,
    tags: Array<string>,
    description: string,
    configs: Record<string, any>,
    control_id?: string,
    control_version?: number,
    status: string,
    risk_level: string,
    risk_hazard: string,
    risk_guidance: string,
    strategy_type: string,
  }

  interface Emits {
    (e: 'nextStep', step: number, params: IFormData): void;
  }
  interface Props {
    editData: StrategyModel
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

  const strategyWayComMap: Record<string, any> = {
    rule: Customize,
    model: ReferenceModel,
  };

  const comRef = ref();
  const formRef = ref();
  const tagData = ref<Array<{
    id: string;
    name: string
  }>>([]);
  const canEditRiskLevel = ref(false);
  const formData = ref<IFormData>({
    strategy_name: '',
    tags: [],
    description: '',
    configs: {
    },
    control_id: '',
    status: '',
    risk_level: '',
    risk_hazard: '',
    risk_guidance: '',
    strategy_type: 'rule',
  });
  const isStockData = ref(false); // 是否是存量数据
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
    strategy_type: [
      {
        validator: (value: string) => !!value,
        message: t('配置方式不能为空'),
        trigger: 'change',
      },
    ],
    'configs.config_type': [
      {
        validator: (value: Array<string>) => !!value,
        message: t('数据源不能为空'),
        trigger: 'change',
      }],
    'configs.data_source.system_id': [
      {
        validator: (value: Array<string>) => !!value && value.length > 0,
        message: t('系统不能为空'),
        trigger: 'change',
      }],
    'configs.data_source.system_ids': [
      {
        validator: (value: Array<string>) => !!value && value.length > 0,
        message: t('系统不能为空'),
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
    'configs.schedule_config.count_freq': [
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
    // 调度方式
    'configs.data_source.source_type': [
      {
        validator: (value: string) => !!value,
        message: t('调度方式不能为空'),
        trigger: 'change',
      },
    ],
  };

  const strategyTagMap = ref<Record<string, string>>({});
  const strategyWayList = ref<Array<ItemType>>([]); // 配置方式列表
  const riskLevelList = ref<Array<ItemType>>([]); // 风险等级列表
  const controlDetail = ref<ControlModel | null>(null);

  const riskLevelTipMap: Record<'HIGH' | 'MIDDLE' | 'LOW', string> = {
    HIGH: t('问题存在影响范围很大或程度很深，或已导致重大错报、合规违规或资产损失风险，不处理可能产生更严重问题，需立即介入并优先处置'),
    MIDDLE: t('问题存在影响范围较大或程度较深，可能影响局部业务效率或安全性，需针对性制定措施并跟踪整改'),
    LOW: t('问题存在但影响范围有限，短期内不会对有重大问题，可通过常规流程优化解决'),
  };

  const typeTableLoading = computed(() => comRef.value?.typeTableLoading);

  // 编辑
  const setFormData = (editData: StrategyModel) => {
    formData.value.status = editData.status;
    formData.value.strategy_id = editData.strategy_id;
    formData.value.strategy_name = isCloneMode ? `${editData.strategy_name}_copy` : editData.strategy_name;
    formData.value.tags = editData.tags ? editData.tags.map(item => item.toString()) : [];
    formData.value.description = editData.description;
    formData.value.risk_hazard = editData.risk_hazard;
    formData.value.risk_guidance = editData.risk_guidance;
    formData.value.risk_level = editData.risk_level;
    // 存量数据
    if (!editData.strategy_type) {
      isStockData.value = true;
    }
    formData.value.strategy_type = editData.strategy_type || 'referenceModel';

    // 是否允许编辑风险等级
    // canEditRiskLevel.value = !!editData.risk_level;
  };

  const {
    loading: commonLoading,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: new CommonDataModel(),
    manual: true,
    onSuccess: (data) => {
      riskLevelList.value = data.risk_level.map(item => ({
        ...item,
        config: {
          tips: riskLevelTipMap[item.value as 'HIGH' | 'MIDDLE' | 'LOW'],
        },
      }));
      strategyWayList.value = [{
        label: t('自定义规则审计'),
        value: 'rule',
        config: {
          tips: t('指根据目前审计中可用的日志、资产数据，直接配置规则，得到审计结果的方式。适用于大部分复杂程度不高的场景策略。'),
        },
      }, {
        label: t('引入模型审计'),
        value: 'model',
        config: {
          tips: t('指先通过蓝鲸 BKBase 的 AIOps 内开发场景模型后，在审计中心内配置字段映射生成策略的方式。适用于对 aiops 有数据开发能力，且需要实现的审计方案较复杂的情况。'),
        },
      }];
    },
  });

  // 获取标签列表
  const {
    loading: tagLoading,
  } = useRequest(MetaManageService.fetchTags, {
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

  const handleStrategyWay = (way: string) => {
    if (!formData.value.strategy_type
      || (!formData.value.configs.config_type && formData.value.strategy_type === 'rule')
      || (!formData.value.control_id && formData.value.strategy_type === 'model')) {
      formData.value.strategy_type = way;
      formRef.value.validate('strategy_type');
      return;
    }
    InfoBox({
      type: 'warning',
      title: t('切换配置方式请注意'),
      subTitle: () => h('div', {
        style: {
          color: '#4D4F56',
          backgroundColor: '#f5f6fa',
          height: '46px',
          lineHeight: '46px',
          borderRadius: '2px',
          fontSize: '14px',
        },
      }, t('切换后，已配置的数据将被清空。是否继续？')),
      confirmText: t('继续切换'),
      cancelText: t('取消'),
      headerAlign: 'center',
      contentAlign: 'center',
      footerAlign: 'center',
      onConfirm() {
        if (way === 'rule') {
          controlDetail.value = null;
          delete formData.value.control_id;
          delete formData.value.control_version;
        }
        formData.value.configs = {};
        formData.value.strategy_type = way;
        formRef.value.validate('strategy_type');
      },
    });
  };

  // 设置风险等级
  const handleLevel = (level: string) => {
    formData.value.risk_level = level;
    formRef.value.validate('risk_level');
  };

  // 更新方案详情
  const updateControlDetail = (detail: ControlModel) => {
    controlDetail.value = detail;
  };

  const updateFormData = (data: Record<string, any>) => {
    formData.value = {
      ...formData.value,
      ...data,
    };
    if (formData.value.configs.config_type) {
      formRef.value.clearValidate('configs.config_type');
    }
  };

  // 下一步
  const handleNext = () => {
    const tastQueue = [formRef.value.validate()];
    // 有配置组件
    if (formData.value.strategy_type) {
      tastQueue.push(comRef.value.getValue?.());
    }
    Promise.all(tastQueue).then(() => {
      if (!isEditMode) {
        delete formData.value.strategy_id;
      }
      const baseParams = { ...formData.value };
      if (baseParams.tags) {
        baseParams.tags = baseParams.tags.map(item => (strategyTagMap.value[item] ? strategyTagMap.value[item] : item));
      }
      // 获取审计参数（自定义规则审计、引入模型审计）
      const fields = comRef.value.getFields();
      // 非联表不需要link_table参数
      if (fields.configs.config_type !== 'LinkTable' && fields.configs.data_source) {
        fields.configs.data_source.link_table = null;
      }
      // 非周期不需要schedule_config
      if (fields.configs.data_source && fields.configs.data_source.source_type !== 'batch_join_source') {
        fields.configs.schedule_config = undefined;
      }
      // 合并参数
      const params = {
        ...baseParams,
        ...fields,
      };
      emits('nextStep', 2, params);
    });
  };

  watch(() => props.editData, (data) => {
    if (isEditMode || isCloneMode) {
      setFormData(data);
    }
  });

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
</script>
<style lang="postcss" scoped>
.create-strategy-page {
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

      /* max-width: 1280px; */

      :deep(.bk-button-group) {
        .bk-button {
          padding: 0 35px;
          font-size: 12px;
        }
      }

      .risk-level-group {
        :deep(.bk-button-group) {
          .bk-button {
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
</style>
<style>
.strategy-way-tips {
  width: 400px;
  word-break: break-all;
}
</style>
