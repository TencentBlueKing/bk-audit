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
  <div class="retrieval-guide-wrap">
    <div class="retrieval-guide-card">
      <!-- 已选系统 -->
      <div class="systems-section">
        <div
          class="systems-header"
          @click="systemsExpanded = !systemsExpanded">
          <div class="systems-title">
            <audit-icon
              class="title-icon"
              type="help-fill" />
            <span>已选 {{ systems.length }} 个系统</span>
          </div>
          <audit-icon
            class="expand-icon"
            :class="{ 'is-collapsed': !systemsExpanded }"
            type="angle-line-down" />
        </div>
        <template v-if="systemsExpanded">
          <div class="system-tags">
            <span
              v-for="item in systems"
              :key="item.id"
              class="system-tag">
              {{ item.name }}({{ item.id }})
            </span>
          </div>
          <div
            class="reselect-link"
            @click.stop="$emit('reselect')">
            <audit-icon
              class="reselect-icon"
              type="refresh" />
            <span>重新选择</span>
          </div>
        </template>
      </div>

      <!-- 建议操作 -->
      <div class="suggest-section">
        <div class="suggest-title">
          可按以下建议进行后续操作
        </div>
        <div class="suggest-columns">
          <div class="suggest-column">
            <div class="column-label">
              常用操作
            </div>
            <button
              v-for="(item, index) in commonSuggestions"
              :key="`common-${index}`"
              class="suggest-item"
              type="button"
              @click="$emit('select-suggestion', item)">
              {{ item }}
            </button>
          </div>
          <div class="suggest-column">
            <div class="column-label">
              历史操作
            </div>
            <button
              v-for="(item, index) in historySuggestions"
              :key="`history-${index}`"
              class="suggest-item"
              type="button"
              @click="$emit('select-suggestion', item)">
              {{ item }}
            </button>
          </div>
        </div>
      </div>

      <!-- 按字段检索 -->
      <div class="field-section">
        <div class="field-divider">
          <span class="divider-line" />
          <span class="divider-text">没有合适的操作？试试按字段检索</span>
          <span class="divider-line" />
        </div>
        <div class="field-toolbar">
          <div
            class="field-title"
            @click="fieldExpanded = !fieldExpanded">
            <span
              class="field-arrow"
              :class="{ 'is-collapsed': !fieldExpanded }" />
            <span>按字段检索</span>
          </div>
          <template v-if="fieldExpanded">
            <div class="field-tabs">
              <button
                class="field-tab"
                :class="{ 'is-active': fieldTab === 'common' }"
                type="button"
                @click="fieldTab = 'common'">
                通用字段
              </button>
              <button
                class="field-tab"
                :class="{ 'is-active': fieldTab === 'extend' }"
                type="button"
                @click="fieldTab = 'extend'">
                拓展字段
              </button>
            </div>
            <div class="field-tip">
              <audit-icon
                class="tip-icon"
                type="info-fill" />
              <span>可使用字段进行精准筛选，支持自然语言检索和条件筛选检索两种方式。</span>
            </div>
          </template>
        </div>

        <div
          v-if="fieldExpanded"
          class="field-table-wrap">
          <table
            class="field-table"
            :class="{ 'is-extend': fieldTab === 'extend' }">
            <thead>
              <tr>
                <th>字段名称</th>
                <th>字段说明</th>
                <th>最近一条数据</th>
                <th v-if="fieldTab === 'extend'">
                  所属系统
                </th>
                <th>检索方式</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, index) in currentFieldRows"
                :key="`${fieldTab}-${row.name}-${index}`">
                <td class="col-name">
                  <span
                    v-bk-tooltips="{ content: row.name, disabled: !row.name }"
                    class="cell-text">
                    {{ row.name }}
                  </span>
                </td>
                <td class="col-desc">
                  <span
                    v-bk-tooltips="{ content: row.desc, disabled: !row.desc }"
                    class="cell-text">
                    {{ row.desc }}
                  </span>
                </td>
                <td class="col-sample">
                  <span
                    v-bk-tooltips="{ content: row.sample, disabled: !row.sample }"
                    class="cell-text">
                    {{ row.sample }}
                  </span>
                </td>
                <td
                  v-if="fieldTab === 'extend'"
                  class="col-system">
                  <span
                    v-bk-tooltips="{ content: row.system, disabled: !row.system }"
                    class="cell-text">
                    {{ row.system }}
                  </span>
                </td>
                <td class="col-actions">
                  <button
                    class="action-link"
                    type="button"
                    @click="handleFieldSearch(row, 'nl')">
                    自然语言
                  </button>
                  <button
                    class="action-link"
                    type="button"
                    @click="handleFieldSearch(row, 'filter')">
                    条件筛选
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div
      v-if="filterCardShow"
      ref="filterCardAnchorRef"
      class="condition-filter-slot">
      <condition-filter-card
        :field-options="allFieldNames"
        :seed-field="filterSeedField"
        :systems="systems"
        @close="filterCardShow = false"
        @search="handleFilterSearch" />
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { computed, nextTick, ref } from 'vue';

  import ConditionFilterCard from './condition-filter-card.vue';
  import type { SelectedSystem } from '../../types';

  defineProps<{
    systems: SelectedSystem[];
  }>();

  const emit = defineEmits<{
    reselect: [];
    'select-suggestion': [text: string];
    'submit-query': [text: string];
  }>();

  interface FieldRow {
    name: string;
    desc: string;
    sample: string;
    system?: string;
  }

  const systemsExpanded = ref(true);
  const fieldExpanded = ref(true);
  const fieldTab = ref<'common' | 'extend'>('common');
  const filterCardShow = ref(false);
  const filterSeedField = ref<{ name: string; sample?: string } | null>(null);
  const filterCardAnchorRef = ref<HTMLElement | null>(null);

  const commonSuggestions = [
    '查询「替换为实际用户」近7天的删除操作',
    '查询「替换为实际安装包」近7天的下载操作',
    '查询「替换为实际安装包」近7天的成功操作',
    '查询「替换为实际用户」近30天的API操作',
  ];

  const historySuggestions = [
    '查询 frodomei 近7天的删除操作',
    '查询 audit_admin 近30天的下载操作',
    '查询「蓝盾」近7天的 package_delete 操作',
    '查询 bkci-agent-2.0.7tgz 近30天的 API 操作',
  ];

  const commonFields: FieldRow[] = [
    {
      name: '操作起始时间',
      desc: '日志中记录的操作开始时间，查询必填。',
      sample: '2026-07-07 10:00:00',
    },
    {
      name: '操作人',
      desc: '发起操作的账号或用户标识。',
      sample: 'frodomei',
    },
    {
      name: '操作人账号类型',
      desc: '账号来源类型，如个人账号、平台账号、服务账号。',
      sample: '服务账号',
    },
    {
      name: '来源系统',
      desc: '上报该条审计日志的业务系统。',
      sample: 'cetus_tk',
    },
    {
      name: '操作结果',
      desc: '操作是否成功。',
      sample: '失败',
    },
    {
      name: '操作途径',
      desc: '操作入口来源。',
      sample: 'API',
    },
    {
      name: '来源IP',
      desc: '发起操作的客户端 IP。',
      sample: '10.12.8.21',
    },
    {
      name: '事件ID',
      desc: '审计事件唯一标识。',
      sample: 'evt-cetus_tk-100000',
    },
    {
      name: '请求ID',
      desc: '业务请求链路标识。',
      sample: 'req-0mw276db-0',
    },
  ];

  const extendFields: FieldRow[] = [
    {
      name: '请求路径',
      desc: '请求路径',
      sample: '/story/api/v1/story/create/',
      system: 'cetus_tk',
    },
    {
      name: '请求方法',
      desc: '请求方法',
      sample: 'GET',
      system: 'cetus_tk',
    },
    {
      name: 'ins_cu_content',
      desc: '实例创建或更新的内容',
      sample: '',
      system: 'cetus_tk',
    },
    {
      name: '蓝盾流水线ID',
      desc: '蓝盾流水线ID',
      sample: 'p-abc123',
      system: '蓝盾',
    },
    {
      name: '蓝盾流水线名称',
      desc: '蓝盾流水线名称',
      sample: 'audit-deploy',
      system: '蓝盾',
    },
    {
      name: '项目ID',
      desc: '项目ID',
      sample: 'space-120',
      system: '蓝盾',
    },
    {
      name: '构建号',
      desc: '构建号',
      sample: '1024',
      system: '蓝盾',
    },
    {
      name: '触发方式',
      desc: '触发方式',
      sample: 'manual',
      system: '蓝盾',
    },
    {
      name: '风险等级',
      desc: '风险等级',
      sample: '高',
      system: '云安全审计',
    },
    {
      name: '告警策略',
      desc: '告警策略名称',
      sample: '异常登录检测',
      system: '云安全审计',
    },
    {
      name: '资源类型',
      desc: '权限资源类型',
      sample: 'system',
      system: '权限中心',
    },
    {
      name: '操作动作',
      desc: '权限操作动作',
      sample: 'manage',
      system: '权限中心',
    },
    {
      name: '账单周期',
      desc: '账单所属周期',
      sample: '2026-06',
      system: 'TOD账单系统',
    },
    {
      name: '费用科目',
      desc: '费用科目编码',
      sample: 'cost-cloud',
      system: 'TOD账单系统',
    },
  ];

  const currentFieldRows = computed(() => (
    fieldTab.value === 'common' ? commonFields : extendFields
  ));

  const allFieldNames = computed(() => Array.from(new Set([
    ...commonFields.map(item => item.name),
    ...extendFields.map(item => item.name),
  ])));

  const scrollFilterCardIntoView = async () => {
    await nextTick();
    // 等布局完成后再滚，确保筛选卡高度已计入滚动区域
    requestAnimationFrame(() => {
      filterCardAnchorRef.value?.scrollIntoView({
        behavior: 'smooth',
        block: 'end',
      });
    });
  };

  const handleFieldSearch = (row: FieldRow, mode: 'nl' | 'filter') => {
    if (mode === 'filter') {
      filterSeedField.value = {
        name: row.name,
        sample: row.sample,
      };
      filterCardShow.value = true;
      scrollFilterCardIntoView();
      return;
    }
    const sampleText = row.sample || '替换为实际值';
    emit('select-suggestion', `查询「${row.name}」为 ${sampleText} 的审计日志`);
  };

  const handleFilterSearch = (summary: string) => {
    filterCardShow.value = false;
    emit('submit-query', summary);
  };
