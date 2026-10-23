import { defineComponent, h } from 'vue';

/** 失败原因提示：正文单独滚动，避免把气泡箭头裁掉。 */
export const executionErrorTip = (
  content: string,
  extra: { placement?: 'top' | 'bottom'; disabled?: boolean } = {},
) => ({
  content: defineComponent({
    setup() {
      return () => h('div', { class: 'execution-error-tip-body' }, content);
    },
  }),
  placement: extra.placement || 'top',
  disabled: extra.disabled,
  delay: 80,
  extCls: 'execution-attempt-tip',
});
