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
  <!-- 步进条 -->
  <teleport to="#teleport-nav-step">
    <bk-steps
      v-model:cur-step="currentStep"
      class="strategy-upgrade-step"
      :steps="steps" />
  </teleport>

  <keep-alive>
    <component
      :is="renderCom"
      ref="comRef"
      :edit-data="editData"
      :form-data="formData"
      :is-edit-data-loading="isEditDataLoading"
      :select="formData.configs.select"
      :strategy-name="formData.strategy_name"
      :strategy-type="formData.strategy_type"
      style="margin-bottom: 24px;"
      @cancel="handleCancel"
      @next-step="(step: any, params: any) => handleNextStep(step, params)"
      @previous-step="(step: any) => currentStep = step"
      @show-preview="showPreview = true"
      @submit-data="handleSubmit" />
  </keep-alive>

  <audit-sideslider
    ref="sidesliderRef"
    v-model:isShow="showPreview"
    :show-footer="false"
    :title="t('风险单预览')"
    :width="960">
    <div>
      <preview :risk-data="formData" />
    </div>
  </audit-sideslider>
</template>

<script setup lang='ts'>
  import { InfoBox } from 'bkui-vue';
  import _ from 'lodash';
  import {
    computed,
    onMounted,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import StrategyManageService from '@service/strategy-manage';

  import StrategyModel from '@model/strategy/strategy';
  import StrategyFieldEvent from '@model/strategy/strategy-field-event';

  import eventReport from './components/event-report/index.vue';
  import Preview from './components/preview/index.vue';
  import Step1 from './components/step1/index.vue';
  import Step2 from './components/step2/index.vue';
  import Step3 from './components/step3/index.vue';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';

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
    risk_title: string,
    strategy_type: string,
    event_data_field_configs: StrategyFieldEvent['event_data_field_configs'],
    event_basic_field_configs: StrategyFieldEvent['event_basic_field_configs'],
    event_evidence_field_configs: StrategyFieldEvent['event_evidence_field_configs'],
    risk_meta_field_config: StrategyFieldEvent['risk_meta_field_config'],
    processor_groups: [],
    notice_groups: []
    report_enabled: boolean,
    report_config: Record<string, any>,
  }

  const router = useRouter();
  const route = useRoute();
  const { messageSuccess } = useMessage();
  const { t } = useI18n();

  const comMap = {
    1: Step1,
    2: Step2,
    3: eventReport,
    4: Step3,
  };
  const steps = [
    { title: t('风险发现') },
    { title: t('单据展示') },
    { title: t('事件调查报告') },
    { title: t('其他配置') },
  ];
  const currentStep = ref(1);
  const comRef = ref();

  const renderCom = computed(() => comMap[currentStep.value as keyof typeof comMap]);

  let isSwitchSuccess = false;
  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';

  const showPreview = ref(false);
  const controlTypeId = ref('');// 方案类型id
  const editData = ref(new StrategyModel());
  const formData = ref<IFormData>({
    strategy_name: '',
    tags: [],
    description: '',
    control_id: '',
    configs: {},
    status: '',
    risk_level: '',
    risk_hazard: '',
    risk_guidance: '',
    risk_title: '',
    strategy_type: '',
    event_data_field_configs: [],
    event_basic_field_configs: [],
    event_evidence_field_configs: [],
    risk_meta_field_config: [],
    processor_groups: [],
    notice_groups: [],
    report_enabled: false,
    report_config: {},
  });

  // 编辑状态获取数据
  const {
    run: fetchStrategyList,
    loading: isEditDataLoading,
  } = useRequest(StrategyManageService.fetchStrategyList, {
    defaultValue: {
      results: [],
      page: 1,
      num_pages: 1,
      total: 1,
    },
    onSuccess: (data) => {
      // eslint-disable-next-line prefer-destructuring
      editData.value = data.results[0];
      editData.value.event_basic_field_configs = editData.value.event_basic_field_configs.map((item) => {
        if (item.drill_config && !Array.isArray(item.drill_config)) {
          // eslint-disable-next-line no-param-reassign
          item.drill_config = [item.drill_config];
          item.drill_config.forEach((drill) => {
            if (!drill.drill_name) {
              // eslint-disable-next-line no-param-reassign
              drill.drill_name = '';
            }
          });
        }
        return item;
      });
      editData.value.event_data_field_configs = editData.value.event_data_field_configs.map((item) => {
        if (item.drill_config && !Array.isArray(item.drill_config)) {
          // eslint-disable-next-line no-param-reassign
          item.drill_config = [item.drill_config];
          item.drill_config.forEach((drill) => {
            if (!drill.drill_name) {
              // eslint-disable-next-line no-param-reassign
              drill.drill_name = '';
            }
          });
        }
        return item;
      });
      editData.value.event_evidence_field_configs = editData.value.event_evidence_field_configs.map((item) => {
        if (item.drill_config && !Array.isArray(item.drill_config)) {
          // eslint-disable-next-line no-param-reassign
          item.drill_config = [item.drill_config];
          item.drill_config.forEach((drill) => {
            if (!drill.drill_name) {
              // eslint-disable-next-line no-param-reassign
              drill.drill_name = '';
            }
          });
        }
        return item;
      });
      editData.value.risk_meta_field_config = editData.value.risk_meta_field_config.map((item) => {
        if (item.drill_config && !Array.isArray(item.drill_config)) {
          // eslint-disable-next-line no-param-reassign
          item.drill_config = [item.drill_config];
          item.drill_config.forEach((drill) => {
            if (!drill.drill_name) {
              // eslint-disable-next-line no-param-reassign
              drill.drill_name = '';
            }
          });
        }
        return item;
      });
    },
  });

  // 保存接口
  const {
    run: saveStrategy,
  } = useRequest(isEditMode
    ? StrategyManageService.updateStrategy
    : StrategyManageService.saveStrategy, {
    defaultValue: {},
    onSuccess: (data) => {
      if (isEditMode && formData.value.status === 'running') {
        window.changeConfirm = false;
        router.push({
          name: 'strategyList',
        });
        messageSuccess(t('编辑成功'));
        return;
      }
      const SendSwitchStrategy = (toggle: boolean) => {
        messageSuccess(isEditMode ? t('编辑成功') : t('新建成功'));
        fetchSwitchStrategy({
          strategy_id: data.strategy_id,
          toggle,
        }).then(() => {
          if (isSwitchSuccess) return;
          window.changeConfirm = false;
          router.push({
            name: 'strategyList',
          });
        });
      };
      // 常规策略
      if (controlTypeId.value === 'BKM' && (!isEditMode || !(formData.value.status === 'running'))) {
        isSwitchSuccess = false;
        InfoBox({
          title: t('是否启用该策略'),
          subTitle: t('启用策略将开始按照策略进行审计并输出异常事件，请确认是否启用该策略'),
          confirmText: t('启用'),
          cancelText: t('暂不启用'),
          headerAlign: 'center',
          contentAlign: 'center',
          footerAlign: 'center',
          onConfirm() {
            SendSwitchStrategy(true);
          },
          onClose() {
            SendSwitchStrategy(false);
          },
        });
      } else {
        messageSuccess(isEditMode ? t('编辑成功') : t('新建成功'));
        window.changeConfirm = false;
        router.push({
          name: 'strategyList',
        });
      }
    },
  });

  // 启用该策略
  const {
    run: fetchSwitchStrategy,
  } = useRequest(StrategyManageService.fetchSwitchStrategy, {
    defaultValue: {},
    onSuccess: () => {
      window.changeConfirm = false;
      router.push({
        name: 'strategyList',
      });
      isSwitchSuccess = true;
    },
  });

  // 提交
  const handleSubmit = () => {
    const params = _.cloneDeep(formData.value);
    console.log('params', params);
    // ai策略
    if (controlTypeId.value !== 'BKM') {
      InfoBox({
        title: t('策略提交确认'),
        subTitle: t('策略一旦提交，审计中心会开启策略配置的相关检测，若有风险命中策略会立即输出风险，请仔细检查策略配置是否正确以免输出错误风险。'),
        confirmText: t('提交'),
        cancelText: t('取消'),
        headerAlign: 'center',
        contentAlign: 'center',
        footerAlign: 'center',
        onConfirm() {
          saveStrategy(params);
        },
      });
    } else {
      saveStrategy(params);
    }
  };

  const handleNextStep = (step: number, params: any) => {
    // 更新formData
    Object.assign(formData.value, params);
    currentStep.value = step;
  };

  const handleCancel = () => {
    router.push({
      name: 'strategyList',
    });
  };

  onMounted(() => {
    if (isEditMode || isCloneMode) {
      fetchStrategyList({
        page: 1,
        page_size: 1,
        strategy_id: route.params.id,
      });
    }
  });

</script>
<style scoped>
.strategy-upgrade-step {
  width: 650px;
  margin: 0 auto;
  transform: translateX(-86px);

  :deep(.bk-step ) {
    display: flex;

    .bk-step-content {
      display: flex;
    }
  }
}
</style>
