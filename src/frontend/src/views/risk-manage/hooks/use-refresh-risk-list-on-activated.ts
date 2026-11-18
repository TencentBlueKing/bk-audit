/*
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
*/
import { onActivated, ref } from 'vue';

interface RiskListExpose {
  refreshList?: () => void;
  fetchData?: (...args: any[]) => void;
}

/**
 * 风险列表 keep-alive 后，从详情返回时刷新当前页数据，
 * 让列表状态与详情中的工单处理状态保持一致。
 */
export const useRefreshRiskListOnActivated = (getListRef: () => RiskListExpose | null | undefined) => {
  const hasActivatedOnce = ref(false);

  onActivated(() => {
    if (!hasActivatedOnce.value) {
      hasActivatedOnce.value = true;
      return;
    }
    const list = getListRef();
    if (list?.refreshList) {
      list.refreshList();
      return;
    }
    list?.fetchData?.();
  });
};
