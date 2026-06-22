import {
  type ComputedRef,
  nextTick,
  type Ref,
  ref,
} from 'vue';
import { useI18n } from 'vue-i18n';

import useMessage from '@hooks/use-message';

interface ListRefExpose {
  resolveExportSelection?: () => Promise<{ keys: Array<string | number> }>;
}

interface SearchBoxRefExpose {
  exportData?: (val: string[], type: string) => Promise<unknown>;
}

export function createRiskExportRequest(options: {
  listRef: Ref<ListRefExpose | undefined>;
  searchBoxRef: Ref<SearchBoxRefExpose | undefined>;
  riskViewType: string;
}) {
  const { t } = useI18n();
  const { messageWarn } = useMessage();

  return async () => {
    const { keys } = await options.listRef.value?.resolveExportSelection?.() || { keys: [] };
    const selectedData = keys.map((id: string | number) => id.toString());
    if (!selectedData.length) {
      messageWarn(t('请选择要操作的数据'));
      return;
    }
    await options.searchBoxRef.value?.exportData?.(selectedData, options.riskViewType);
  };
}

export function useRiskBatchExport(options: {
  listRef: Ref<ListRefExpose | undefined>;
  searchBoxRef: Ref<SearchBoxRefExpose | undefined>;
  riskViewType: string;
  isExportEnabled: ComputedRef<boolean>;
}) {
  const isExportLoading = ref(false);
  const runExport = createRiskExportRequest(options);

  const handleExport = async () => {
    if (!options.isExportEnabled.value || isExportLoading.value) {
      return;
    }
    isExportLoading.value = true;
    await nextTick();
    try {
      await runExport();
    } finally {
      isExportLoading.value = false;
    }
  };

  return {
    isExportLoading,
    handleExport,
    runExport,
  };
}

export default useRiskBatchExport;
