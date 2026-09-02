<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
-->
<!-- step2 单据展示 -->
<template>
  <smart-action
    class="create-strategy-page document-display-step"
    :offset-target="getSmartActionOffsetTarget">
    <div class="create-strategy-main">
      <card-part-vue :title="t('风险字段配置')">
        <template #content>
          <strategy-table
            ref="strategyTableRef"
            :data="editData"
            :select="select"
            :strategy-id="editData.strategy_id"
            :strategy-name="strategyName"
            :strategy-type="strategyType" />
        </template>
      </card-part-vue>
      <card-part-vue :title="t('事件字段配置')">
        <template #content>
          <event-table
            ref="eventRef"
            :data="editData"
            :select="select"
            :strategy-id="editData.strategy_id"
            :strategy-name="strategyName"
            :strategy-type="strategyType" />
        </template>
      </card-part-vue>
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
        v-if="showSaveDraftButton"
        class="ml8"
        @click="handleSaveDraft">
        {{ t('保存草稿') }}
      </bk-button>
      <bk-button
        class="ml8"
        @click="handleCancel">
        {{ t('取消') }}
      </bk-button>
      <bk-button
        style="margin-left: 48px;"
        @click="handlePreview">
        {{ t('预览') }}
      </bk-button>
    </template>
  </smart-action>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import { computed, inject, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import DatabaseTableFieldModel from '@model/strategy/database-table-field';
  import StrategyModel from '@model/strategy/strategy';
  import StrategyFieldEvent from '@model/strategy/strategy-field-event';

  import CardPartVue from '../step1/components/card-part.vue';

  import EventTable from './components/event-table/index.vue';
  import StrategyTable from './components/strategy-table/index.vue';

  import { getStrategyRouteNames } from '../../../utils/strategy-routes';
  import { STRATEGY_SHOW_SAVE_DRAFT_KEY } from '../../composables/use-strategy-config-lock';

  interface IFormData {
    event_evidence_field_configs: StrategyFieldEvent['event_evidence_field_configs'],
    event_data_field_configs: StrategyFieldEvent['event_data_field_configs'],
    event_basic_field_configs: StrategyFieldEvent['event_basic_field_configs'],
    risk_meta_field_config: StrategyFieldEvent['risk_meta_field_config'],
  }

  interface Emits {
    (e: 'previousStep', step: number, params: IFormData): void;
    (e: 'nextStep', step: number, params: IFormData): void;
    (e: 'showPreview'): void;
    (e: 'saveDraft', params: IFormData): void;
  }
  interface Props {
    editData: StrategyModel,
    select: Array<DatabaseTableFieldModel>,
    strategyType: string,
    strategyName: string
  }

  defineProps<Props>();

  const emits = defineEmits<Emits>();

  const router = useRouter();
  const route = useRoute();
  const strategyRoutes = getStrategyRouteNames(route);
  const { t } = useI18n();
  const showSaveDraftButton = inject(STRATEGY_SHOW_SAVE_DRAFT_KEY, computed(() => true));

  const eventRef = ref();
  const strategyTableRef = ref();

  const getSmartActionOffsetTarget = () => document.querySelector('.create-strategy-page');

  const buildStepParams = (): IFormData => {
    const params: IFormData = _.cloneDeep(Object.assign(
      {},
      eventRef.value.getData(),
      strategyTableRef.value.getData(),
    ));
    params.event_basic_field_configs = params.event_basic_field_configs.map((item) => {
      cleanMapConfig(item);
      cleanDrillConfig(item);
      return item;
    });
    params.risk_meta_field_config = params.risk_meta_field_config.map((item) => {
      cleanMapConfig(item);
      cleanDrillConfig(item);
      return item;
    });
    params.event_data_field_configs = params.event_data_field_configs.map(cleanDrillConfig);
    params.event_evidence_field_configs = params.event_evidence_field_configs.map(cleanDrillConfig);
    return params;
  };

  const handlePreview = () => {
    emits('nextStep', 3, buildStepParams());
    emits('showPreview');
  };

  const handlePrevious = () => {
    emits('previousStep', 2, buildStepParams());
  };

  const handleCancel = () => {
    router.push({
      name: strategyRoutes.list,
    });
  };

  const handleNext = () => {
    eventRef.value.getValue().then(() => {
      emits('nextStep', 4, buildStepParams());
    });
  };

  const handleSaveDraft = () => {
    emits('saveDraft', buildStepParams());
  };

  const cleanDrillConfig = (item: IFormData['event_basic_field_configs'][0]) => {
    if (item.drill_config && !item.drill_config.length) {
      // eslint-disable-next-line no-param-reassign
      delete item.drill_config;
    }
    return item;
  };

  const cleanMapConfig = (item: IFormData['event_basic_field_configs'][0]) => {
    if (item.map_config) {
      if (!item.map_config.source_field && !item.map_config.target_value) {
        // eslint-disable-next-line no-param-reassign
        delete item.map_config;
      } else if (item.map_config.source_field && item.map_config.target_value) {
        // eslint-disable-next-line no-param-reassign
        item.map_config.source_field = undefined;
      }
    }
    return item;
  };
</script>
<style lang="postcss" scoped>
.document-display-step {
  .create-strategy-main {
    padding-top: 4px;
    margin-bottom: 24px;
  }

  :deep(.strategy-create-card-part) {
    margin-bottom: 16px;

    > .card-part-content {
      padding: 16px 24px 24px;
    }
  }

  :deep(.strategy-table),
  :deep(.event-table) {
    margin-bottom: 0;
    border-radius: 2px;
    overflow: hidden;
  }
}
</style>
