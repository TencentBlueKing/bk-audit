<!--
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
-->
<template>
  <div class="preview">
    <div class="base-info">
      <div class="info-title">
        风险单标题文本占位
      </div>
      <div>
        <base-info-form
          :data="eventData"
          :risk-status-common="riskStatusCommon"
          :show-field-names="priorityFieldNames"
          :strategy-list="strategyList" />
        <base-info-form
          v-if="isShowMore"
          :data="eventData"
          :risk-status-common="riskStatusCommon"
          :show-field-names="normalFieldNames"
          :strategy-list="strategyList" />
      </div>
      <div class="show-more-condition-btn">
        <bk-button
          class="show-more-btn"
          text
          @click="() => isShowMore = !isShowMore">
          <audit-icon
            :class="{ active: isShowMore }"
            style=" margin-right: 5px;"
            type="angle-double-down" />
          {{ isShowMore ? t('收起字段') : t('展开更多字段') }}
        </bk-button>
      </div>
    </div>

    <div class="event-info">
      <div class="event-title">
        {{ t('关联事件') }}
        <span class="event-count">1000</span>
      </div>
      <div class="event-list">
        <div class="event-list-left">
          <div
            v-for="event in evevtList"
            :key="event.risk_id"
            :class=" activeEventId === event.risk_id ? `active-event event-time` : `event-time`"

            @click="() => activeEventId = event.risk_id">
            {{ event.event_end_time }}
          </div>
        </div>
        <div class="event-list-right">
          <div class="right-info">
            <div class="right-info-title">
              {{ t('基本信息') }}
            </div>
            <div class="right-info-item">
              <span class="info-item">
                <span
                  v-bk-tooltips="t('事件ID')"
                  class="dashed-underline">{{ t('事件ID') }}</span>: {{ t('事件ID') }}
              </span>
              <span class="info-item">
                <span>{{ t('事件ID') }}</span>: {{ t('事件ID') }}
              </span>
              <span class="info-item">
                <span>{{ t('事件ID') }}</span>: {{ t('事件ID') }}
              </span>
            </div>
          </div>
          <div class="right-info">
            <div class="right-info-title">
              {{ t('事件数据') }}
            </div>
            <div class="right-info-item">
              <span class="info-item">
                <span
                  v-bk-tooltips="t('事件ID')"
                  class="dashed-underline">{{ t('事件ID') }}</span>: {{ t('事件ID') }}
              </span>
              <span class="info-item">
                <span>{{ t('事件ID') }}</span>: {{ t('事件ID') }}
              </span>
              <span class="info-item">
                <span>{{ t('事件ID') }}</span>: {{ t('事件ID') }}
              </span>
            </div>
          </div>
          <div class="right-info">
            <div class="right-info-title">
              {{ t('事件证据 (12)') }}
            </div>
            <div class="events-evidence">
              <div
                v-for="evidence in 20"
                :key="evidence"
                class="evidence-item">
                <div class="evidence-title">
                  <span
                    v-bk-tooltips="t('事件ID')"
                    class="dashed-underline">{{ t('事件ID') }}</span>
                </div>
                <div class="evidence-value">
                  vaaaa
                </div>
                <div class="evidence-value">
                  vaaaa
                </div>
                <div class="evidence-value">
                  vaaaa
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RiskManageService from '@service/risk-manage';
  import StrategyManageService from '@service/strategy-manage';

  import useRequest from '@hooks/use-request';

  import BaseInfoForm from '../../../risk-manage/detail/components/base-info-form.vue';

  const { t } = useI18n();
  const isShowMore = ref(false);
  const activeEventId = ref('20251018111406168314');
  const eventData = ref({
    risk_id: '20251018111406168314',
    strategy_id: 89,
    tags: [],
    event_end_time: '2025-10-17 22:00:00',
    created_at: '2025-10-18 11:14:06',
    created_by: 'admin',
    updated_at: '2025-10-18 12:00:32',
    updated_by: 'admin',
    event_content: 'kellin 已离职，河图系统 中还有权限未清理，需要尽快清理',
    raw_event_id: 'kellin|QUIT|dg-hetu',
    event_evidence: '[{"combined_id": "kellin", "strategy_id": 89, "timestamp": 1760709600000, "resource_type_id": "dg-hetu_acl", "origin_data": "{\\"utctime\\": \\"2025-10-12 16:01:34\\", \\"system_id\\": \\"dg-hetu\\", \\"resource_type_id\\": \\"dg-hetu_acl\\", \\"id\\": \\"kellin\\", \\"display_name\\": \\"kellin\\\\u5728 dg-hetu \\\\u6709\\\\u6743\\\\u9650\\", \\"creator\\": \\"farmlan\\", \\"created_at\\": \\"1702383845000\\", \\"updater\\": \\"farmlan\\", \\"updated_at\\": \\"1702383845000\\", \\"operator\\": \\"kellin\\", \\"bk_bak_operator\\": \\"\\", \\"is_deleted\\": \\"false\\"}", "__id__": "X19ncm91cF9pZF9f:Y21WemRXeDBYM1JoWW14bFgybGs6TlRBd01EUTBPRjl6YzE5bGJuUnllVjh4TURRMU9GOXBibkIxZEE9PQ==,dGltZXN0YW1w:MTc2MDcwOTYwMDAwMA==", "operator": "kellin", "__index__": "4936558241527332768_343", "system_id": "dg-hetu", "__group_id__": "cmVzdWx0X3RhYmxlX2lk:NTAwMDQ0OF9zc19lbnRyeV8xMDQ1OF9pbnB1dA=="}]',
    event_type: [
      'QUIT',
    ],
    event_data: {
      cnt: 1,
      enabled: 'false',
      operator: 'kellin',
      uniq_cnt: 1,
      move_date: '',
      system_id: 'dg-hetu',
      audit_type: 'privilege',
      event_name: 'QUIT',
      move_type_id: 0,
      staff_status: '2',
      after_leader_username: '-',
      before_leader_username: 'minayin',
      after_department_full_name: '-',
      before_department_full_name: '腾讯公司/TEG技术工程事业群/机器学习平台部/产品中心/数据产品组',
    },
    event_time: '2025-10-17 22:00:00',
    event_source: 'dg-hetu',
    operator: [
      'kellin',
    ],
    status: 'closed',
    rule_id: 38,
    rule_version: 2,
    origin_operator: [],
    current_operator: [],
    notice_users: [
      'sheenhu',
      'barondeng',
    ],
    risk_label: 'normal',
    last_operate_time: '2025-10-18 12:00:32',
    title: 'kellin 已离职，河图系统 中还有权限未清理，需要尽快清理',
    permission: {
      edit_risk_v2: true,
    },
    ticket_history: [],
    risk_level: 'HIGH',
    risk_hazard: null,
    risk_guidance: null,
    event_basic_field_configs: [
      {
        field_name: 'raw_event_id',
        display_name: '原始事件ID',
        is_priority: false,
        description: '系统会将原始事件ID相同的事件，关联至同一个未关闭的风险单据',
        enum_mappings: null,
        drill_config: [],
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'operator',
        display_name: '负责人',
        is_priority: false,
        description: '',
        enum_mappings: null,
        drill_config: [],
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'event_time',
        display_name: '事件发生时间',
        is_priority: false,
        description: '',
        enum_mappings: null,
        drill_config: [],
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'event_source',
        display_name: '事件来源',
        is_priority: false,
        description: '',
        enum_mappings: null,
        drill_config: [],
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'strategy_id',
        display_name: '命中策略(ID)',
        is_priority: false,
        description: '',
        enum_mappings: null,
        drill_config: [],
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'event_content',
        display_name: '事件描述',
        is_priority: false,
        description: '',
        enum_mappings: null,
        drill_config: [],
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'event_type',
        display_name: '事件类型',
        is_priority: false,
        description: '',
        enum_mappings: null,
        drill_config: [],
        is_show: true,
        duplicate_field: false,
      },
    ],
    event_data_field_configs: [
      {
        field_name: 'cnt',
        display_name: 'cnt',
        is_priority: false,
        description: '',
        enum_mappings: null,
        drill_config: [],
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'enabled',
        display_name: 'enabled',
        is_priority: false,
        description: '',
        enum_mappings: null,
        drill_config: [],
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'operator',
        display_name: 'operator',
        is_priority: false,
        description: '',
        enum_mappings: null,
        drill_config: [],
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'uniq_cnt',
        display_name: 'uniq_cnt',
        is_priority: false,
        description: '',
        enum_mappings: null,
        drill_config: [],
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'move_date',
        display_name: 'move_date',
        is_priority: false,
        description: '',
        enum_mappings: null,
        drill_config: [],
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'system_id',
        display_name: 'system_id',
        is_priority: false,
        description: '',
        enum_mappings: null,
        drill_config: [],
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'audit_type',
        display_name: 'audit_type',
        is_priority: false,
        description: '',
        enum_mappings: null,
        drill_config: [],
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'event_name',
        display_name: 'event_name',
        is_priority: false,
        description: '',
        enum_mappings: null,
        drill_config: [],
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'move_type_id',
        display_name: 'move_type_id',
        is_priority: false,
        description: '',
        enum_mappings: null,
        drill_config: [],
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'staff_status',
        display_name: 'staff_status',
        is_priority: false,
        description: '',
        enum_mappings: null,
        drill_config: [],
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'leader_username',
        display_name: 'leader_username',
        is_priority: false,
        description: '',
        enum_mappings: null,
        drill_config: [],
        is_show: true,
        duplicate_field: false,
      },
    ],
    event_evidence_field_configs: [],
    risk_meta_field_config: [
      {
        field_name: 'risk_id',
        display_name: '风险ID',
        is_priority: true,
        description: '',
        enum_mappings: {
          related_type: 'strategy',
          related_object_id: 'strategy_id',
          collection_id: 'auto-generate',
          mappings: [],
        },
        drill_config: null,
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'risk_level',
        display_name: '风险等级',
        is_priority: true,
        description: '',
        enum_mappings: {
          related_type: 'strategy',
          related_object_id: 'strategy_id',
          collection_id: 'auto-generate',
          mappings: [],
        },
        drill_config: null,
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'event_type',
        display_name: '风险类型',
        is_priority: false,
        description: '',
        enum_mappings: {
          related_type: 'strategy',
          related_object_id: 'strategy_id',
          collection_id: 'auto-generate',
          mappings: [],
        },
        drill_config: null,
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'risk_tags',
        display_name: '风险标签',
        is_priority: true,
        description: '',
        enum_mappings: {
          related_type: 'strategy',
          related_object_id: 'strategy_id',
          collection_id: 'auto-generate',
          mappings: [],
        },
        drill_config: null,
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'strategy_name',
        display_name: '风险命中策略',
        is_priority: false,
        description: '',
        enum_mappings: {
          related_type: 'strategy',
          related_object_id: 'strategy_id',
          collection_id: 'auto-generate',
          mappings: [],
        },
        drill_config: null,
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'event_content',
        display_name: '风险描述',
        is_priority: false,
        description: '',
        enum_mappings: {
          related_type: 'strategy',
          related_object_id: 'strategy_id',
          collection_id: 'auto-generate',
          mappings: [],
        },
        drill_config: null,
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'risk_hazard',
        display_name: '风险危害',
        is_priority: true,
        description: '',
        enum_mappings: {
          related_type: 'strategy',
          related_object_id: 'strategy_id',
          collection_id: 'auto-generate',
          mappings: [],
        },
        drill_config: null,
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'risk_guidance',
        display_name: '处理指引',
        is_priority: true,
        description: '',
        enum_mappings: {
          related_type: 'strategy',
          related_object_id: 'strategy_id',
          collection_id: 'auto-generate',
          mappings: [],
        },
        drill_config: null,
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'status',
        display_name: '处理状态',
        is_priority: true,
        description: '',
        enum_mappings: {
          related_type: 'strategy',
          related_object_id: 'strategy_id',
          collection_id: 'auto-generate',
          mappings: [],
        },
        drill_config: null,
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'operator',
        display_name: '责任人',
        is_priority: false,
        description: '',
        enum_mappings: {
          related_type: 'strategy',
          related_object_id: 'strategy_id',
          collection_id: 'auto-generate',
          mappings: [],
        },
        drill_config: null,
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'current_operator',
        display_name: '当前处理人',
        is_priority: true,
        description: '',
        enum_mappings: {
          related_type: 'strategy',
          related_object_id: 'strategy_id',
          collection_id: 'auto-generate',
          mappings: [],
        },
        drill_config: null,
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'notice_users',
        display_name: '关注人',
        is_priority: false,
        description: '',
        enum_mappings: {
          related_type: 'strategy',
          related_object_id: 'strategy_id',
          collection_id: 'auto-generate',
          mappings: [],
        },
        drill_config: null,
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'event_time',
        display_name: '首次发现时间',
        is_priority: false,
        description: '',
        enum_mappings: {
          related_type: 'strategy',
          related_object_id: 'strategy_id',
          collection_id: 'auto-generate',
          mappings: [],
        },
        drill_config: null,
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'event_end_time',
        display_name: '最后发现时间',
        is_priority: false,
        description: '',
        enum_mappings: {
          related_type: 'strategy',
          related_object_id: 'strategy_id',
          collection_id: 'auto-generate',
          mappings: [],
        },
        drill_config: null,
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'last_operate_time',
        display_name: '最后一次处理时间',
        is_priority: false,
        description: '',
        enum_mappings: {
          related_type: 'strategy',
          related_object_id: 'strategy_id',
          collection_id: 'auto-generate',
          mappings: [],
        },
        drill_config: null,
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'risk_label',
        display_name: '风险标记',
        is_priority: false,
        description: '',
        enum_mappings: {
          related_type: 'strategy',
          related_object_id: 'strategy_id',
          collection_id: 'auto-generate',
          mappings: [],
        },
        drill_config: null,
        is_show: true,
        duplicate_field: false,
      },
      {
        field_name: 'rule_id',
        display_name: '处理规则',
        is_priority: false,
        description: '',
        enum_mappings: {
          related_type: 'strategy',
          related_object_id: 'strategy_id',
          collection_id: 'auto-generate',
          mappings: [],
        },
        drill_config: null,
        is_show: true,
        duplicate_field: false,
      },
    ],
  });
  const evevtList = ref([
    {
      risk_id: '20251018111406168314',
      strategy_id: 89,
      tags: [],
      event_end_time: '2025-10-17 22:00:00',
      created_at: '2025-10-18 11:14:06',
      created_by: 'admin',
      updated_at: '2025-10-18 12:00:32',
      updated_by: 'admin',
      event_content: 'kellin 已离职，河图系统 中还有权限未清理，需要尽快清理',
      raw_event_id: 'kellin|QUIT|dg-hetu',
      event_evidence: '[{"combined_id": "kellin", "strategy_id": 89, "timestamp": 1760709600000, "resource_type_id": "dg-hetu_acl", "origin_data": "{\\"utctime\\": \\"2025-10-12 16:01:34\\", \\"system_id\\": \\"dg-hetu\\", \\"resource_type_id\\": \\"dg-hetu_acl\\", \\"id\\": \\"kellin\\", \\"display_name\\": \\"kellin\\\\u5728 dg-hetu \\\\u6709\\\\u6743\\\\u9650\\", \\"creator\\": \\"farmlan\\", \\"created_at\\": \\"1702383845000\\", \\"updater\\": \\"farmlan\\", \\"updated_at\\": \\"1702383845000\\", \\"operator\\": \\"kellin\\", \\"bk_bak_operator\\": \\"\\", \\"is_deleted\\": \\"false\\"}", "__id__": "X19ncm91cF9pZF9f:Y21WemRXeDBYM1JoWW14bFgybGs6TlRBd01EUTBPRjl6YzE5bGJuUnllVjh4TURRMU9GOXBibkIxZEE9PQ==,dGltZXN0YW1w:MTc2MDcwOTYwMDAwMA==", "operator": "kellin", "__index__": "4936558241527332768_343", "system_id": "dg-hetu", "__group_id__": "cmVzdWx0X3RhYmxlX2lk:NTAwMDQ0OF9zc19lbnRyeV8xMDQ1OF9pbnB1dA=="}]',
      event_type: [
        'QUIT',
      ],
      event_data: {
        cnt: 1,
        enabled: 'false',
        operator: 'kellin',
        uniq_cnt: 1,
        move_date: '',
        system_id: 'dg-hetu',
        audit_type: 'privilege',
        event_name: 'QUIT',
        move_type_id: 0,
        staff_status: '2',
        after_leader_username: '-',
        before_leader_username: 'minayin',
        after_department_full_name: '-',
        before_department_full_name: '腾讯公司/TEG技术工程事业群/机器学习平台部/产品中心/数据产品组',
      },
      event_time: '2025-10-17 22:00:00',
      event_source: 'dg-hetu',
      operator: [
        'kellin',
      ],
      status: 'closed',
      rule_id: 38,
      rule_version: 2,
      origin_operator: [],
      current_operator: [],
      notice_users: [
        'sheenhu',
        'barondeng',
      ],
      risk_label: 'normal',
      last_operate_time: '2025-10-18 12:00:32',
      title: 'kellin 已离职，河图系统 中还有权限未清理，需要尽快清理',
      permission: {
        edit_risk_v2: true,
      },
      ticket_history: [],
      risk_level: 'HIGH',
      risk_hazard: null,
      risk_guidance: null,
      event_basic_field_configs: [
        {
          field_name: 'raw_event_id',
          display_name: '原始事件ID',
          is_priority: false,
          description: '系统会将原始事件ID相同的事件，关联至同一个未关闭的风险单据',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'operator',
          display_name: '负责人',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'event_time',
          display_name: '事件发生时间',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'event_source',
          display_name: '事件来源',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'strategy_id',
          display_name: '命中策略(ID)',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'event_content',
          display_name: '事件描述',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'event_type',
          display_name: '事件类型',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
      ],
      event_data_field_configs: [
        {
          field_name: 'cnt',
          display_name: 'cnt',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'enabled',
          display_name: 'enabled',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'operator',
          display_name: 'operator',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'uniq_cnt',
          display_name: 'uniq_cnt',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'move_date',
          display_name: 'move_date',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'system_id',
          display_name: 'system_id',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'audit_type',
          display_name: 'audit_type',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'event_name',
          display_name: 'event_name',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'move_type_id',
          display_name: 'move_type_id',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'staff_status',
          display_name: 'staff_status',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'leader_username',
          display_name: 'leader_username',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
      ],
      event_evidence_field_configs: [],
      risk_meta_field_config: [
        {
          field_name: 'risk_id',
          display_name: '风险ID',
          is_priority: true,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'risk_level',
          display_name: '风险等级',
          is_priority: true,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'event_type',
          display_name: '风险类型',
          is_priority: false,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'risk_tags',
          display_name: '风险标签',
          is_priority: true,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'strategy_name',
          display_name: '风险命中策略',
          is_priority: false,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'event_content',
          display_name: '风险描述',
          is_priority: false,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'risk_hazard',
          display_name: '风险危害',
          is_priority: true,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'risk_guidance',
          display_name: '处理指引',
          is_priority: true,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'status',
          display_name: '处理状态',
          is_priority: true,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'operator',
          display_name: '责任人',
          is_priority: false,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'current_operator',
          display_name: '当前处理人',
          is_priority: true,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'notice_users',
          display_name: '关注人',
          is_priority: false,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'event_time',
          display_name: '首次发现时间',
          is_priority: false,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'event_end_time',
          display_name: '最后发现时间',
          is_priority: false,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'last_operate_time',
          display_name: '最后一次处理时间',
          is_priority: false,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'risk_label',
          display_name: '风险标记',
          is_priority: false,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'rule_id',
          display_name: '处理规则',
          is_priority: false,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
      ],
    },
    {
      risk_id: '20251018111406168314112',
      strategy_id: 89,
      tags: [],
      event_end_time: '2025-10-17 22:00:00',
      created_at: '2025-10-18 11:14:06',
      created_by: 'admin',
      updated_at: '2025-10-18 12:00:32',
      updated_by: 'admin',
      event_content: 'kellin 已离职，河图系统 中还有权限未清理，需要尽快清理',
      raw_event_id: 'kellin|QUIT|dg-hetu',
      event_evidence: '[{"combined_id": "kellin", "strategy_id": 89, "timestamp": 1760709600000, "resource_type_id": "dg-hetu_acl", "origin_data": "{\\"utctime\\": \\"2025-10-12 16:01:34\\", \\"system_id\\": \\"dg-hetu\\", \\"resource_type_id\\": \\"dg-hetu_acl\\", \\"id\\": \\"kellin\\", \\"display_name\\": \\"kellin\\\\u5728 dg-hetu \\\\u6709\\\\u6743\\\\u9650\\", \\"creator\\": \\"farmlan\\", \\"created_at\\": \\"1702383845000\\", \\"updater\\": \\"farmlan\\", \\"updated_at\\": \\"1702383845000\\", \\"operator\\": \\"kellin\\", \\"bk_bak_operator\\": \\"\\", \\"is_deleted\\": \\"false\\"}", "__id__": "X19ncm91cF9pZF9f:Y21WemRXeDBYM1JoWW14bFgybGs6TlRBd01EUTBPRjl6YzE5bGJuUnllVjh4TURRMU9GOXBibkIxZEE9PQ==,dGltZXN0YW1w:MTc2MDcwOTYwMDAwMA==", "operator": "kellin", "__index__": "4936558241527332768_343", "system_id": "dg-hetu", "__group_id__": "cmVzdWx0X3RhYmxlX2lk:NTAwMDQ0OF9zc19lbnRyeV8xMDQ1OF9pbnB1dA=="}]',
      event_type: [
        'QUIT',
      ],
      event_data: {
        cnt: 1,
        enabled: 'false',
        operator: 'kellin',
        uniq_cnt: 1,
        move_date: '',
        system_id: 'dg-hetu',
        audit_type: 'privilege',
        event_name: 'QUIT',
        move_type_id: 0,
        staff_status: '2',
        after_leader_username: '-',
        before_leader_username: 'minayin',
        after_department_full_name: '-',
        before_department_full_name: '腾讯公司/TEG技术工程事业群/机器学习平台部/产品中心/数据产品组',
      },
      event_time: '2025-10-17 22:00:00',
      event_source: 'dg-hetu',
      operator: [
        'kellin',
      ],
      status: 'closed',
      rule_id: 38,
      rule_version: 2,
      origin_operator: [],
      current_operator: [],
      notice_users: [
        'sheenhu',
        'barondeng',
      ],
      risk_label: 'normal',
      last_operate_time: '2025-10-18 12:00:32',
      title: 'kellin 已离职，河图系统 中还有权限未清理，需要尽快清理',
      permission: {
        edit_risk_v2: true,
      },
      ticket_history: [],
      risk_level: 'HIGH',
      risk_hazard: null,
      risk_guidance: null,
      event_basic_field_configs: [
        {
          field_name: 'raw_event_id',
          display_name: '原始事件ID',
          is_priority: false,
          description: '系统会将原始事件ID相同的事件，关联至同一个未关闭的风险单据',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'operator',
          display_name: '负责人',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'event_time',
          display_name: '事件发生时间',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'event_source',
          display_name: '事件来源',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'strategy_id',
          display_name: '命中策略(ID)',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'event_content',
          display_name: '事件描述',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'event_type',
          display_name: '事件类型',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
      ],
      event_data_field_configs: [
        {
          field_name: 'cnt',
          display_name: 'cnt',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'enabled',
          display_name: 'enabled',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'operator',
          display_name: 'operator',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'uniq_cnt',
          display_name: 'uniq_cnt',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'move_date',
          display_name: 'move_date',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'system_id',
          display_name: 'system_id',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'audit_type',
          display_name: 'audit_type',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'event_name',
          display_name: 'event_name',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'move_type_id',
          display_name: 'move_type_id',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'staff_status',
          display_name: 'staff_status',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'leader_username',
          display_name: 'leader_username',
          is_priority: false,
          description: '',
          enum_mappings: null,
          drill_config: [],
          is_show: true,
          duplicate_field: false,
        },
      ],
      event_evidence_field_configs: [],
      risk_meta_field_config: [
        {
          field_name: 'risk_id',
          display_name: '风险ID',
          is_priority: true,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'risk_level',
          display_name: '风险等级',
          is_priority: true,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'event_type',
          display_name: '风险类型',
          is_priority: false,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'risk_tags',
          display_name: '风险标签',
          is_priority: true,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'strategy_name',
          display_name: '风险命中策略',
          is_priority: false,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'event_content',
          display_name: '风险描述',
          is_priority: false,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'risk_hazard',
          display_name: '风险危害',
          is_priority: true,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'risk_guidance',
          display_name: '处理指引',
          is_priority: true,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'status',
          display_name: '处理状态',
          is_priority: true,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'operator',
          display_name: '责任人',
          is_priority: false,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'current_operator',
          display_name: '当前处理人',
          is_priority: true,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'notice_users',
          display_name: '关注人',
          is_priority: false,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'event_time',
          display_name: '首次发现时间',
          is_priority: false,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'event_end_time',
          display_name: '最后发现时间',
          is_priority: false,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'last_operate_time',
          display_name: '最后一次处理时间',
          is_priority: false,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'risk_label',
          display_name: '风险标记',
          is_priority: false,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
        {
          field_name: 'rule_id',
          display_name: '处理规则',
          is_priority: false,
          description: '',
          enum_mappings: {
            related_type: 'strategy',
            related_object_id: 'strategy_id',
            collection_id: 'auto-generate',
            mappings: [],
          },
          drill_config: null,
          is_show: true,
          duplicate_field: false,
        },
      ],
    },
  ]);
  const {
    data: strategyList,
  } = useRequest(StrategyManageService.fetchAllStrategyList, {
    manual: true,
    defaultValue: [],
  });
  const {
    data: riskStatusCommon,
  } = useRequest(RiskManageService.fetchRiskStatusCommon, {
    manual: true,
    defaultValue: [],
  });

  // 重点展示字段的 field_name 数组
  const priorityFieldNames = computed(() => eventData.value.risk_meta_field_config
    .filter(item => item.is_priority));

  console.log('priorityFieldNames', priorityFieldNames.value);

  // 非重点展示字段的 field_name 数组
  const normalFieldNames = computed(() => eventData.value.risk_meta_field_config
    .filter(item => !item.is_priority));
//   const color = ref('red');
//   const borderStyle = computed(() => ({
//     'border-top': `6px solid ${color.value}`,
//   }));
</script>

<style lang="postcss" scoped>
.preview {
  .base-info {
    position: relative;
    width: 96%;
    margin-top: 20px;
    margin-left: 2%;
    background: #fff;
    border-top: 6px solid red;
    border-radius: 2px;
    box-shadow: 0 2px 4px 0 #1919290d;

    .info-title {
      margin-top: 5px;
      margin-left: 16px;
      font-size: 14px;
      font-weight: 700;
      line-height: 22px;
      letter-spacing: 0;
      color: #313238;
    }

    .show-more-condition-btn {
      position: absolute;
      right: calc(50% - 52px);
      bottom: -10px;
      box-shadow: 0 2px 4px 0 #1919290d;

      .show-more-btn {
        width: 120px;
        height: 22px;
        color: #fff;
        background: #c4c6cc;
        ;
        border-radius: 12px;

        &:hover {
          background-color: #3a84ff;
        }
      }

      .active {
        transform: rotateZ(-180deg);
        transition: all .15s;
      }
    }
  }

  .event-info {
    position: relative;
    width: 96%;
    margin-top: 20px;
    margin-left: 2%;
    background: #fff;
    border-radius: 2px;
    box-shadow: 0 2px 4px 0 #1919290d;

    .event-title {
      padding-top: 10px;
      padding-bottom: 10px;
      margin-left: 16px;
      font-size: 14px;
      font-weight: 700;
      line-height: 22px;
      letter-spacing: 0;
      color: #313238;

      .event-count {
        display: inline-block;
        height: 16px;
        padding-right: 3px;
        padding-left: 3px;
        font-size: 12px;
        line-height: 16px;
        letter-spacing: 0;
        color: #979ba5;
        text-align: center;
        background-color: #f0f1f5;
        border-radius: 2px;
      }
    }

    .event-list {
      display: flex;
      width: 96%;
      padding-bottom: 10px;
      margin-top: 20px;
      margin-left: 2%;
      background: #fff;

      .event-list-left {
        width: 144px;
        margin-left: 10px;
        background: #f5f7fa;
        border-radius: 4px;

        .event-time {
          width: 100%;
          height: 32px;
          font-size: 12px;
          line-height: 32px;
          color: #4d4f56;
          text-align: center;
          cursor: pointer;
        }

        .active-event {
          background: #e1ecff;
          border-left: 3px solid #3a84ff;
        }
      }

      .event-list-right {
        width: calc(100% - 154px);
        margin-left: 10px;

        .right-info {
          .right-info-title {
            font-size: 14px;
            font-weight: 700;
            line-height: 22px;
            letter-spacing: 0;
            color: #313238;
          }

          .right-info-item {
            /* display: flex;
            justify-content: space-between; */
            margin-top: 10px;
            margin-bottom: 10px;

            .info-item {
              display: inline-block;
              width: 50%;
              font-size: 12px;
              line-height: 32px;
              letter-spacing: 0;
              color: #4d4f56;
            }
          }

          .events-evidence {
            border-top: 1px solid #c4c6cc;

            .evidence-item {
              display: flex;
              height: 32px;
              line-height: 32px;
              border-bottom: 1px solid #c4c6cc;

              .evidence-title {
                width: 25%;
                padding-right: 10px;
                text-align: right;
              }

              .evidence-value {
                width: 25%;
                padding-left: 10px;
                text-align: left;
                border-left: 1px solid #c4c6cc;
              }
            }
          }
        }
      }
    }
  }

  .dashed-underline {
    padding-bottom: 2px;
    cursor: pointer;
    border-bottom: 1px dashed #c4c6cc;
  }
}
</style>
