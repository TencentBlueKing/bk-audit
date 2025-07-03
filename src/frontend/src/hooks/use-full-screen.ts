import screenfull from 'screenfull';
import { onBeforeUnmount, ref } from 'vue';

export default function useFullScreen(
  editorGetter: () => any,
  containerGetter: () => any,
) {
  const showExit = ref(false);

  const handleScreenfullChanage = () => {
    const editor = editorGetter();
    const container = containerGetter();

    if (!editor || !container) return;

    showExit.value = screenfull.isFullscreen;
    editor.layout();
  };

  const handleReize = () => {
    const editor = editorGetter();
    if (editor) {
      editor.layout();
    }
  };

  const handleScreenfull = () => {
    const container = containerGetter();
    if (container) {
      screenfull.toggle(container);
    }
  };

  // 初始化监听
  screenfull.on('change', handleScreenfullChanage);
  window.addEventListener('resize', handleReize);

  // 清理
  onBeforeUnmount(() => {
    screenfull.off('change', handleScreenfullChanage);
    window.removeEventListener('resize', handleReize);
  });

  return {
    showExit,
    handleScreenfull,
  };
}
