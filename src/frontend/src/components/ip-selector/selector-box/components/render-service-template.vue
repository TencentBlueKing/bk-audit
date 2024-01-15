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
  <bk-loading :loading="isTemplateTopoLoading">
    <div class="render-service-template">
      <div class="topo-tree-box">
        <bk-input
          v-model="templateTopoSearch"
          :placeholder="t('搜索拓扑节点')" />
        <div class="topo-tree-container">
          <div
            v-for="nodeItem in renderTemplateTopoList"
            :key="nodeItem.bk_inst_id"
            class="template-node-row">
            <bk-checkbox
              :label="nodeItem.bk_inst_id"
              :model-value="Boolean(nodeCheckedMap[nodeItem.bk_inst_id])"
              @change="(value: boolean | string | number) => handleNodeCheckChange(value, nodeItem)">
              {{ nodeItem.bk_inst_name }}
            </bk-checkbox>
          </div>
          <bk-exception
            v-if="renderTemplateTopoList.length < 1"
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
          :placeholder="t('搜索节点名')" />
        <bk-loading :loading="isNodeBaseInfoLoading">
          <table>
            <thead>
              <tr>
                <th style="width: 180px;">
                  {{ t('节点名称') }}
                </th>
                <th>
                  {{ t('Agent 状态') }}
                </th>
                <th style="width: 80px;">
                  {{ t('分类') }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="nodeBaseInfo in renderList"
                :key="nodeBaseInfo.node_path">
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
                <td>
                  --
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
  </bk-loading>
</template>
<script setup lang="ts">
  import {
    shallowRef,
    triggerRef,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import BizManageService from '@service/biz-manage';

  import type NodeInstanceStatusModel from '@model/biz/node-instance-status';
  import type TemplateTopoModel from '@model/biz/template-topo';

  import useRequest from '@hooks/use-request';

  import useRenderList from '../hooks/use-render-list';
  import useSearchList from '../hooks/use-serach-list';

  interface Props {
    bizId: number,
    lastServiceTemplateList: Array<TemplateTopoModel>
  }
  interface Emits {
    (e: 'change', type: 'serviceTemplate', value: Array<TemplateTopoModel>): void
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();


  type TNodeAgentStatusMap = Record<number, NodeInstanceStatusModel>
  type TNodeCheckedMap = Record<number, TemplateTopoModel>
  const { t } = useI18n();

  let innerChange = false;
  const nodeAgentStatusMap = shallowRef<TNodeAgentStatusMap>({});
  const nodeCheckedMap = shallowRef<TNodeCheckedMap>({});

  // 同步外部变更
  watch(() => props.lastServiceTemplateList, (lastServiceTemplateList) => {
    if (innerChange) {
      innerChange = false;
      return;
    }
    nodeCheckedMap.value = lastServiceTemplateList.reduce((result, item) => {
      // eslint-disable-next-line no-param-reassign
      result[item.bk_inst_id] = item;
      return result;
    }, {} as TNodeCheckedMap);
  }, {
    immediate: true,
  });

  // 获取服务模板节点列表
  const {
    loading: isTemplateTopoLoading,
    data: templateTopoList,
    // eslint-disable-next-line vue/no-setup-props-destructure
  } = useRequest(BizManageService.fetchAllTemplateTopo, {
    defaultParams: {
      biz_id: props.bizId,
      template_type: 'SERVICE_TEMPLATE',
    },
    defaultValue: [],
    manual: true,
  });

  const {
    search: templateTopoSearch,
    list: renderTemplateTopoList,
  } = useSearchList(templateTopoList, (node, rule) => rule.test(node.bk_inst_name));

  // 获取 template topo node 的 agent status 基础信息
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
      triggerRef(nodeAgentStatusMap);
    },
  });

  // 获取 template topo node 的基础信息
  // 异步获取节点的 agent status 信息
  const {
    loading: isNodeBaseInfoLoading,
    data: nodeBaseInfoList,
    run: fetchTemplateNodesBaseInfo,
  } = useRequest(BizManageService.fetchTemplateNodesBaseInfo, {
    defaultValue: [],
    onSuccess(data) {
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
  } = useRenderList(nodeBaseInfoList, (node, rule) => rule.test(node.bk_inst_name));

  const handleNodeCheckChange = (checked: boolean | string | number, node: TemplateTopoModel) => {
    if (checked) {
      nodeCheckedMap.value[node.bk_inst_id] = node;
    } else {
      delete nodeCheckedMap.value[node.bk_inst_id];
    }
    fetchTemplateNodesBaseInfo({
      biz_id: props.bizId,
      bk_inst_ids: Object.keys(nodeCheckedMap.value).join(','),
      template_type: 'SERVICE_TEMPLATE',
    });
    innerChange = true;
    emits('change', 'serviceTemplate', Object.values(nodeCheckedMap.value));
  };
</script>
<style lang="postcss">
  .render-service-template {
    display: flex;

    .topo-tree-box {
      width: 240px;

      .topo-tree-container {
        height: 473px;
        margin-top: 8px;
        overflow: auto;
      }

      .template-node-row {
        line-height: 32px;
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
