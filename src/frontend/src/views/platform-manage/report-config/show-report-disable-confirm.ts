/*
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
  Copyright (C) 2023 THL A29 Limited,
  a Tencent company. All rights reserved.
  Licensed under the MIT License (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at http://opensource.org/licenses/MIT
  Unless required by applicable law or agreed to in writing,
  software distributed under the License is distributed on
  an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
  either express or implied. See the License for the
  specific language governing permissions and limitations under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
*/
import { InfoBox } from 'bkui-vue';
import { h } from 'vue';
import type { ComposerTranslation } from 'vue-i18n';

interface ShowReportDisableConfirmOptions {
  /** 报表名称 */
  name: string;
  t: ComposerTranslation;
  onConfirm: () => void | Promise<void>;
  /**
   * 是否抬高层级以盖过侧滑（z-index: 9999）。
   * InfoBox 未透传 zIndex，通过 class + CSS 处理。
   */
  aboveSideslider?: boolean;
}

/** 平台报表停用确认弹窗（列表与编辑侧滑共用） */
export function showReportDisableConfirm(options: ShowReportDisableConfirmOptions) {
  const { name, t, onConfirm, aboveSideslider = false } = options;

  return InfoBox({
    class: aboveSideslider ? 'report-disable-infobox-above-sideslider' : undefined,
    title: t('确定停用该报表？'),
    subTitle: () => h('div', { style: { textAlign: 'left' } }, [
      h('div', {
        style: {
          marginBottom: '12px',
          fontSize: '14px',
          color: '#313238',
        },
      }, `${t('报表：')}${name}`),
      h('div', {
        style: {
          padding: '12px 16px',
          fontSize: '14px',
          color: '#63656e',
          textAlign: 'center',
          backgroundColor: '#f5f7fa',
          borderRadius: '2px',
        },
      }, t('停用后，可见范围内的空间将无法查看和使用该报表，请谨慎操作！')),
    ]),
    confirmText: t('停用'),
    cancelText: t('取消'),
    headerAlign: 'center',
    contentAlign: 'center',
    footerAlign: 'center',
    confirmButtonTheme: 'danger',
    onConfirm,
  });
}
