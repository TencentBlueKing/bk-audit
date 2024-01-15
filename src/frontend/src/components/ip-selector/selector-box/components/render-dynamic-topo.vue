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
  <div class="render-dynamic-topo">
    <div class="topo-tree-box">
      <bk-input
        v-model.trim="topoTreeSearch"
        :placeholder="t('搜索拓扑节点')"
        type="search" />
      <div class="topo-tree-container">
        <bk-tree
          v-if="topoTreeData.length"
          ref="treeRef"
          :auto-open-parent-node="false"
          children="children"
          :data="topoTreeData"
          label="name"
          node-key="id"
          :search="topoTreeSearchOption"
          :show-node-type-icon="false"
          @node-click="handleNodeClick" />
        <bk-exception
          v-else
          class="exception-part"
          scene="part"
          type="search-empty">
          {{ t('暂无数据') }}
        </bk-exception>
      </div>
    </div>
    <div class="topo-node-list">
      <bk-input
        v-model.trim="searchKey"
        :placeholder="t('搜索子节点名称')"
        type="search" />
      <bk-loading :loading="isNodeBaseInfoLoading">
        <table>
          <thead>
            <tr>
              <th style="width: 50px;">
                <list-check
                  :disabled="nodeBaseInfoList.length < 1"
                  :value="listCheckValue"
                  @change="handleListCheckChange" />
              </th>
              <th style="width: 220px;">
                {{ t('子节点名称') }}
              </th>
              <th>{{ t('Agent 状态') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="nodeBaseInfo in renderList"
              :key="nodeBaseInfo.node_path"
              @click="handleTableRowClick(nodeBaseInfo)">
              <td>
                <bk-checkbox
                  label
                  :model-value="Boolean(checkedMap[nodeBaseInfo.bk_inst_id])" />
              </td>
              <td>
                <div class="cell-text">
                  {{ nodeBaseInfo.node_path }}
                </div>
              </td>
              <td>
                <audit-icon
                  v-if="!nodeAgentStatusMap[nodeBaseInfo.bk_inst_id]"
                  class="rotate-loading"
                  svg
                  type="loading" />
                <template v-else>
                  <span>
                    <span class="number">{{ nodeAgentStatusMap[nodeBaseInfo.bk_inst_id].count }}</span>
                    {{ t('台主机') }}
                  </span>
                  <span
                    v-if="nodeAgentStatusMap[nodeBaseInfo.bk_inst_id].agent_error_count > 0">
                    <span>(</span>
                    <span
                      class="number"
                      style="color: #ea3636;">
                      {{ nodeAgentStatusMap[nodeBaseInfo.bk_inst_id].agent_error_count }}
                    </span>
                    <span>{{ t('台 Agent 异常') }})</span>
                  </span>
                </template>
              </td>
            </tr>
          </tbody>
        </table>
        <bk-exception
          v-if="searchList.length < 1"
          class="exception-part"
          scene="part"
          type="search-empty">
          {{ t('暂无数据') }}
        </bk-exception>
        <bk-pagination
          v-if="showPagination"
          v-model="pagination.modelValue"
          align="center"
          class="mt8"
          :count="pagination.count"
          :limit="pagination.limit"
          :show-limit="false"
          :show-total-count="false"
          small />
      </bk-loading>
    </div>
  </div>
</template>
<script setup lang="ts">
  import {
    nextTick,
    ref,
    shallowRef,
    triggerRef,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import BizManageService from '@service/biz-manage';

  import type NodeInstanceStatusModel from '@model/biz/node-instance-status';
  import type TopoModel from '@model/biz/topo';

  import useDebouncedRef from '@hooks/use-debounced-ref';
  import useRequest from '@hooks/use-request';

  import useListCheck from '../hooks/use-list-check';
  import useRenderList from '../hooks/use-render-list';
  import useTreeSearch from '../hooks/use-tree-search';

  import ListCheck from './list-check.vue';
  import  {
    getChildNodeList,
    getTopoNodeByBkInstId,
    type TTopoTreeData,
  } from './utils';

  interface Props {
    bizId: number,
    topoTreeData: Array<TTopoTreeData>,
    originalTopoTreeData: Array<TopoModel>,
    lastNodeList: Array<NodeInstanceStatusModel>
  }
  interface Emits {
    (e: 'change', type: 'dynamicTopo', value: Array<NodeInstanceStatusModel>): void
  }
  type TNodeAgentStatusMap = Record<NodeInstanceStatusModel['bk_inst_id'], NodeInstanceStatusModel>
  type TNodeCheckedMap = Record<NodeInstanceStatusModel['bk_inst_id'], NodeInstanceStatusModel>

  const props = defineProps<Props>();

  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  let innerChange = false;
  let selectTopoNode = {} as TopoModel;

  const treeRef = ref();
  const topoTreeSearch = useDebouncedRef('');
  const topoTreeSearchOption = useTreeSearch(topoTreeSearch);
  const checkedMap = shallowRef<TNodeCheckedMap>({});
  const nodeAgentStatusMap = shallowRef<TNodeAgentStatusMap>({});

  // 同步外部变更
  watch(() => props.lastNodeList, (lastNodeList) => {
    if (innerChange) {
      innerChange = false;
      return;
    }
    checkedMap.value = lastNodeList.reduce((result, item) => {
      // eslint-disable-next-line no-param-reassign
      result[item.bk_inst_id] = item;
      return result;
    }, {} as TNodeCheckedMap);
  }, {
    immediate: true,
  });
  // 默认展开第一个节点
  watch(() => props.topoTreeData, (topoTreeData) => {
    if (topoTreeData.length > 0) {
      nextTick(() => {
        treeRef.value.setOpen([`${topoTreeData[0].id}`]);
        treeRef.value.setSelect([`${topoTreeData[0].id}`]);
        handleNodeClick(topoTreeData[0]);
      });
    }
  }, {
    immediate: true,
  });

  const triggerChange = () => {
    console.log(900);
    innerChange = true;
    triggerRef(checkedMap);
    emits('change', 'dynamicTopo', Object.values(checkedMap.value));
  };

  // 获取 nodeAgentStatus 状态
  const {
    run: fetchNodeAgentStatus,
  } = useRequest(BizManageService.fetchNodeAgentStatus, {
    defaultValue: [],
    onSuccess(data) {
      nodeAgentStatusMap.value = data.reduce((result, item) => {
        // eslint-disable-next-line no-param-reassign
        result[item.bk_inst_id] = item;
        return result;
      }, {} as TNodeAgentStatusMap);
    },
  });

  // 获取 topo node 的 hostInstance 列表
  const {
    loading: isNodeBaseInfoLoading,
    data: nodeBaseInfoList,
    run: fetchNodeBaseInfo,
  } = useRequest(BizManageService.fetchNodeBaseInfo, {
    defaultValue: [],
    onSuccess(data) {
      nodeAgentStatusMap.value = {};
      fetchNodeAgentStatus({
        biz_id: props.bizId,
        node_list: data,
      });
    },
  });

  // 本地分页
  const {
    showPagination,
    searchKey,
    pagination,
    renderList,
    searchList,
  } = useRenderList(
    nodeBaseInfoList,
    (node, rule) => rule.test(node.bk_inst_name) || rule.test(node.node_path),
  );

  const listCheckValue = useListCheck(nodeBaseInfoList, renderList, checkedMap, 'bk_inst_id');

  // 选中 topo 节点获取节点的子节点
  const handleNodeClick = (node: TTopoTreeData) => {
    selectTopoNode = node.payload;
    let nodeList = getChildNodeList(props.originalTopoTreeData, selectTopoNode.bk_inst_id);
    if (nodeList.length < 1) {
      const nodeData = getTopoNodeByBkInstId(props.originalTopoTreeData, selectTopoNode.bk_inst_id);
      if (!nodeData) {
        return;
      }
      nodeList = [nodeData];
    }
    fetchNodeBaseInfo({
      biz_id: selectTopoNode.bk_biz_id,
      node_list: nodeList,
    });
  };

  // 本页全选、跨页全选
  const handleListCheckChange = (type: string) => {
    if (type === 'page') {
      renderList.value.forEach((node) => {
        checkedMap.value[node.bk_inst_id] = node;
      });
    } else if (type === 'pageCancel') {
      renderList.value.forEach((node) => {
        delete checkedMap.value[node.bk_inst_id];
      });
    } else if (type === 'all') {
      nodeBaseInfoList.value.forEach((node) => {
        checkedMap.value[node.bk_inst_id] = node;
      });
    } else if (type === 'allCancel') {
      checkedMap.value = {};
    }
    triggerChange();
  };

  const handleTableRowClick = (node: NodeInstanceStatusModel) => {
    if (checkedMap.value[node.bk_inst_id]) {
      delete checkedMap.value[node.bk_inst_id];
    } else {
      checkedMap.value[node.bk_inst_id] = node;
    }
    triggerChange();
  };

</script>
<style lang="postcss">
  .render-dynamic-topo {
    display: flex;

    .topo-tree-box {
      width: 240px;

      .topo-tree-container {
        height: 473px;
        margin-top: 8px;
        overflow: auto;
      }
    }

    .topo-node-list {
      width: 0;
      padding-left: 20px;
      overflow: hidden;
      flex: 0 0 480px;

      table {
        width: 100%;
        margin-top: 12px;
        font-size: 12px;
        text-align: left;
        table-layout: fixed;

        tr {
          border-bottom: 1px solid #e7e8ed;
        }

        th {
          height: 40px;
          font-weight: normal;
          line-height: 40px;
          vertical-align: middle;
          background: #f5f6fa;
        }

        th,
        td {
          height: 40px;
          padding: 0 8px;
        }

        tbody {
          tr {
            cursor: pointer;
          }
        }

        .cell-text {
          width: 100%;
          height: 20px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          direction: rtl;
        }
      }
    }
  }
</style>