</script>

<style lang="postcss" scoped>
  .retrieval-guide-wrap {
    display: flex;
    width: 900px;
    max-width: 100%;
    flex-direction: column;
    gap: 16px;
  }

  .condition-filter-slot {
    width: 100%;
  }

  .retrieval-guide-card {
    width: 100%;
    max-width: 100%;
    padding: 20px 24px 24px;
    font-size: 14px;
    line-height: 22px;
    color: #63656e;
    letter-spacing: 0;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 8px;
    box-shadow: 0 0 10px rgb(0 0 0 / 10%);
    box-sizing: border-box;
  }

  .systems-section {
    margin-bottom: 20px;
  }

  .systems-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    cursor: pointer;
    user-select: none;
  }

  .systems-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 500;
    line-height: 22px;
    color: #313238;

    .title-icon {
      font-size: 16px;
      color: #979ba5;
    }
  }

  .expand-icon {
    font-size: 14px;
    color: #979ba5;
    transition: transform .2s;

    &.is-collapsed {
      transform: rotate(-90deg);
    }
  }

  .system-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 12px;
    padding: 12px;
    background: #f0f5ff;
    border-radius: 4px;
  }

  .system-tag {
    display: inline-flex;
    max-width: 100%;
    height: 22px;
    padding: 0 8px;
    font-size: 12px;
    line-height: 22px;
    color: #63656e;
    letter-spacing: 0;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 2px;
    box-sizing: border-box;
  }

  .reselect-link {
    display: inline-flex;
    margin-top: 12px;
    color: #3a84ff;
    cursor: pointer;
    align-items: center;
    gap: 4px;

    &:hover {
      opacity: .85;
    }

    .reselect-icon {
      font-size: 14px;
    }
  }

  .suggest-section {
    margin-bottom: 8px;
  }

  .suggest-title {
    margin-bottom: 12px;
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    color: #313238;
  }

  .suggest-columns {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px 24px;
  }

  .column-label {
    margin-bottom: 8px;
    font-size: 12px;
    font-weight: 700;
    line-height: 20px;
    color: #313238;
  }

  .suggest-item {
    display: block;
    width: 100%;
    margin-bottom: 8px;
    padding: 8px 12px;
    font-size: 14px;
    line-height: 22px;
    color: #63656e;
    text-align: left;
    letter-spacing: 0;
    cursor: pointer;
    background: #f5f7fa;
    border: 1px solid transparent;
    border-radius: 4px;
    transition: background-color .15s, border-color .15s;
    box-sizing: border-box;

    &:last-child {
      margin-bottom: 0;
    }

    &:hover {
      color: #3a84ff;
      background: #f0f5ff;
      border-color: #c5d8ff;
    }
  }

  .field-section {
    margin-top: 16px;
  }

  .field-divider {
    display: flex;
    margin-bottom: 16px;
    align-items: center;
    gap: 12px;

    .divider-line {
      flex: 1;
      height: 1px;
      background: #dcdee5;
    }

    .divider-text {
      flex-shrink: 0;
      font-size: 12px;
      line-height: 20px;
      color: #979ba5;
    }
  }

  .field-toolbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px 16px;
  }

  .field-title {
    display: flex;
    font-size: 14px;
    font-weight: 700;
    line-height: 22px;
    color: #313238;
    cursor: pointer;
    user-select: none;
    align-items: center;
    gap: 6px;

    .field-arrow {
      display: inline-block;
      width: 0;
      height: 0;
      border-style: solid;
      border-width: 7px 5px 0;
      border-color: #63656e transparent transparent;
      transition: transform .2s;
      flex-shrink: 0;

      &.is-collapsed {
        transform: rotate(-90deg);
      }
    }
  }

  .field-tabs {
    display: inline-flex;
    padding: 2px;
    background: #f0f1f5;
    border-radius: 4px;
  }

  .field-tab {
    height: 28px;
    padding: 0 12px;
    font-size: 12px;
    line-height: 28px;
    color: #63656e;
    cursor: pointer;
    background: transparent;
    border: none;
    border-radius: 2px;

    &.is-active {
      color: #3a84ff;
      background: #fff;
      box-shadow: 0 1px 2px rgb(0 0 0 / 6%);
    }
  }

  .field-tip {
    display: flex;
    flex: 1;
    min-width: 240px;
    font-size: 12px;
    line-height: 20px;
    color: #979ba5;
    align-items: flex-start;
    gap: 4px;

    .tip-icon {
      margin-top: 2px;
      font-size: 14px;
      color: #979ba5;
      flex-shrink: 0;
    }
  }

  .field-table-wrap {
    margin-top: 12px;
    overflow: auto;
    border: 1px solid #dcdee5;
    border-radius: 2px;
  }

  .field-table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;

    th,
    td {
      padding: 0 16px;
      overflow: hidden;
      font-size: 12px;
      line-height: 20px;
      text-align: left;
      vertical-align: middle;
      border-bottom: 1px solid #dcdee5;
      box-sizing: border-box;
    }

    th {
      height: 42px;
      font-weight: 400;
      color: #313238;
      background: #fafbfd;
    }

    td {
      height: 42px;
      color: #63656e;
      background: #fff;
    }

    tbody tr:nth-child(even) td {
      background: #fafbfd;
    }

    tbody tr:last-child td {
      border-bottom: none;
    }

    .cell-text {
      display: block;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .col-name {
      width: 18%;
      font-weight: 400;
      color: #313238;
    }

    .col-desc {
      width: 34%;
    }

    .col-sample {
      width: 28%;
    }

    .col-system {
      width: 14%;
    }

    .col-actions {
      width: 20%;
      overflow: visible;
      white-space: nowrap;
    }

    &.is-extend {
      .col-name {
        width: 16%;
      }

      .col-desc {
        width: 26%;
      }

      .col-sample {
        width: 24%;
      }

      .col-actions {
        width: 18%;
      }
    }
  }

  .action-link {
    margin-right: 12px;
    padding: 0;
    font-size: 12px;
    line-height: 20px;
    color: #3a84ff;
    cursor: pointer;
    background: none;
    border: none;

    &:last-child {
      margin-right: 0;
    }

    &:hover {
      opacity: .85;
    }
  }

  @media (max-width: 720px) {
    .suggest-columns {
      grid-template-columns: 1fr;
    }

    .field-table {
      table-layout: auto;
    }
  }
</style>
