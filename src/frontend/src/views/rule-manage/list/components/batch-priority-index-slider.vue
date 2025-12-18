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
  <audit-sideslider
    ref="sidesliderRef"
    v-model:isShow="showBatchAdjustPriorityIndexDetail"
    class="batch-priority-index-slider-wrap"
    :show-footer="false"
    show-header-slot
    title="批量调整优先级"
    :width="960">
    <template #header>
      {{ t('批量调整规则执行优先级') }}
    </template>
    <bk-loading :loading="loading">
      <div style="padding: 24px 32px;">
        <bk-alert theme="info">
          {{ t('可手动拖拽排列规则的执行优先级') }}，
          <span style="font-weight: 500;">{{ t('数值越大，优先级越高') }}</span>。
        </bk-alert>
        <bk-loading :loading="listLoading">
          <bk-table
            ref="batchTableRef"
            class="rule-table batch-priority-index-table audit-highlight-table"
            :columns="priorityTableColumn"
            :data="cloneTableData"
            :row-class="handleRowClass"
            row-key="rule_id"
            style="margin-top: 19px;" />
        </bk-loading>

        <div style="margin-top: 33px;">
          <bk-button
            class="w88 mr8"
            :loading="saveLoading"
            theme="primary"
            @click="handleSavePriorityIndex">
            {{ t('保存') }}
          </bk-button>
          <bk-button
            class="w88"
            @click="handleCancel">
            {{ t('取消') }}
          </bk-button>
        </div>
      </div>
    </bk-loading>
  </audit-sideslider>
</template>

