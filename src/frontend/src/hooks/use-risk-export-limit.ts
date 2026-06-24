import { computed, type Ref } from 'vue';
import { useI18n } from 'vue-i18n';

/** 超过该条数时走异步导出 */
export const RISK_EXPORT_ASYNC_THRESHOLD = 300;
/** 导出上限，超出后禁止导出 */
export const RISK_EXPORT_MAX_COUNT = 10000;

export interface RiskSelectionMeta {
  mode: '' | 'page' | 'all';
  count: number;
  total: number;
  isSelectAll: boolean;
}

export function useRiskExportLimit(selectionMeta: Ref<RiskSelectionMeta>) {
  const { t } = useI18n();

  const exportCount = computed(() => selectionMeta.value.count);

  const isExportEnabled = computed(() => exportCount.value > 0);

  const exportTooltip = computed(() => {
    if (exportCount.value <= 0) {
      return { disabled: false, content: t('请至少选择 1 条风险单') };
    }
    return { disabled: true, content: '' };
  });

  const exportDisabledTooltip = computed(() => (
    exportTooltip.value.disabled ? '' : exportTooltip.value.content
  ));

  return {
    exportCount,
    isExportEnabled,
    exportTooltip,
    exportDisabledTooltip,
  };
}

export default useRiskExportLimit;
