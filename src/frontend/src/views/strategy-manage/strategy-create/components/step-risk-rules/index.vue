<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
-->
<template>
  <smart-action
    class="create-strategy-page"
    :offset-target="getSmartActionOffsetTarget">
    <div class="create-strategy-main">
      <audit-form
        ref="formRef"
        class="strategt-form"
        form-type="vertical"
        :model="stepFormData"
        :rules="rules">
        <card-part-vue :title="t('风险发现规则')">
          <template #content>
            <component
              :is="strategyWayComMap[stepFormData.strategy_type]"
              ref="comRef"
              :edit-data="editData"
              :parent-configs="parentConfigs"
              :parent-form-data="parentFormData"
              step-mode="rules"
              @update-form-data="updateFormData" />
          </template>
        </card-part-vue>
      </audit-form>
    </div>
    <template #action>
      <bk-button @click="handlePrevious">
        {{ t('上一步') }}
      </bk-button>
      <bk-button
        class="ml8"
        theme="primary"
        @click="handleNext">
        {{ t('下一步') }}
      </bk-button>
      <bk-button
        class="ml8"
        @click="handleSaveDraft">
        {{ t('保存草稿') }}
      </bk-button>
      <bk-button
        class="ml8"
        @click="handleCancel">
        {{ t('取消') }}
      </bk-button>
    </template>
  </smart-action>
</template>
<script setup lang="ts">
  import {
    computed,
    provide,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import StrategyModel from '@model/strategy/strategy';

  import CardPartVue from '../step1/components/card-part.vue';
  import Customize from '../step1/components/customize/index.vue';
  import ReferenceModel from '../step1/components/reference-model/index.vue';

  interface IFormData {
    strategy_id?: number,
    strategy_name: string,
    strategy_type: string,
    control_id?: string,
    control_version?: number,
    configs: Record<string, any>,
    status: string,
    risk_level: string,
  }

  interface Props {
    editData: StrategyModel,
    formData: Record<string, any>,
  }

  interface Emits {
    (e: 'nextStep', step: number, params: Record<string, any>): void;
    (e: 'previousStep', step: number, params: Record<string, any>): void;
    (e: 'saveDraft', params: Record<string, any>): void;
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const router = useRouter();
  const route = useRoute();
  const { t } = useI18n();

  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';

  const strategyWayComMap: Record<string, any> = {
    rule: Customize,
    model: ReferenceModel,
  };

  const formRef = ref();
  provide('strategyStep1FormRef', formRef);
  const comRef = ref();

  const stepFormData = ref<IFormData>({
    strategy_name: '',
    strategy_type: 'rule',
    configs: {},
    status: '',
    risk_level: 'MIDDLE',
  });

  const parentFormData = computed(() => props.formData ?? {});
  const parentConfigs = computed(() => props.formData?.configs ?? {});

  const rules = {
    'configs.agg_condition': [
      {
        validator: (val: Array<Record<string, any>>) => val?.length > 0,
        message: t('检测条件不能为空'),
        trigger: 'none',
      },
    ],
    'configs.agg_dimension': [
      {
        validator: (value: Array<string>) => value?.length > 0,
        message: t('统计字段不能为空'),
        trigger: 'change',
      },
    ],
  };

  watch(
    () => props.formData,
    (data) => {
      if (!data) return;
      stepFormData.value.strategy_type = data.strategy_type || 'rule';
      stepFormData.value.strategy_name = data.strategy_name ?? '';
      stepFormData.value.control_id = data.control_id;
      stepFormData.value.control_version = data.control_version;
      stepFormData.value.status = data.status ?? '';
      stepFormData.value.risk_level = data.risk_level || 'MIDDLE';
      if (data.strategy_id) {
        stepFormData.value.strategy_id = data.strategy_id;
      }
    },
    { immediate: true, deep: true },
  );

  watch(
    () => props.editData,
    (data) => {
      if ((isEditMode || isCloneMode) && data?.strategy_id) {
        stepFormData.value.strategy_type = data.strategy_type || 'rule';
      }
    },
    { immediate: true },
  );

  const updateFormData = (data: Record<string, any>) => {
    stepFormData.value = {
      ...stepFormData.value,
      ...data,
    };
  };

  const getSmartActionOffsetTarget = () => document.querySelector('.create-strategy-page');

  const buildStepParams = () => {
    const baseParams = { ...stepFormData.value };
    const fields = comRef.value?.getFields?.({ forValidate: false }) ?? { configs: stepFormData.value.configs };
    const mergedConfigs = {
      ...(parentFormData.value.configs ?? {}),
      ...(fields.configs ?? {}),
    };
    if (stepFormData.value.strategy_type === 'rule') {
      if (mergedConfigs.config_type !== 'LinkTable' && mergedConfigs.data_source) {
        mergedConfigs.data_source.link_table = null;
      }
    }
    return {
      ...parentFormData.value,
      ...baseParams,
      configs: mergedConfigs,
      control_id: fields.control_id ?? baseParams.control_id ?? parentFormData.value.control_id,
      control_version: fields.control_version ?? baseParams.control_version ?? parentFormData.value.control_version,
    };
  };

  const handlePrevious = () => {
    emits('previousStep', 1, buildStepParams());
  };

  const handleNext = () => {
    const runValidate = () => {
      setTimeout(() => {
        const tasks = [formRef.value.validate()];
        if (stepFormData.value.strategy_type === 'model' && comRef.value?.getValue) {
          tasks.push(comRef.value.getValue());
        }
        Promise.all(tasks).then(() => {
          emits('nextStep', 3, buildStepParams());
        });
      }, 0);
    };
    if (stepFormData.value.strategy_type === 'rule' && comRef.value?.getFields) {
      const fields = comRef.value.getFields({ forValidate: true });
      stepFormData.value.configs = {
        ...parentConfigs.value,
        ...fields.configs,
      };
    }
    runValidate();
  };

  const handleSaveDraft = () => {
    emits('saveDraft', buildStepParams());
  };

  const handleCancel = () => {
    router.push({ name: 'strategyList' });
  };
</script>
<style lang="postcss" scoped>
.create-strategy-page {
  .create-strategy-main {
    padding-top: 4px;
    margin-bottom: 24px;
  }
}
</style>
