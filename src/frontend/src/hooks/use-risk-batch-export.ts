import {
  type ComputedRef,
  type Ref,
} from 'vue';
import { useI18n } from 'vue-i18n';

import { showAsyncExportNotifyIfNeeded } from '@hooks/use-async-export-notify';
import useMessage from '@hooks/use-message';
import {
  RISK_EXPORT_ASYNC_THRESHOLD,
  RISK_EXPORT_MAX_COUNT,
  type RiskSelectionMeta,
} from '@hooks/use-risk-export-limit';
import { isRiskExportLoading } from '@hooks/use-risk-export-loading';
import type {
  RiskExportDataOptions,
  RiskExportFilters,
  RiskViewType,
} from '@hooks/use-risk-export-types';

interface ListRefExpose {
  resolveExportSelection?: () => Promise<{ keys: Array<string | number> }>;
  getExportFilters?: () => RiskExportFilters;
}

interface SearchBoxRefExpose {
  exportData?: (
    val: string[],
    type: string,
    options?: RiskExportDataOptions,
  ) => Promise<unknown>;
}

export type { RiskExportDataOptions };

export function createRiskExportRequest(options: {
  listRef: Ref<ListRefExpose | undefined>;
  searchBoxRef: Ref<SearchBoxRefExpose | undefined>;
  riskViewType: RiskViewType | string;
  selectionMeta: Ref<RiskSelectionMeta>;
}) {
  const { t } = useI18n();
  const { messageWarn } = useMessage();

  const warnExportOverLimit = () => {
    messageWarn(t('导出数据量超过10000条，请缩小筛选范围后重试'));
  };

  return async () => {
    const meta = options.selectionMeta.value;
    const exportCount = meta.count;
    if (!exportCount) {
      messageWarn(t('请选择要操作的数据'));
      return;
    }

    const limitCount = meta.isSelectAll ? meta.total : exportCount;
    if (limitCount > RISK_EXPORT_MAX_COUNT) {
      warnExportOverLimit();
      return;
    }

    const needAsyncExport = limitCount > RISK_EXPORT_ASYNC_THRESHOLD;

    // 跨页全选且超过 300 条：传 filters，异步导出
    if (meta.isSelectAll && needAsyncExport) {
      const shouldProceed = await showAsyncExportNotifyIfNeeded();
      if (!shouldProceed) {
        return;
      }

      const filters = options.listRef.value?.getExportFilters?.() || {};
      await options.searchBoxRef.value?.exportData?.([], options.riskViewType, {
        async: true,
        filters,
      });
      return;
    }

    // 本页/勾选（含跨页全选 ≤300 条）：传 risk_ids
    const { keys } = await options.listRef.value?.resolveExportSelection?.() || { keys: [] };
    const selectedData = keys.map((id: string | number) => id.toString());
    if (!selectedData.length) {
      messageWarn(t('请选择要操作的数据'));
      return;
    }

    if (needAsyncExport) {
      const shouldProceed = await showAsyncExportNotifyIfNeeded();
      if (!shouldProceed) {
        return;
      }

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
  riskViewType: RiskViewType | string;
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
