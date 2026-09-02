import { computed, inject, type Ref, ref } from 'vue';
import { useRoute } from 'vue-router';

import {
  isDraftStrategyStatus,
  isStrategyCloneRoute,
  isStrategyEditRoute,
  isStrategyUpgradeRoute,
} from '../../utils/strategy-routes';

export const STRATEGY_DRAFT_EDIT_KEY = Symbol('strategyDraftEdit');

export function useStrategyConfigLock(strategyStatus?: Ref<string | undefined>) {
  const route = useRoute();
  const isEditMode = isStrategyEditRoute(route.name);
  const isCloneMode = isStrategyCloneRoute(route.name);
  const isUpgradeMode = isStrategyUpgradeRoute(route.name);
  const injectedDraftEdit = inject<Ref<boolean>>(STRATEGY_DRAFT_EDIT_KEY, ref(false));
  const isDraftStrategyEdit = computed(() => {
    if (strategyStatus?.value !== undefined) {
      return isEditMode && isDraftStrategyStatus(strategyStatus.value);
    }
    return injectedDraftEdit.value;
  });
  const isStrategyConfigLocked = computed(() => (
    (isEditMode || isCloneMode) && !isDraftStrategyEdit.value
  ));

  return {
    isEditMode,
    isCloneMode,
    isUpgradeMode,
    isDraftStrategyEdit,
    isStrategyConfigLocked,
  };
}
