import { InfoBox } from 'bkui-vue';

import i18n from '@/language';

export const ASYNC_EXPORT_NOTIFY_STORAGE_KEY = 'audit-risk-async-export-notify-dismissed';

export function isAsyncExportNotifyDismissed() {
  return sessionStorage.getItem(ASYNC_EXPORT_NOTIFY_STORAGE_KEY) === '1';
}

export function markAsyncExportNotifyDismissed() {
  sessionStorage.setItem(ASYNC_EXPORT_NOTIFY_STORAGE_KEY, '1');
}

export function showAsyncExportNotifyIfNeeded(): Promise<boolean> {
  if (isAsyncExportNotifyDismissed()) {
    return Promise.resolve(true);
  }

  const { t } = i18n.global;

  return new Promise((resolve) => {
    InfoBox({
      type: 'info',
      title: t('变更为异步导出通知'),
      content: t('当前导出数据量超出300条，需采用异步导出，导出成功后将发送邮件通知'),
      confirmText: t('我知道了'),
      headerAlign: 'center',
      contentAlign: 'center',
      footerAlign: 'center',
      onConfirm() {
        markAsyncExportNotifyDismissed();
        resolve(true);
      },
      onClose() {
        resolve(false);
      },
    });
  });
}

export default showAsyncExportNotifyIfNeeded;
