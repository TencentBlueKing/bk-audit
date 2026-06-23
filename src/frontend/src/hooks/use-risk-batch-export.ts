import {
  type ComputedRef,
  type Ref,
} from 'vue';
import { useI18n } from 'vue-i18n';

import { showAsyncExportNotifyIfNeeded } from '@hooks/use-async-export-notify';
import useMessage from '@hooks/use-message';
import {
  RISK_EXPORT_MAX_COUNT,
  type RiskSelectionMeta,
} from '@hooks/use-risk-export-limit';
import { isRiskExportLoading } from '@hooks/use-risk-export-loading';

interface ListRefExpose {
  resolveExportSelection?: () => Promise<{ keys: Array<string | number> }>;
}

export interface RiskExportDataOptions {
  async?: boolean;
  showSuccessMessage?: boolean;
}

interface SearchBoxRefExpose {
  exportData?: (val: string[], type: string, options?: RiskExportDataOptions) => Promise<unknown>;
}

export function createRiskExportRequest(options: {
  listRef: Ref<ListRefExpose | undefined>;
  searchBoxRef: Ref<SearchBoxRefExpose | undefined>;
  riskViewType: string;
  selectionMeta: Ref<RiskSelectionMeta>;
}) {
  const { t } = useI18n();
  const { messageWarn } = useMessage();

  return async () => {
    const exportCount = options.selectionMeta.value.count;
    if (!exportCount) {
      messageWarn(t('请选择要操作的数据'));
      return;
    }

    const isAsyncExport = exportCount > RISK_EXPORT_MAX_COUNT;
    if (isAsyncExport) {
      const shouldProceed = await showAsyncExportNotifyIfNeeded();
      if (!shouldProceed) {
        return;
      }
    }

    const { keys } = await options.listRef.value?.resolveExportSelection?.() || { keys: [] };
    const selectedData = keys.map((id: string | number) => id.toString());
    if (!selectedData.length) {
      messageWarn(t('请选择要操作的数据'));
      return;
    }

    if (isAsyncExport) {
      await options.searchBoxRef.value?.exportData?.(selectedData, options.riskViewType, {
        async: true,
      });
      return;
    }

    await options.searchBoxRef.value?.exportData?.(selectedData, options.riskViewType);
  };
}

export function useRiskBatchExport(options: {
  listRef: Ref<ListRefExpose | undefined>;
  searchBoxRef: Ref<SearchBoxRefExpose | undefined>;
  riskViewType: string;
  selectionMeta: Ref<RiskSelectionMeta>;
  isExportEnabled: ComputedRef<boolean>;
}) {
  const runExport = createRiskExportRequest(options);

  const handleExport = async () => {
    if (!options.isExportEnabled.value) {
      return;
    }
    await runExport();
  };

  return {
    isExportLoading: isRiskExportLoading,
    handleExport,
    runExport,
  };
}

export default useRiskBatchExport;
