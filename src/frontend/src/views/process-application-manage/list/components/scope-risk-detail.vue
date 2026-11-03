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
  <div
    ref="panelRef"
    class="rule-panel">
    <render-list
      ref="scopeListRef"
      :border="['row']"
      class="audit-highlight-table rule-table"
      :columns="scopeTableColumn"
      :data-source="scopeRiskDataSource"
      is-need-scene-id
      :layout-height="layoutHeight"
      scene-id-key="scene_id"
      :sync-url="false"
      use-skeleton />
  </div>
</template>

<script setup lang='tsx'>
  import type { Column } from 'bkui-vue/lib/table/props';
  import {
    computed,
    nextTick,
    onBeforeUnmount,
    onMounted,
    ref,
  } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';

  import ProcessApplicationManageService from '@service/process-application-manage';

  import type ProcessApplicationManageModel from '@model/application/application';

  import Tooltips from '@components/show-tooltips-text/index.vue';

  interface Props{
    data: ProcessApplicationManageModel
  }
  const props = defineProps<Props>();
  const scopeRiskDataSource = ProcessApplicationManageService.fetchRuleList;
  const { t } = useI18n();
  const scopeListRef = ref();
  const panelRef = ref<HTMLElement>();
  const SIDESLIDER_HEADER = 52;
  const PANEL_PADDING_TOP = 16;
  const BOTTOM_RESERVE = 20;
  // 最大高度 = 100vh - 侧栏头部 - 面板上内边距 - 底部 20
  const layoutHeight = ref(Math.max(160, window.innerHeight - SIDESLIDER_HEADER - PANEL_PADDING_TOP - BOTTOM_RESERVE));
  const TABLE_HEAD = 42;
  const TABLE_FOOT = 60;
  // 最大高度给整张表，表体再扣掉表头和分页，超出后只滚表体
  const bodyMaxHeight = computed(() => Math.max(120, layoutHeight.value - TABLE_HEAD - TABLE_FOOT));
  let panelObserver: ResizeObserver | undefined;

  const syncLayoutHeight = () => {
    const panel = panelRef.value;
    if (!panel) return;
    const style = getComputedStyle(panel);
    const paddingTop = parseFloat(style.paddingTop) || 0;
    const rect = panel.getBoundingClientRect();
    const available = Math.floor(window.innerHeight - rect.top - paddingTop - BOTTOM_RESERVE);
    if (available < 160 || available === layoutHeight.value) return;
    layoutHeight.value = available;
  };
  const scopeTableColumn = [
    {
      label: () => t('规则ID'),
      field: () => 'rule_id',
      render: ({ data }: { data: { rule_id: string } }) => <Tooltips data={data.rule_id} />,
      sort: 'custom',
    },
    {
      label: () => t('规则名称'),
      field: () => 'name',
      sort: 'custom',
      render: ({ data }: { data: { name: string, rule_id: number,} }) => {
        const to = {
          name: 'ruleManageList',
          query: {
            rule_id: data.rule_id,
          },
        };
        return <router-link to = {to} target='_blank'>
          <Tooltips data={data.name} />
        </router-link>;
      },
    },
    {
      label: () => t('规则状态'),
      field: () => 'is_enabled',
      render: ({ data }: { data: { is_enabled: string } }) => (
        <bk-tag type={data.is_enabled ? 'success' : ''}>{data.is_enabled ? t('启用') : t('停用')}</bk-tag>
      ),
    },
  ] as Column[];

  onMounted(async () => {
    await nextTick();
    syncLayoutHeight();
    if (panelRef.value) {
      panelObserver = new ResizeObserver(() => {
        syncLayoutHeight();
      });
      panelObserver.observe(panelRef.value);
    }
    window.addEventListener('resize', syncLayoutHeight);
    if (!props.data) return;
    scopeListRef.value.fetchData({
      id: props.data.id,
      page: 1,
    });
  });

  onBeforeUnmount(() => {
    panelObserver?.disconnect();
    window.removeEventListener('resize', syncLayoutHeight);
  });
</script>
<style scoped lang="postcss">
.rule-panel {
  box-sizing: border-box;
  height: calc(100vh - 52px);
  padding: 16px 24px 20px;
  overflow: hidden;
}

.rule-table :deep(.bk-table) {
  height: auto;
  max-height: none;
}

.rule-table :deep(.bk-table-body) {
  max-height: calc(v-bind(bodyMaxHeight) * 1px);
  overflow: auto;
}

.rule-table :deep(thead th) {
  background-color: #f5f7fa;
}
</style>
