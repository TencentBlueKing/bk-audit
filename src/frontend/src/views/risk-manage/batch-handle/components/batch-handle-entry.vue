<template>
  <span
    v-bk-tooltips="tooltip"
    data-testid="batch-handle-button">
    <auth-button
      action-id="process_risk"
      :disabled="!availability.enabled"
      outline
      :permission="permission"
      theme="primary"
      @click="handleOpen">
      {{ t('批量处理') }}
    </auth-button>
  </span>
  <batch-process-dialog
    ref="processDialogRef"
    :availability="availability"
    :count="selectionMeta.count"
    :event-fields="visibleEventFields"
    :risk-fields="riskFields"
    :risk-ids="riskIds"
    :scope="scope"
    @success="handleSuccess" />
  <batch-confirm-dialog
    ref="confirmDialogRef"
    :event-fields="visibleEventFields"
    :risk-fields="riskFields"
    :risk-ids="riskIds"
    @success="handleSuccess" />
</template>

<script setup lang="ts">
  import { computed, nextTick, onMounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskManageService from '@service/risk-manage';

  import useRequest from '@hooks/use-request';

  import {
    evaluateBatchSelection,
    hasBatchProcessPermission,
    type BatchRiskRow,
  } from '../evaluate';

  import BatchConfirmDialog from './batch-confirm-dialog.vue';
  import BatchProcessDialog from './batch-process-dialog.vue';

  interface FieldItem {
    id: string;
    name: string;
  }

  interface ListExpose {
    getSelection?: () => Array<Record<string, any>>;
    getSelectedKeys?: () => Array<string | number>;
    clearSelection?: () => void;
    refreshList?: () => void;
  }

  interface Props {
    listRef?: ListExpose | null;
    scope?: 'scene' | 'all';
    selectionMeta: {
      count: number;
      mode: '' | 'page' | 'all';
      isSelectAll: boolean;
    };
    username?: string;
  }

  const props = withDefaults(defineProps<Props>(), {
    listRef: null,
    scope: 'scene',
    username: '',
  });

  const { t } = useI18n();
  const processDialogRef = ref<InstanceType<typeof BatchProcessDialog>>();
  const confirmDialogRef = ref<InstanceType<typeof BatchConfirmDialog>>();
  const rowCache = new Map<string, BatchRiskRow>();
  const selectedKeys = ref<string[]>([]);
  const eventFields = ref<FieldItem[]>([]);

  const rows = computed(() => selectedKeys.value
    .map(id => rowCache.get(id))
    .filter((row): row is BatchRiskRow => Boolean(row)));

  const availability = computed(() => evaluateBatchSelection(rows.value, {
    count: props.selectionMeta.count,
    incomplete: rows.value.length !== props.selectionMeta.count,
  }));

  const riskIds = computed(() => rows.value.map(row => String(row.risk_id)));

  const visibleEventFields = computed(() => (
    availability.value.strategyUnique ? eventFields.value : []
  ));

  const permission = computed(() => {
    if (!availability.value.enabled || !rows.value.length) {
      return true;
    }
    return rows.value.some(row => hasBatchProcessPermission(row, props.username));
  });

  const tooltip = computed(() => ({
    disabled: availability.value.enabled || !availability.value.reason,
    content: availability.value.reason ? t(availability.value.reason) : '',
  }));

  const normalizeFieldList = (data: unknown, eventField = false): FieldItem[] => {
    if (!Array.isArray(data)) {
      return [];
    }
    return data.map((item) => {
      const rawId = String(item?.id ?? item?.field_name ?? item?.key ?? '');
      const id = eventField && rawId && !rawId.startsWith('event_data.')
        ? `event_data.${rawId}`
        : rawId;
      const name = String(item?.name ?? item?.display_name ?? item?.description ?? id);
      return { id, name };
    }).filter(item => item.id);
  };

  const {
    data: riskFieldSource,
    run: fetchRiskFields,
  } = useRequest(RiskManageService.fetchFields, {
    defaultValue: [],
    manual: true,
  });

  const riskFields = computed(() => normalizeFieldList(riskFieldSource.value));

  const { run: fetchEventFields } = useRequest(RiskManageService.fetchEventFields, {
    defaultValue: [],
    manual: true,
    onSuccess(data: unknown) {
      eventFields.value = normalizeFieldList(data, true);
    },
  });

  const sync = () => {
    const list = props.listRef;
    if (!list?.getSelectedKeys || !list.getSelection) {
      selectedKeys.value = [];
      return;
    }
    const keys = list.getSelectedKeys().map(key => String(key));
    const keySet = new Set(keys);
    list.getSelection().forEach((row) => {
      const id = String(row.risk_id);
      if (!keySet.has(id)) {
        return;
      }
      rowCache.set(id, {
        risk_id: row.risk_id,
        status: row.status,
        strategy_id: row.strategy_id,
        scene_id: row.scene_id,
        permission: row.permission,
        current_operator: row.current_operator,
      });
    });
    Array.from(rowCache.keys()).forEach((id) => {
      if (!keySet.has(id)) {
        rowCache.delete(id);
      }
    });
    selectedKeys.value = keys;
  };

  watch(
    () => [props.selectionMeta.count, props.selectionMeta.mode, props.selectionMeta.isSelectAll],
    () => {
      nextTick(sync);
    },
  );

  watch(
    () => [availability.value.strategyUnique, availability.value.strategyId] as const,
    ([unique, strategyId]) => {
      if (!unique || !strategyId) {
        eventFields.value = [];
        return;
      }
      fetchEventFields({ strategy_ids: [strategyId] });
    },
  );

  const handleOpen = () => {
    if (!availability.value.enabled) {
      return;
    }
    if (availability.value.dialog === 'confirm') {
      confirmDialogRef.value?.open();
      return;
    }
    processDialogRef.value?.open();
  };

  const handleSuccess = () => {
    rowCache.clear();
    selectedKeys.value = [];
    props.listRef?.clearSelection?.();
    props.listRef?.refreshList?.();
  };

  onMounted(() => {
    fetchRiskFields();
  });

  defineExpose({ sync });
</script>
