import {
  nextTick,
  ref,
} from 'vue';

export const isRiskExportLoading = ref(false);

export function startRiskExportLoading() {
  isRiskExportLoading.value = true;
}

export function stopRiskExportLoading() {
  isRiskExportLoading.value = false;
}

export async function withRiskExportLoading<T>(fn: () => Promise<T>): Promise<T> {
  startRiskExportLoading();
  await nextTick();
  try {
    return await fn();
  } finally {
    stopRiskExportLoading();
  }
}

export default withRiskExportLoading;
