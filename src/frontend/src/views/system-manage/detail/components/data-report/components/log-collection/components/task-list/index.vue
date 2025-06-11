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
    ref="listRef"
    class="collector-task-list"
    :style="{ height: `${listHeight}px` }">
    <scroll-faker v-if="!isStatusLoading">
      <div class="wrapper">
        <!-- collector -->
        <div
          v-for="item in collectorLists"
          :key="item.collector_config_id"
          action-id="view_collection_v2_bk_log"
          class="collector-item"
          :class="{
            checked: item.collector_config_id === checked
          }"
          @click="handleChecked(item.collector_config_id, item.collector_config_name)"
          @mouseenter="handleOperationMouseenter(item.collector_config_id)"
          @mouseleave="handleOperationMouseleave">
          <div class="collector-type-icon">
            <audit-icon
              class="type-icon"
              type="blueking" />
          </div>
          <div class="collector-item-content">
            <span class="collector-item-name">
              <span>{{ item.custom_type }}</span>
            </span>
            <div>
              <audit-icon
                class="status-icon"
                :class="{
                  'rotate-loading': statusMap[item.collector_config_id].isRunning
                }"
                svg
                :type="statusMap[item.collector_config_id].icon" />
              <span class="collector-sub-title">
                {{ item.collector_config_name }}
              </span>
            </div>
          </div>
          <div class="collector-item-operation">
            <component
              :is="statusCom[statusMap[item.collector_config_id]?.operation]"
              :id="props.id"
              :checked="checked"
              :current="current"
              :data="item"
              @get-collector-lists="handleFetchLists" />
          </div>
        </div>

        <!-- dataid -->
        <div
          v-for="item in dataIdList"
          :key="item.bk_data_id"
          class="collector-item"
          :class="{
            checked: item.bk_data_id === checked
          }"
          @click="handleChecked(item.bk_data_id, item.collector_config_name,'bkbase')"
          @mouseenter="handleOperationMouseenter(item.bk_data_id)"
          @mouseleave="handleOperationMouseleave">
          <div class="collector-type-icon">
            <audit-icon
              class="type-icon"
              type="bkbase" />
          </div>
          <div class="collector-item-content">
            <span class="collector-item-name">
              <span>bkbase</span>
            </span>
            <div>
              <audit-icon
                class="status-icon"
                svg
                :type="item.bkbase_table_id ? 'normal' :'warning'" />
              <span class="collector-sub-title">
                {{ item.collector_config_name }}
              </span>
            </div>
          </div>
          <div class="collector-item-operation">
            <component
              :is="dataIdStatusCom[dataIdStatusMap[item.bk_data_id].operation]"
              :id="props.id"
              :checked="checked"
              :current="current"
              :data="item"
              @get-collector-lists="handleDataIdList" />
          </div>
        </div>
      </div>
    </scroll-faker>
  </div>
