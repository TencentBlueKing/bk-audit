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
  <div class="render-static-topo">
    <div class="topo-tree-box">
      <bk-input
        v-model.trim="topoTreeSearch"
        :placeholder="t('搜索拓扑节点')" />
      <div class="topo-tree-container">
        <bk-tree
          ref="treeRef"
          children="children"
          :data="topoTreeData"
          :empty-text="t('暂无数据')"
          label="name"
          :search="topoTreeSearchOption"
          :show-node-type-icon="false"
          @node-click="handleNodeClick" />
      </div>
    </div>
    <div class="topo-node-list">
      <bk-input
        v-model="searchKey"
        :placeholder="t('搜索 IP')" />
      <bk-loading :loading="isHostInstanceListLoading">
        <table>
          <thead>
            <tr>
              <th style="width: 50px;">
                <list-check
                  :disabled="hostInstanceList.length < 1"
                  :value="listCheckValue"
                  @change="handleListCheckChange" />
              </th>
              <th style="width: 100px;">
                IP
              </th>
              <th>{{ t('Agent 状态') }}</th>
              <th>{{ t('云区域') }}</th>
              <th>
                {{ t('操作系统') }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="hostBaseInfo in renderList"
              :key="getHostKey(hostBaseInfo)"
              @click="handleTableRowClick(hostBaseInfo)">
              <td>
                <bk-checkbox
                  label
                  :model-value="Boolean(checkedMap[getHostKey(hostBaseInfo)])" />
              </td>
              <td>
                <div class="cell-text">
                  {{ hostBaseInfo.ip }}
                </div>
              </td>
              <td>
                <div class="cell-text">
                  {{ hostBaseInfo.agent_status_name }}
                </div>
              </td>
              <td>
                <div class="cell-text">
                  {{ hostBaseInfo.bk_cloud_name }}
                </div>
              </td>
              <td style="width: 80px;">
                <div class="cell-text">
                  {{ hostBaseInfo.bk_os_type || '--' }}
                </div>
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

  import type HostInstanceStatusModel from '@model/biz/host-instance-status';
  import type TopoModel from '@model/biz/topo';

  import useDebouncedRef from '@hooks/use-debounced-ref';
  import useRequest from '@hooks/use-request';

  import useListCheck from '../hooks/use-list-check';
  import useRenderList from '../hooks/use-render-list';
  import useTreeSearch from '../hooks/use-tree-search';

  import ListCheck from './list-check.vue';
  import {
    getHostKey,
    getTopoNodeIPList,
    type TTopoTreeData,
  } from './utils';

  interface Props {
    topoTreeData: Array<TTopoTreeData>,
    originalTopoTreeData: Array<TopoModel>,
    lastHostList: Array<HostInstanceStatusModel>
  }
  interface Emits {
    (e: 'change', type: 'staticTopo', value: Array<HostInstanceStatusModel>): void
  }
  type THostCheckedMap = { [key: string]: HostInstanceStatusModel }

  const props = defineProps<Props>();

  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  const treeRef = ref();
  const checkedMap = shallowRef<THostCheckedMap>({});

  const topoTreeSearch = useDebouncedRef('');
  const topoTreeSearchOption = useTreeSearch(topoTreeSearch);

  let innerChange = false;
  let selectTopoNode = {} as TopoModel;

  // 同步外部变更
  watch(() => props.lastHostList, (lastHostList) => {
    if (innerChange) {
      innerChange = false;
      return;
    }
    checkedMap.value = lastHostList.reduce((result, item) => {
      // eslint-disable-next-line no-param-reassign
      result[getHostKey(item)] = item;
      return result;
    }, {} as THostCheckedMap);
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

  // 触发更新事件
  const triggerChange = () => {
    innerChange = true;
    triggerRef(checkedMap);
    emits('change', 'staticTopo', Object.values(checkedMap.value));
  };

  // 获取 topo node 的 基础信息
  const {
    loading: isHostInstanceListLoading,
    data: hostInstanceList,
    run: fetchHostBaseInfo,
  } = useRequest(BizManageService.fetchHostBaseInfo, {
    defaultValue: [],
    onSuccess(data) {
      pagination.count = data.length;
    },
  });

  // 本地分页
  const {
    showPagination,
    searchKey,
    pagination,
    renderList,
    searchList,
  } = useRenderList(hostInstanceList,  (node, rule) => rule.test(node.ip));
  const listCheckValue = useListCheck(hostInstanceList, renderList, checkedMap, 'primaryKey');

  // 选中topo节点，获取topo节点下面的所有主机
  const handleNodeClick = (node: TTopoTreeData) => {
    selectTopoNode = node.payload;
    const ipList = getTopoNodeIPList(props.originalTopoTreeData, selectTopoNode.bk_inst_id);
    fetchHostBaseInfo({
      biz_id: selectTopoNode.bk_biz_id,
      ip_list: ipList,
    });
  };
  // 选中主机
  const handleTableRowClick = (hostBaseInfo: HostInstanceStatusModel) => {
    const hostKey = hostBaseInfo.primaryKey;
    if (checkedMap.value[hostKey]) {
      delete checkedMap.value[hostKey];
    } else {
      checkedMap.value[hostKey] = hostBaseInfo;
    }
    triggerChange();
  };
  // 本页全选、跨页全选
  const handleListCheckChange = (type: string) => {
    if (type === 'page') {
      renderList.value.forEach((item) => {
        checkedMap.value[item.primaryKey] = item;
      });
    } else if (type === 'pageCancel') {
      renderList.value.forEach((item) => {
        delete checkedMap.value[item.primaryKey];
      });
    } else if (type === 'all') {
      hostInstanceList.value.forEach((item) => {
        checkedMap.value[item.primaryKey] = item;
      });
    } else if (type === 'allCancel') {
      checkedMap.value = {};
    }
    triggerChange();
  };
</script>
<style lang="postcss">
  .render-static-topo {
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
          line-height: 20px;
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
