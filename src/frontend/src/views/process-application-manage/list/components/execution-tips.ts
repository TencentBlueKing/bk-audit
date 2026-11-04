import { defineComponent, h } from 'vue';

/** 长文本提示：正文单独滚动，避免把气泡箭头裁掉。 */
export const executionErrorTip = (
  content: string,
  extra: {
    placement?: 'top' | 'bottom' | 'bottom-start';
    disabled?: boolean;
    extCls?: string;
  } = {},
) => ({
  content: defineComponent({
    setup() {
      return () => h('div', { class: 'execution-error-tip-body' }, content);
    },
  }),
  placement: extra.placement || 'top',
  disabled: extra.disabled,
  delay: 80,
  extCls: extra.extCls || 'execution-attempt-tip',
});
