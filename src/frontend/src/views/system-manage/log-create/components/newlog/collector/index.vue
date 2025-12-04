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
  <div class="log-create-collector">
    <div class="log-create-collector-container">
      <!-- 左侧步骤条 -->
      <div class="log-create-collector-steps">
        <bk-steps
          v-model:cur-step="currentStep"
          class="steps-vertical"
          direction="vertical"
          :steps="steps" />
      </div>

      <!-- 右侧表单内容 -->
      <div class="log-create-collector-content">
        <keep-alive>
          <component
            :is="renderStepCom"
            :form-data="formData"
            @cancel="handleCancel"
            @next="handleNext"
            @previous="handlePrevious"
            @update:form-data="handleFormDataUpdate" />
        </keep-alive>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import useUrlSearch from '@hooks/use-url-search';

  import Step1 from './pages/step1/index.vue';
  import Step2 from './pages/step2/index.vue';
  import Step3 from './pages/step3/index.vue';
  import Step4 from './pages/step4/index.vue';
  import Step5 from './pages/step5/index.vue';


  // interface Emits {
  //   (e: 'change', step: number, formData: Record<string, any>): void
  // }

  // const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const router = useRouter();
  const route = useRoute();
  const { appendSearchParams } = useUrlSearch();

  const routeStep = Number(route.query.step);
  const currentStep = ref(Number.isFinite(routeStep) && routeStep >= 1 && routeStep <= 5 ? routeStep : 1);

  const steps = [
    {
      title: t('前置：记录日志'),
      description: t('根据“审计中心日志标准”规范要求使用 SDK 或Log 记录日志'),
    },
    {
      title: t('采集配置'),
      description: t('新建后选择物理或容器环境配置相关采集的基础信息与日志过滤'),
    },
    {
      title: t('采集下发'),
      description: t('确认采集目标的采集状态，确认状态成功之后进入下一步'),
    },
    {
      title: t('字段清洗'),
      description: t('根据上报数据,配置字段映射后生成标准化日志'),
    },
    {
      title: t('数据验证 (可选)'),
      description: t('验证上报数据是否有和是否正确'),
    },
  ];

  const stepComMap = {
    1: Step1,
    2: Step2,
    3: Step3,
    4: Step4,
    5: Step5,
  };

  const renderStepCom = computed(() => stepComMap[currentStep.value as keyof typeof stepComMap]);

  const formData = ref({
    record_log_type: 'SDK',
    select_sdk_type: 'PYTHON_SDK',
    notice: {
      read_requirement: false,
      read_standard: false,
    },
    is_reported: false,
    collector_config_name: '',
    collector_config_name_en: '',
    environment: 'linux',
    bk_biz_id: undefined as number | undefined,
    target_node_type: '',
    target_nodes: [] as Array<Record<string, any>>,
    data_encoding: '',
    params: {
      paths: [''],
      conditions: {
        type: 'match',
        match_type: '',
        match_content: '',
        separator: '',
        separator_filters: [
          {
            logic_op: 'AND',
            fieldindex: '',
            word: '',
          },
        ],
      },
    },
    bcs_cluster_id: '',
    yaml_config: '',
  });

  const handleFormDataUpdate = (...args: any[]) => {
    const value = args[0] as Record<string, any>;
    formData.value = { ...formData.value, ...value };
  };

  const handlePrevious = (...args: any[]) => {
    const targetStep = args[0] as number | undefined;
    if (targetStep) {
      currentStep.value = targetStep;
      appendSearchParams({
        step: currentStep.value,
      });
      return;
    }
    if (currentStep.value > 1) {
      currentStep.value -= 1;
      appendSearchParams({
        step: currentStep.value,
      });
    }
  };

  const handleNext = (...args: any[]) => {
    const targetStep = args[0] as number | undefined;
    const formDataArg = args[1] as Record<string, any> | undefined;
    if (formDataArg) {
      handleFormDataUpdate(formDataArg);
    }
    const nextStep = targetStep ?? currentStep.value + 1;
    if (nextStep <= steps.length) {
      currentStep.value = nextStep;
      appendSearchParams({
        step: currentStep.value,
      });
    }
  };

  const handleCancel = () => {
    router.back();
  };

</script>

<style scoped lang="postcss">
.log-create-collector {
  min-height: calc(100vh - 200px);
  background: #fff;
  border: 1px solid #dcdee5;
  box-shadow: 0 2px 4px 0 #1919290d;
}

.log-create-collector-container {
  display: flex;
  gap: 24px;
  min-height: calc(100vh - 202px);
}

.log-create-collector-steps {
  width: 200px;
  flex-shrink: 0;
  padding: 24px;
  background-color: #fafbfd;
  border-right: 1px solid #dcdee5;

  .steps-vertical {
    max-height: 800px;

    :deep(.bk-step) {
      padding-left: 0;
    }

    :deep(.current) {
      position: relative;
      overflow: visible;

      .bk-step-content {
        &::before {
          position: absolute;
          top: 4px;
          right: -24px;
          width: 0;
          height: 0;
          border-top: 8px solid transparent;
          border-right: 8px solid #dcdee5;
          border-bottom: 8px solid transparent;
          content: '';
        }

        &::after {
          position: absolute;
          top: 4px;
          right: -25px;
          width: 0;
          height: 0;
          border-top: 8px solid transparent;
          border-right: 8px solid #fff;
          border-bottom: 8px solid transparent;
          content: '';
        }
      }
    }

    :deep(.bk-step-title) {
      position: relative;
      font-size: 14px;
      font-weight: 600;
      color: #313238;
    }

    :deep(.bk-step-description) {
      max-width: 120px;
      margin-top: 4px;
      font-size: 12px;
      color: #979ba5;
    }
  }
}

.log-create-collector-content {
  display: flex;
  width: calc(100% - 200px);
  padding: 24px;
  padding-left: 0;
  flex-direction: column;
  gap: 24px;
}


</style>
