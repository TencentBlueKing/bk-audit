import { computed, type Ref } from 'vue';
import { useI18n } from 'vue-i18n';

export const RISK_EXPORT_MAX_COUNT = 300;

export interface RiskSelectionMeta {
  mode: '' | 'page' | 'all';
  count: number;
  total: number;
  isSelectAll: boolean;
}

export function useRiskExportLimit(selectionMeta: Ref<RiskSelectionMeta>) {
  const { t } = useI18n();

  const exportCount = computed(() => selectionMeta.value.count);

  const isExportEnabled = computed(() => (
    exportCount.value > 0 && exportCount.value <= RISK_EXPORT_MAX_COUNT
  ));

  const exportTooltip = computed(() => {
    if (exportCount.value <= 0) {
      return { disabled: false, content: t('请至少选择 1 条风险单') };
    }
    if (exportCount.value > RISK_EXPORT_MAX_COUNT) {
      return { disabled: false, content: t('当前最多导出300条数据') };
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
