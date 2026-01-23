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
  <skeleton-loading
    fullscreen
    :loading="!collectorTaskStatus.task_ready"
    name="createCollectorStep2">
    <smart-action :offset-target="getSmartActionOffsetTarget">
      <div class="collection-delivery-page">
        <bk-alert
          theme="info"
          :title="t('采集下发完成后 24 小时之内，如无配置第 3 步”字段清洗“，任务会被强制停用。')" />
        <div
          v-if="isEmpty"
          class="task-empty">
          <bk-exception
            scene="part"
            type="empty">
            {{ t('采集目标未变更，无需下发') }}
          </bk-exception>
        </div>
        <div v-else>
          <div class="status-operation-box">
            <status-tab
              v-model="listType"
              :data="collectorTaskStatus" />
            <bk-button
              :disabled="collectorTaskStatus.failedList.length < 1"
              :loading="isRetryTaskLoading"
              style="margin-left: auto;"
              @click="handleRetryFaildTask">
              {{ t('失败批量重试') }}
            </bk-button>
          </div>
          <bk-table
            :columns="tableColumn"
            :data="renderList"
            :empty-text="t('暂无数据')" />
        </div>
      </div>
      <template #action>
        <bk-button
          class="w88"
          :disabled="!isFinished"
          theme="primary"
          @click="handleNext">
          {{ t('下一步') }}
        </bk-button>
        <audit-popconfirm
          :confirm-handler="handleGoEdit"
          :content="t('采集下发完成后 24 小时之内，如无配置第 3 步”字段清洗“，任务会被强制停用。')"
          :title="t('确认返回上一步？')">
          <bk-button class="ml8">
            {{ t('上一步') }}
          </bk-button>
        </audit-popconfirm>
        <bk-button
          class="ml8"
          @click="handleGoAPPDetail">
          {{ t('返回系统详情') }}
        </bk-button>
      </template>
    </smart-action>
    <audit-sideslider
      v-model:is-show="isShowDetail"
      :show-footer="false"
      :title="t('部署详情')"
      :width="640">
      <deploy-log
        :collector-config-id="collectorConfigId"
        :instance-id="logInstanceId" />
    </audit-sideslider>
  </skeleton-loading>
