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
import type { Ref } from 'vue';
import { h, resolveComponent, resolveDirective, withDirectives } from 'vue';
import { useI18n } from 'vue-i18n';

import type RiskManageModel from '@model/risk/risk';

import EditTag from '@components/edit-box/tag.vue';
import Tooltips from '@components/show-tooltips-text/index.vue';

import { RISK_STATUS_TAG_MAP } from '@views/risk-manage/constants';
import RiskLevel from '@views/risk-manage/list/components/risk-level.vue';

export interface RiskColumnDeps {
  levelData: Ref<Record<string, any>>;
  strategyTagMap: Ref<Record<string, string>>;
  strategyList: Ref<Array<{ value: number; label: string }>>;
  riskStatusCommon: Ref<Array<{ id: string; name: string }>>;
  handleToDetail: (row: RiskManageModel, needToRiskContent?: boolean) => void;
}

const createTextColumn = (title: string, colKey: string, minWidth = 320) => ({
  title,
  colKey,
  minWidth,
  ellipsis: true,
  cell: (_h: any, { row }: { row: RiskManageModel }) => h(Tooltips, { data: (row as any)[colKey] }),
});

export const createRiskIdColumn = (routeName: string) => {
  const { t } = useI18n();
  return {
    title: t('风险ID'),
    colKey: 'risk_id',
    width: 200,
    minWidth: 180,
    fixed: 'left',
    ellipsis: true,
    cell: (_h: any, { row }: { row: RiskManageModel }) => {
      const RouterLink = resolveComponent('router-link');
      const to = {
        name: routeName,
        params: { riskId: row.risk_id },
      };
      return h(RouterLink as any, { to }, () => [
        h(Tooltips, { data: row.risk_id }),
      ]);
    },
  };
};

export const createBaseRiskColumns = (deps: RiskColumnDeps) => {
  const { t } = useI18n();
  const statusToMap = RISK_STATUS_TAG_MAP;
  const { levelData, strategyTagMap, strategyList, riskStatusCommon, handleToDetail } = deps;

  return [
    // 多选列
    {
      type: 'multiple',
      colKey: 'row-select',
      width: 80,
      fixed: 'left',
    },
    createTextColumn(t('风险标题'), 'title'),
    createTextColumn(t('风险描述'), 'event_content'),
    {
      title: t('风险等级'),
      colKey: 'risk_level',
      width: 120,
      sortType: 'all',
      sorter: true,
      cell: (_h: any, { row }: { row: RiskManageModel }) => h(RiskLevel, {
        levelData: levelData.value,
        data: row,
      }),
    },
    {
      title: t('风险标签'),
      colKey: 'tags',
      width: 120,
      cell: (_h: any, { row }: { row: RiskManageModel }) => {
        const tags = row.tags.map((item: string) => strategyTagMap.value[item] || item);
        return h(EditTag, { data: tags, key: row.strategy_id });
      },
    },
    {
      title: t('责任人'),
      colKey: 'operator',
      width: 160,
      cell: (_h: any, { row }: { row: RiskManageModel }) => h(EditTag, { data: row.operator }),
    },
    {
      title: t('处理状态'),
      colKey: 'status',
      width: 110,
      cell: (_h: any, { row }: { row: RiskManageModel }) => {
        const BkTag = resolveComponent('bk-tag');
        const BkButton = resolveComponent('bk-button');
        const AuditIcon = resolveComponent('audit-icon');
        const config = statusToMap[row.status] || {};
        const name = riskStatusCommon.value.find((i: any) => i.id === row.status)?.name || '--';

        const tagNode = h(BkTag as any, { theme: config.tag }, () => [
          h('p', { style: 'display: flex; align-items: center;' }, [
            h(AuditIcon as any, {
              type: config.icon,
              style: `margin-right: 6px; color: ${config.color || ''}`,
            }),
            h('span', name),
          ]),
        ]);

        if (row.status === 'closed' && row.experiences > 0) {
          const bkTooltips = resolveDirective('bk-tooltips');
          return h('div', { style: 'display: flex; align-items: center; height: 100%;' }, [
            tagNode,
            h(BkButton as any, {
              text: true,
              theme: 'primary',
              onClick: () => handleToDetail(row, true),
            }, () => [
              bkTooltips
                ? withDirectives(
                  h(AuditIcon as any, {
                    type: 'report',
                    style: 'font-size: 14px;',
                  }),
                  [[bkTooltips, t('已填写"风险总结"')]],
                )
                : h(AuditIcon as any, {
                  type: 'report',
                  style: 'font-size: 14px;',
                }),
            ]),
          ]);
        }

        return tagNode;
      },
    },
    {
      title: t('当前处理人'),
      colKey: 'current_operator',
      width: 200,
      cell: (_h: any, { row }: { row: RiskManageModel }) => h(EditTag, { data: row.current_operator }),
    },
    {
      title: t('关注人'),
      colKey: 'notice_users',
      width: 200,
      cell: (_h: any, { row }: { row: RiskManageModel }) => h(EditTag, { data: row.notice_users }),
    },
    {
      title: t('风险命中策略(ID)'),
      colKey: 'strategy_id',
      width: 200,
      ellipsis: true,
      cell: (_h: any, { row }: { row: RiskManageModel }) => {
        const RouterLink = resolveComponent('router-link');
        const to = {
          name: 'strategyList',
          query: { strategy_id: row.strategy_id, scope_id: row.scene_id, scope_type: 'scene' },
        };
        const strategyName = strategyList.value
          .find((item: any) => item.value === row.strategy_id)?.label;
        return strategyName
          ? h(RouterLink as any, { to, target: '_blank' }, () => [
            h('span', `${strategyName}(${row.strategy_id})`),
          ])
          : h('span', '--');
      },
    },
    {
      title: t('首次发现时间'),
      colKey: 'event_time',
      width: 168,
      minWidth: 168,
      sortType: 'all',
      sorter: true,
    },
    {
      title: t('最后一次处理时间'),
      colKey: 'last_operate_time',
      width: 160,
      sorter: true,
      cell: (_h: any, { row }: { row: RiskManageModel }) => row.last_operate_time || '--',
    },
    {
      title: t('事件调查报告'),
      colKey: 'has_report',
      width: 160,
      filter: {
        type: 'single',
        showConfirmAndReset: true,
        resetValue: undefined,
        list: [
          { label: t('已生成'), value: true },
          { label: t('未生成'), value: false },
        ],
      },
      cell: (_h: any, { row }: { row: RiskManageModel }) => {
        const BkTag = resolveComponent('bk-tag');
        return h(BkTag as any, null, () => [
          row.has_report ? t('已生成') : t('未生成'),
        ]);
      },
    },
    {
      title: t('风险标记'),
      colKey: 'risk_label',
      width: 110,
      cell: (_h: any, { row }: { row: RiskManageModel }) => h('span', {
        class: {
          misreport: row.risk_label === 'misreport',
          'risk-label-status': true,
        },
      }, row.risk_label === 'normal' ? t('正常') : t('误报')),
    },
  ];
};
