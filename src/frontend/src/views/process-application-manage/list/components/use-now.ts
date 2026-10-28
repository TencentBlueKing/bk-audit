import {
  onUnmounted,
  ref,
  watch,
  type WatchSource,
} from 'vue';

/** 条件成立时每秒刷新一次当前时间，用于执行中耗时。 */
export const useNow = (active: WatchSource<boolean>) => {
  const now = ref(Date.now());
  let timer: number | undefined;

  const stop = () => {
    if (timer == null) return;
    window.clearInterval(timer);
    timer = undefined;
  };

  watch(active, (on) => {
    if (!on) {
      stop();
      return;
    }
    now.value = Date.now();
    if (timer != null) return;
    timer = window.setInterval(() => {
      now.value = Date.now();
    }, 1000);
  }, { immediate: true });

  onUnmounted(stop);
  return now;
};