<script setup lang='tsx'>
  import Sortable from 'sortablejs';
  import {
    computed,
    nextTick,
    ref,
    watch,
  } from 'vue';
  import {
    useI18n,
  } from 'vue-i18n';

  import RiskRuleManageService from '@service/rule-manage';

  import RiskRuleManageModel from '@model/risk-rule/risk-rule';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';

  import Tooltips from '@components/show-tooltips-text/index.vue';

  import { changeConfirm } from '@utils/assist';
  import getAssetsFile from '@utils/getAssetsFile';

  interface Emits{
    (e: 'showDetail', data: RiskRuleManageModel): void,
    (e:'refreshList'): void,
  }
  interface Exposes{
    show(tableData: RiskRuleManageModel[]): void,
  }
  interface Props{
    loading: boolean,
    permissionCheckData: Record<string, boolean>
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const priorityTableColumn = [
    {
      label: () => '',
      width: 40,
      render() {
        return <p
          style='width: 100%; height: 100%;'>
          <audit-icon
            style='font-size: 16px; cursor: pointer;'
            type="move" />
        </p>;
      },
    },
    // {
    //   label: () => t('规则ID'),
    //   render: ({ data }: { data: RiskRuleManageModel }) => <Tooltips data={data.rule_id}></Tooltips>,
    // },
    {
      label: () => t('规则名称'),
      render: ({ data }: { data: RiskRuleManageModel }) => {
        const isNew = isNewData(data);
        return isNew
          ? (
            <a
              class='ignore-drag'
              style='width: 100%;display: flex;align-items: center;'
              onClick={() => handleDetail(data)}>
              <Tooltips data={data.name } />
              <img class='table-new-tip' src={getAssetsFile('new-tip.png')}
              style='width: 30px;margin-left: 4px;'/>
            </a>)
          : (
            <a
              class='ignore-drag'
              onClick={() => handleDetail(data)}>
              <Tooltips data={data.name } />
            </a>);
      },
    },
    {
      label: () => t('执行优先级'),
      field: () => 'priority_index',
      render: ({ data }: { data: RiskRuleManageModel }) => <span>{data.priority_index}</span>,
    },
    {
      label: () => t('启用/停用'),
      render: ({ data }: { data: RiskRuleManageModel }) => (
        props.permissionCheckData.edit_rule
          ? (
            <audit-popconfirm
              confirm-text={data.is_enabled ? t('停用') : t('启用')}
              content={data.is_enabled
                ? t('处理规则停用后，即使有风险命中该规则也不会按照规则制定的套餐自动处理。请确认是否停用规则？')
                : t('处理规则启用后，若有风险命中本规则会按照规则制定的套餐自动处理。请确认是否启用规则？')}
              title={data.is_enabled ? t('规则停用确认') : t('规则启用确认')}
              confirm-handler={() => handleToggle(data)}>
              <auth-switch
              action-id="edit_rule"
              class='ignore-drag'
              model-value={data.is_enabled}
              permission={props.permissionCheckData.edit_rule}
              theme="primary"
              />
          </audit-popconfirm>
          )
          : (<auth-switch
            action-id="edit_rule"
            class='ignore-drag'
            model-value={data.is_enabled}
            onClick = { () => handleToggle(data)}
            permission={props.permissionCheckData.edit_rule}
            theme="primary"
            />
          )
      ),
    },
  ] as any[];


  const showBatchAdjustPriorityIndexDetail = ref(false);
  const batchTableRef = ref();

  // 排序过后的表格key
  const sortedKey = ref<Array<string>>([]);
  const tableDataMap = computed(() => cloneTableData.value.reduce((res, item) => {
    res[item.name] = item;
    return res;
  }, {} as Record<string, RiskRuleManageModel>));
  const cloneTableData = ref<RiskRuleManageModel[]>([]);

  const {
    run: fetchRuleList,
    loading: listLoading,
  } = useRequest(RiskRuleManageService.fetchRuleList, {
    defaultValue: {
      results: [],
      total: 0,
      page: 1,
      num_pages: 1,
    },
    onSuccess(data) {
      let sortPriorityIndex = data.total;
      cloneTableData.value = data.results.map(item => new RiskRuleManageModel(item));
      cloneTableData.value.forEach((item) => {
        const tmpItem = item;
        tmpItem.priority_index = sortPriorityIndex;
        sortPriorityIndex = sortPriorityIndex - 1;
      });
      nextTick(() => {
        handlerowDrop();
      });
      setTimeout(() => {
        cloneTableData.value.forEach((item, index) => {
          const isNew = isNewData(item);
          setNewCreateTrHighlight(index, isNew);
        });
      }, 300);
    },
  });
  const {
    run: setPriorityIndex,
    loading: saveLoading,
  } = useRequest(RiskRuleManageService.setPriorityIndex, {
    defaultValue: null,
    onSuccess() {
      window.changeConfirm = false;
      showBatchAdjustPriorityIndexDetail.value = false;
      messageSuccess(t('新的规则执行优先级已生效'));
    },
  });
  const {
    run: toggleRiskRules,
  }  = useRequest(RiskRuleManageService.toggleRiskRules, {
    defaultValue: null,
    onSuccess(data) {
      if (!data) return;
      messageSuccess(data.is_enabled ? t('启用成功') : t('停用成功'));
    },
  });


  // 判断是否是新建数据
  const isNewData = (data: RiskRuleManageModel) => {
    const time = new Date(data.created_at).getTime();
    const now = new Date().getTime();
    const diff = Math.abs(now - time);
    const isNew = diff < (5 * 60 * 1000);
    return isNew;
  };
  // 排序方法
  const sortble = (el: any) => {
    if (el) {
      Sortable.create(el, {
        //  指定父元素下可被拖拽的子元素
        draggable: '.bk-table tr',
        forceFallback: true,
        animation: 100,
        delay: 80, // 定义一个延迟时间防止误触
        filter: '.ignore-drag', // 忽略拖拽
        onEnd(evt: any) {
          const { oldIndex } = evt;
          const { newIndex } = evt;
          if (oldIndex !== newIndex) {
            const list = Array.from(evt.to.rows).map((item: any) => {
              const el = (item as HTMLElement).querySelector('.show-tooltips-text')  as HTMLElement;
              return el?.innerText;
            });
            sortedKey.value = list;
            window.changeConfirm = true;

            let sortPriorityIndex = list.length;
            sortedKey.value.forEach((id) => {
              if (tableDataMap.value[id]) {
                tableDataMap.value[id].priority_index = sortPriorityIndex;
                sortPriorityIndex = sortPriorityIndex - 1;
              }
            });
          }
        },
      });
    }
  };
  const handlerowDrop = () => {
    // 此时找到的元素是要拖拽元素的父容器
    if (!batchTableRef.value) return;
    const tbody = (batchTableRef.value.$el as HTMLElement).querySelector('.bk-table-body tbody') as HTMLElement;
    if (tbody) {
      sortble(tbody);
    }
  };
  const handleRowClass = (data: RiskRuleManageModel) => data?.rule_id;
  // 批量调整优先级
  const handleSavePriorityIndex = () => {
    const params = [] as Array<{
      rule_id: string,
      priority_index: number,
      is_enabled: boolean
    }>;
    cloneTableData.value.forEach((item) => {
      params.push({
        rule_id: item.rule_id,
        priority_index: item.priority_index,
        is_enabled: item.is_enabled,
      });
    });
    setPriorityIndex({
      config: params,
    });
  };
  const handleDetail = (data: RiskRuleManageModel) => {
    emits('showDetail', data);
  };
  const handleCancel = () => {
    changeConfirm().then(() => {
      showBatchAdjustPriorityIndexDetail.value = false;
    });
  };
  // 将新建的tr高亮
  const setNewCreateTrHighlight = (index: number, isNew : boolean) => {
    const domList = document.querySelectorAll(`.audit-highlight-table .bk-table-body tbody tr:nth-child(${index + 1}) td`);
    if (domList) {
      domList.forEach((dom) => {
        const el = dom as HTMLElement;
        el.style.background = isNew ? '#f2fff4' : '#fff';
      });
    }
  };
  const handleToggle = (data: RiskRuleManageModel) => {
    toggleRiskRules({
      rule_id: data.rule_id,
      is_enabled: !data.is_enabled,
    }).then((ret) => {
      if (!ret) return;
      // eslint-disable-next-line no-param-reassign
      data.is_enabled = ret.is_enabled;
    });
  };
  watch(() => showBatchAdjustPriorityIndexDetail.value, () => {
    if (!showBatchAdjustPriorityIndexDetail.value) {
      emits('refreshList');
    }
  }, {
    immediate: true,
  });
  defineExpose<Exposes>({
    show() {
      showBatchAdjustPriorityIndexDetail.value = true;
      fetchRuleList({
        page: 1,
        page_size: 5000,
      });
    },
  });
</script>
<style lang="postcss">

.batch-priority-index-table .bk-table-body {
  max-height: calc(100vh - 280px);

  td {
    border-bottom: 1px solid #dcdee5;
  }

}

.bk-table .bk-table-head table tbody tr td.is-last,
.bk-table .bk-table-body table tbody tr td.is-last {
  border-bottom: 1px solid #dcdee5;
}

/* 修改拖拽的icon的样式 */
tr.sortable-chosen {
  cursor: move;
  opacity: 100% !important;
  box-shadow: 0 2px 4px 0 rgb(0 0 0 / 10%), 0 2px 4px 0 rgb(25 25 41 / 5%);

  td {
    background-color: #f0f5ff !important;
  }

  .audit-icon {
    color: #3a84ff !important;
  }

  td:nth-of-type(1) {
    width: 40px !important;
  }

  td:nth-of-type(2) {
    width: 20% !important;
    min-width: 200px;
  }

  td:nth-of-type(3) {
    width: 20% !important;
    min-width: 200px;
  }

  td:nth-of-type(4) {
    width: 14% !important;
  }

  td:nth-of-type(5) {
    width: 40% !important;

    input {
      width: 100%;
    }
  }
}
</style>
