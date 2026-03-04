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
  <div class="log-create-bkbase">
    <div class="log-create-bkbase-container">
      <!-- 左侧步骤条 -->
      <div class="log-create-bkbase-steps">
        <bk-steps
          v-model:cur-step="currentStep"
          class="steps-vertical"
          direction="vertical"
          :steps="steps" />
      </div>

      <!-- 右侧表单内容 -->
      <div class="log-create-bkbase-content">
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

  // interface Emits {
  //   (e: 'change', step: number, formData: Record<string, any>): void
  // }

  // const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const router = useRouter();
  const route = useRoute();
  const { appendSearchParams } = useUrlSearch();

  const routeStep = Number(route.query.step);
  const currentStep = ref(Number.isFinite(routeStep) && routeStep >= 1 && routeStep <= 3 ? routeStep : 1);

  const steps = [
    {
      title: t('选择数据'),
      description: t('选择在计算平台已有的数据'),
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
  };

  const renderStepCom = computed(() => stepComMap[currentStep.value as keyof typeof stepComMap]);

  const formData = ref({
    bk_biz_id: '',
    bk_data_id: '',
    custom_collector_ch_name: '',
    custom_collector_en_name: '',
    notice: {
      read_requirement: '',
      read_standard: '',
    },
  });

  const handleFormDataUpdate = (...args: any[]) => {
    const value = args[0] as Record<string, any>;
    formData.value = { ...formData.value, ...value };
  };

  const handlePrevious = () => {
    console.log('handlePrevious', currentStep.value);
    if (currentStep.value > 1) {
      currentStep.value -= 1;
      appendSearchParams({
        step: currentStep.value,
      });
    }
  };

  const handleNext = () => {
    if (currentStep.value < steps.length) {
      currentStep.value += 1;
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
.log-create-bkbase {
  min-height: calc(100vh - 200px);
  background: #fff;
  border: 1px solid #dcdee5;
  box-shadow: 0 2px 4px 0 #1919290d;
}

.log-create-bkbase-container {
  display: flex;
  gap: 24px;
  min-height: calc(100vh - 202px);
}

.log-create-bkbase-steps {
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

.log-create-bkbase-content {
  display: flex;
  width: calc(100% - 200px);
  padding: 24px;
  padding-left: 0;
  flex: 1;
  flex-direction: column;
  gap: 24px;
}


</style>
