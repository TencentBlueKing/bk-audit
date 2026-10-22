<template>
  <span
    v-bk-tooltips="tooltip"
    class="batch-handle-btn-wrapper"
    :class="{ 'is-batch-disabled': !availability.enabled }"
    data-testid="batch-handle-button">
    <auth-button
      action-id="process_risk"
      :disabled="!availability.enabled"
      :loading="opening"
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
    :username="username"
    @success="handleSuccess" />
  <batch-confirm-dialog
    ref="confirmDialogRef"
    :event-fields="visibleEventFields"
    :risk-fields="riskFields"
    :risk-ids="riskIds"
    @success="handleSuccess" />
</template>

<script setup lang="ts">
  import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskManageService from '@service/risk-manage';

  import useRequest from '@hooks/use-request';

  import { fetchBatchPreview } from '../adapter';
  import {
    BATCH_SYNC_LIMIT,
    type BatchAvailability,
    type BatchRiskRow,
    createDisabledAvailability,
    hasBatchProcessPermission,
    REASON_LIMIT,
    REASON_NONE,
    REASON_UNLOADED,
    REASON_UNSUPPORTED,
    toBatchAvailability,
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
    resolveSelectAllRows?: (options?: { maxCount?: number }) => Promise<Array<Record<string, any>>>;
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

  const availability = ref<BatchAvailability>(createDisabledAvailability(REASON_NONE));
  const evaluating = ref(false);
  const opening = ref(false);
  let refreshSeq = 0;
  let refreshTimer: ReturnType<typeof setTimeout> | null = null;

  const rows = computed(() => selectedKeys.value
    .map(id => rowCache.get(id))
    .filter((row): row is BatchRiskRow => Boolean(row)));

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
      if (!eventField) {
        const id = String(item?.id ?? item?.field_name ?? item?.key ?? '');
        return { id, name: String(item?.name ?? item?.display_name ?? item?.description ?? id) };
      }
      // event_fields 的 id 为「显示名:字段名」，仅用于搜索框，变量需取 field_name
      const fieldName = String(item?.field_name ?? '');
      const isBasicField = item?.type === 'basic_event_field';
      const id = fieldName && !isBasicField && !fieldName.startsWith('event_data.')
        ? `event_data.${fieldName}`
        : fieldName;
      return { id, name: String(item?.display_name ?? item?.name ?? fieldName) };
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

  const cacheRow = (row: Record<string, any>) => {
    rowCache.set(String(row.risk_id), {
      risk_id: row.risk_id,
      status: row.status,
      strategy_id: row.strategy_id,
      scene_id: row.scene_id,
      permission: row.permission,
      current_operator: row.current_operator,
    });
  };

  const syncFromList = (list: ListExpose) => {
    const keys = (list.getSelectedKeys?.() || []).map(key => String(key));
    const keySet = new Set(keys);
    (list.getSelection?.() || []).forEach((row) => {
      if (keySet.has(String(row.risk_id))) {
        cacheRow(row);
      }
    });
    Array.from(rowCache.keys()).forEach((id) => {
      if (!keySet.has(id)) {
        rowCache.delete(id);
      }
    });
    selectedKeys.value = keys;
  };

  const loadSelectAllRows = async (list: ListExpose, seq: number) => {
    const allRows = await list.resolveSelectAllRows?.({ maxCount: BATCH_SYNC_LIMIT }) || [];
    if (seq !== refreshSeq) {
      return;
    }
    rowCache.clear();
    allRows.forEach(cacheRow);
    selectedKeys.value = allRows.map(row => String(row.risk_id));
  };

  const evaluate = async (seq: number) => {
    const { count } = props.selectionMeta;
    if (count <= 0) {
      availability.value = createDisabledAvailability(REASON_NONE);
      return;
    }
    if (count > BATCH_SYNC_LIMIT) {
      availability.value = createDisabledAvailability(REASON_LIMIT);
      return;
    }
    const selectedRows = rows.value;
    if (selectedRows.length !== count) {
      availability.value = createDisabledAvailability(REASON_UNLOADED);
      return;
    }
    const preview = await fetchBatchPreview(selectedRows.map(row => String(row.risk_id)));
    if (seq === refreshSeq) {
      availability.value = toBatchAvailability(preview, selectedRows);
    }
  };

  const sync = async () => {
    refreshSeq += 1;
    const seq = refreshSeq;
    const list = props.listRef;
    const { count, isSelectAll } = props.selectionMeta;
    evaluating.value = true;
    try {
      if (!list) {
        selectedKeys.value = [];
      } else if (isSelectAll && count > 0 && count <= BATCH_SYNC_LIMIT) {
        if (rows.value.length !== count) {
          await loadSelectAllRows(list, seq);
        }
      } else {
        syncFromList(list);
      }
      if (seq === refreshSeq) {
        await evaluate(seq);
      }
    } catch {
      if (seq === refreshSeq) {
        availability.value = createDisabledAvailability(REASON_UNSUPPORTED);
      }
    } finally {
      if (seq === refreshSeq) {
        evaluating.value = false;
      }
    }
  };

  const scheduleSync = () => {
    if (refreshTimer) {
      clearTimeout(refreshTimer);
      refreshTimer = null;
    }
    const { count } = props.selectionMeta;
    if (count <= 0 || count > BATCH_SYNC_LIMIT) {
      sync();
      return;
    }
    refreshTimer = setTimeout(() => {
      refreshTimer = null;
      sync();
    }, 300);
  };

  watch(
    () => [props.selectionMeta.count, props.selectionMeta.mode, props.selectionMeta.isSelectAll],
    () => {
      nextTick(scheduleSync);
    },
  );

  onBeforeUnmount(() => {
    if (refreshTimer) {
      clearTimeout(refreshTimer);
    }
  });

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

  const handleOpen = async () => {
    if (opening.value) {
      return;
    }
    if (refreshTimer || evaluating.value) {
      if (refreshTimer) {
        clearTimeout(refreshTimer);
        refreshTimer = null;
      }
      opening.value = true;
      try {
        await sync();
      } finally {
        opening.value = false;
      }
    }
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

  defineExpose({ sync: scheduleSync });
</script>
<style lang="postcss" scoped>
.batch-handle-btn-wrapper {
  display: inline-flex;

  /* 禁用的原生 button 不派发鼠标事件，需透传给外层才能触发 tooltip */
  &.is-batch-disabled {
    cursor: not-allowed;

    :deep(.bk-button) {
      pointer-events: none;
    }
  }
}
</style>