</template>
<script setup lang="tsx">
  import type { Column } from 'bkui-vue/lib/table/props';
  import {
    computed,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
    useRouter,
  } from 'vue-router';

  import CollectorManageService from '@service/collector-manage';

  import CollectorTaskStatusModel, { ContentChild } from '@model/collector/task-status';

  import useRequest from '@hooks/use-request';
  import useUrlSearch from '@hooks/use-url-search';

  import DeployLog from './components/deploy-log.vue';
  import StatusTab from './components/status-tab.vue';

  interface Emits {
    (e: 'next', step?: number): void;
    (e: 'previous', step?: number): void;
  }

  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const tableColumn = [
    {
      label: () => t('目标'),
      field: () => 'ip',
    },
    {
      label: () => t('状态'),
      render: ({ data }: {data: ContentChild}) => (
          <>
            <audit-icon
              class="rotate-loading"
              svg
            type={data.statusIconType} />
            <span>{ data.statusText }</span>
          </>
        ),
    },
    {
      label: () => t('更新时间'),
      field: () => 'create_time',
    },
    {
      label: () => t('操作'),
      width: 200,
      render: ({ data }: {data: ContentChild}) => (
        <bk-button
         text
          theme="primary"
          onClick={() => handleShowLog(data)}>
          {t('部署详情')}
        </bk-button>
      ),
    },
  ] as Column[];

  const route = useRoute();
  const router = useRouter();

  const isEditMode = route.name === 'logCollectorEdit';


  const listType = ref(String(route.query.status || 'all'));
  const isShowDetail = ref(false);
  const logInstanceId = ref('');

  // table 数据
  const renderList = computed(() => {
    if (listType.value === 'successed') {
      return collectorTaskStatus.value.successList;
    } if (listType.value === 'failed') {
      return collectorTaskStatus.value.failedList;
    } if (listType.value === 'running') {
      return collectorTaskStatus.value.runningList;
    }
    return collectorTaskStatus.value.allList;
  });
  // 下发任务是否结束
  const isFinished = computed(() => {
    const {
      allList,
      runningList,
    } = collectorTaskStatus.value;
    if (!collectorTaskStatus.value.task_ready) {
      return false;
    }
    // 只有在有任务数据且没有运行中的任务时，才认为任务完成
    // child = [] 时继续轮询，等待任务数据
    return allList.length > 0 && runningList.length < 1;
  });
  // 下发任务是否为空
  const isEmpty = computed(() => collectorTaskStatus.value.task_ready
    && collectorTaskStatus.value.allList.length < 1);

  const {
    getSearchParams,
    removeSearchParam,
  } = useUrlSearch();

  const searchParams = getSearchParams();

  const taskIdList = searchParams.task_id_list;
  const collectorConfigId = ~~searchParams.collector_config_id;

  // 轮询取消函数
  let cancelLoop: (() => void) | null = null;
  let statusWatchStop: (() => void) | null = null;

  // 开启轮询并监听任务状态
  const startLoopAndWatch = () => {
    if (!cancelLoop) {
      cancelLoop = loopCollectorTaskStatus();
      // 只创建一次 watch
      if (!statusWatchStop) {
        statusWatchStop = watch(collectorTaskStatus, () => {
          // setTimeout 保证轮询判断在 isFinished 计算完成之后
          setTimeout(() => {
            // 没有执行中的任务，关闭轮询
            if (isFinished.value && cancelLoop) {
              cancelLoop();
              cancelLoop = null;
            }
          });
        }, {
          immediate: true,
        });
      }
    }
  };

  // 获取任务状态
  const {
    data: collectorTaskStatus,
    loop: loopCollectorTaskStatus,
  } = useRequest(CollectorManageService.fetchCollectorTaskStatus, {
    defaultParams: {
      collector_config_id: collectorConfigId,
      task_id_list: taskIdList,
    },
    defaultValue: new CollectorTaskStatusModel(),
    manual: true,
    loopOnError: true, // 轮询时错误也继续轮询
    onFinally() {
      // 请求完成时（无论成功还是失败）开启轮询
      startLoopAndWatch();
    },
  });

  // 失败重试
  const {
    loading: isRetryTaskLoading,
    run: retryStask,
  } = useRequest(CollectorManageService.retryStask);

  const getSmartActionOffsetTarget = () => document.querySelector('.status-operation-box');

  // 失败批量重试
  const handleRetryFaildTask = () => {
    const targetNodes = collectorTaskStatus.value.failedList.map(item => ({
      bk_cloud_id: item.bk_cloud_id,
      bk_supplier_id: item.bk_supplier_id,
      ip: item.ip,
    }));
    retryStask({
      id: collectorConfigId,
      target_nodes: targetNodes,
    });
  };

  // 部署详情
  const handleShowLog = (data: ContentChild) => {
    isShowDetail.value = true;
    logInstanceId.value = data.instance_id;
  };
  // 下一步
  const handleNext = () => {
    emits('next', 4);
  };
  // 上一步-——返回编辑采集任务
  const handleGoEdit = () => Promise.resolve()
    .then(() => {
      // 编辑状态——回退到第一步
      if (isEditMode) {
        console.log('isEditMode', isEditMode);
        emits('previous', 2);
        removeSearchParam([
          'collector_config_id',
          'task_id_list',
        ]);
        return;
      }
      // 新建状态——跳转到采集编辑页
      router.push({
        name: 'logCollectorEdit',
        params: {
          systemId: route.params.systemId,
          collectorConfigId,
        },
      });
    });
  // 返回应用详情
  const handleGoAPPDetail = () => {
    router.push({
      name: 'systemDetail',
      params: {
        id: route.params.systemId,
      },
      query: {
        contentType: 'dataReport',
      },
    });
  };
</script>
<style lang="postcss">
  .collection-delivery-page {
    padding: 24px;
    margin-bottom: 16px;
    background: #fff;
    border-radius: 2px;
    box-shadow: 0 1px 2px 0 rgb(0 0 0 / 16%);

    .task-empty {
      display: flex;
      align-items: center;
      height: 218px;
      margin-top: 16px;
      background: #fff;
      border: 1px dashed #c4c6cc;
      border-radius: 2px;
    }

    .status-operation-box {
      display: flex;
      margin: 16px 0;
      user-select: none;
    }

    .status-tab {
      display: flex;
      padding: 3px;
      font-size: 12px;
      color: #63656e;
      background: #f0f1f5;
      border-radius: 2px;
    }

    .status-tab-item {
      display: flex;
      height: 26px;
      padding: 0 8px;
      cursor: pointer;
      border-radius: 2px;
      align-items: center;
      justify-content: center;
      transition: all .15s;

      &.active {
        background: #fff;
        box-shadow: 0 1px 2px 0 rgb(0 0 0 / 8%);
      }
    }

    .action-box {
      margin-top: 33px;
    }
  }
</style>