</template>
<script setup lang="ts">
  import {
    type Component,
    onMounted,
    type Ref,
    ref,
  } from 'vue';
  import { useRoute } from 'vue-router';

  import CollectorManageService from '@service/collector-manage';
  import DataIdManageService from '@service/dataid-manage';

  import BatchSubscriptionStatusModel from '@model/collector/batch-subscription-status';
  import type CollectorModel from '@model/collector/collector';

  import useRequest from '@hooks/use-request';

  import { getOffset } from '@utils/assist';

  import RenderDataIdConfig from './components/dataid-render-config.vue';
  import RenderDataIdOperation from './components/dataid-render-operation/index.vue';
  import RenderConfig from './components/render-config.vue';
  import RenderDetail from './components/render-detail.vue';
  import RenderOperation from './components/render-operation/index.vue';

  interface Exposes {
    loading: Ref<boolean>
    handleCancelCheck: ()=> void
  }
  interface Emits {
    (e: 'changeChecked', value: {id: number, name:string, type?:string}): void
    (e: 'changeStatusCom', length: number): void
  }

  interface IStatus {
    [status: string]: Component
  }
  interface Props {
    id: string
  }

  const props = withDefaults(defineProps<Props>(), {
    id: '',
  });
  const emit = defineEmits<Emits>();

  const route = useRoute();

  const listRef = ref();
  const listHeight = ref(0);
  const current = ref(0);
  const checked = ref(0);
  const statusMap = ref<Record<string, BatchSubscriptionStatusModel>>({});
  const dataIdStatusMap =  ref<Record<string, BatchSubscriptionStatusModel>>({});

  const statusCom: IStatus = {
    config: RenderConfig,
    operation: RenderOperation,
    defailt: RenderDetail,
  };
  const dataIdStatusCom: IStatus = {
    config: RenderDataIdConfig,
    operation: RenderDataIdOperation,
  };
  const collectorListMap = ref<Record<number, number>>({});


  const {
    data: collectorLists,
    run: fetchList,
  } = useRequest(CollectorManageService.fetchList, {
    defaultValue: [],
    onSuccess: (result) => {
      if (result.length) {
        const collectorIdLists = result.map(item => item.collector_config_id).join(',');
        result.forEach((item) => {
          collectorListMap.value[item.collector_config_id] = item.collector_config_id;
          statusMap.value[item.collector_config_id] = {} as BatchSubscriptionStatusModel;
        });
        fetchBatchSubscriptionStatus({
          collector_id_list: collectorIdLists,
        });
      }
    },
  });
  const {
    data: dataIdList,
    run: fetchSystemDataIdList,
  } = useRequest(DataIdManageService.fetchSystemDataIdList, {
    defaultValue: [],
    onSuccess(result) {
      result.forEach((item) => {
        dataIdStatusMap.value[item.bk_data_id] = new BatchSubscriptionStatusModel();
        if (!item.bkbase_table_id) {
          dataIdStatusMap.value[item.bk_data_id].status = 'WARNING';
        } else {
          dataIdStatusMap.value[item.bk_data_id].status = 'SUCCESS';
        }
      });
    },
  });

  Promise.all([fetchList({
    system_id: route.params.id || props.id,
  }), fetchSystemDataIdList({
    system_id: route.params.id || props.id,
  })]).then((data) => {
    const result = [...data[0], ...data[1]];
    if (data[0].length) handleChecked(result[0].collector_config_id, result[0].collector_config_name);
    else if (data[1].length) handleChecked(result[0].bk_data_id, result[0].collector_config_name, 'bkbase');
    emit('changeStatusCom',  result.length);
  });
  /**
   * 批量获取下发状态
   */
  const {
    loading: isStatusLoading,
    run: fetchBatchSubscriptionStatus,
  } = useRequest(CollectorManageService.fetchBatchSubscriptionStatus, {
    defaultValue: [],
    onSuccess: (result) => {
      result.forEach((item) => {
        statusMap.value[item.collector_id] = item;
      });
      collectorLists.value.forEach((item: CollectorModel) => {
        if (statusMap.value[item.collector_config_id].status === 'SUCCESS') {
          if (!item.bkbase_table_id) {
            statusMap.value[item.collector_config_id].status = 'WARNING';
          }
        }
      });
    },
  });

  /**
   * 鼠标移入事件
   */
  const handleOperationMouseenter = (id: number) => {
    current.value = id;
  };
  /**
   * 鼠标移出事件
   */
  const handleOperationMouseleave = () => {
    current.value = 0;
  };

  const handleChecked = (id: number, name:string, type?:string) => {
    checked.value = id;
    current.value = id;
    emit('changeChecked', { id, name, type });
  };

  const handleFetchLists = () => {
    fetchList({
      system_id: route.params.id || props.id,
    });
  };
  const handleDataIdList = () => {
    fetchSystemDataIdList({
      system_id: route.params.id || props.id,
    });
  };
  defineExpose<Exposes>({
    loading: isStatusLoading,
    handleCancelCheck() {
      checked.value = 0;
    },
  });

  onMounted(() => {
    const { top } = getOffset(listRef.value);
    listHeight.value = window.innerHeight - top - 40;
  });

</script>
<style lang="postcss">
  .collector-task-list {
    .wrapper {
      padding: 0 24px;
    }

    .collector-item {
      position: relative;
      display: flex;
      height: 56px;
      padding: 8px 12px 8px 8px;
      cursor: pointer;
      background: #f5f7fa;
      border: 1px solid #f5f7fa;
      border-radius: 2px;

      &:nth-child(n+2) {
        margin-top: 8px;
      }

      .collector-type-icon {
        width: 40px;
        height: 40px;
        margin-right: 10px;
        line-height: 40px;
        text-align: center;
        background: #fff;
        border-radius: 2px;

        .type-icon {
          font-size: 21px;
          color: #979ba5;
        }
      }

      .collector-item-content {
        flex: 1;
      }

      .collector-item-name {
        display: flex;
        font-size: 12px;
        color: #979ba5;
      }

      .collector-item-operation {
        position: absolute;
        top: 8px;
        right: 0;
      }

      .status-icon {
        margin-right: 7px;
        font-size: 13px;
        color: #3a84ff;
        vertical-align: sub;
      }

      .collector-sub-title {
        font-size: 12px;
        color: #63656e;
        vertical-align: middle;
      }
    }

    .collector-item:hover {
      cursor: pointer;
      background-color: #f0f1f5;
    }

    .collector-item:first-child {
      margin-top: 0;
    }

    .checked {
      position: relative;
      background: rgb(225 236 255 / 60%) !important;
      border: 1px solid #3a84ff;
      border-radius: 2px;
    }

    .checked::after {
      position: absolute;
      top: 21px;
      right: -7px;
      border-color: #3a84ff #3a84ff transparent transparent;
      border-style: solid;
      border-width: 6px;
      content: '';
      transform: rotate(45deg);
    }
  }
</style>
