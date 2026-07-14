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
    :loading="!isPageReady"
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
          :disabled="!isFinished && !isEmpty"
          :loading="isNextLoading"
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
    onMounted,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
    useRouter,
  } from 'vue-router';

  import CollectorManageService from '@service/collector-manage';

  import { BcsContent, BcsContentChild } from '@model/collector/bcs-task-status';
  import CollectorDetailModel from '@model/collector/collector-detail';
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

  const physicsColumns = [
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

  const bcsColumns = [
    {
      label: 'ID',
      field: () => 'container_collector_config_id',
    },
    {
      label: () => t('名称'),
      field: () => 'name',
    },
    {
      label: () => t('状态'),
      render: ({ data }: {data: BcsContentChild}) => (
          <>
            <audit-icon
              class="rotate-loading"
              svg
              type={data.statusIconType} />
            <span>{ data.statusText }</span>
          </>
        ),
    },
  ] as Column[];

  const route = useRoute();
  const router = useRouter();

  const isEditMode = route.name === 'logCollectorEdit';

  const listType = ref(String(route.query.status || 'all'));
  const isShowDetail = ref(false);
  const logInstanceId = ref('');
  const isPageReady = ref(false);

  const {
    getSearchParams,
    appendSearchParams,
    removeSearchParam,
  } = useUrlSearch();

  const searchParams = getSearchParams();
  const taskIdList = searchParams.task_id_list || '';
  const collectorConfigId = ~~(searchParams.collector_config_id
    || route.params.collectorConfigId
    || 0);
  // 以 URL 为准，缺失时再查采集详情，避免误走物理机列导致目标/时间为空
  const isContainer = ref(searchParams.environment === 'container');
  const tableColumn = computed(() => (isContainer.value ? bcsColumns : physicsColumns));

  // 轮询取消函数
  let cancelLoop: (() => void) | null = null;
  let statusWatchStop: (() => void) | null = null;

  const {
    data: physicsTaskStatus,
    loop: loopPhysicsTaskStatus,
    run: fetchPhysicsTaskStatus,
  } = useRequest(CollectorManageService.fetchCollectorTaskStatus, {
    defaultParams: {
      collector_config_id: collectorConfigId,
      task_id_list: taskIdList,
    },
    defaultValue: new CollectorTaskStatusModel(),
    manual: false,
    loopOnError: true,
  });

  const {
    data: bcsTaskStatus,
    loop: loopBcsTaskStatus,
    run: fetchBcsTaskStatus,
  } = useRequest(CollectorManageService.fetchBcsTaskStatus, {
    defaultParams: {
      collector_config_id: collectorConfigId,
      task_id_list: [],
    },
    defaultValue: new BcsContent(),
    manual: false,
    loopOnError: true,
  });

  const {
    run: fetchCollectorDetail,
  } = useRequest(CollectorManageService.fetchCollectorsById, {
    defaultValue: new CollectorDetailModel(),
    manual: false,
  });

  const collectorTaskStatus = computed(() => (
    isContainer.value ? bcsTaskStatus.value : physicsTaskStatus.value
  ));

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
    if (!isPageReady.value) {
      return false;
    }
    if (isContainer.value) {
      // 容器：加载完成后，无执行中任务即可进入下一步
      return collectorTaskStatus.value.runningList.length < 1;
    }
    const {
      allList,
      runningList,
    } = physicsTaskStatus.value;
    if (!physicsTaskStatus.value.task_ready) {
      return false;
    }
    // 物理机：有任务数据且没有运行中的任务
    return allList.length > 0 && runningList.length < 1;
  });

  // 下发任务是否为空
  const isEmpty = computed(() => {
    if (!isPageReady.value) {
      return false;
    }
    if (isContainer.value) {
      return collectorTaskStatus.value.allList.length < 1;
    }
    return physicsTaskStatus.value.task_ready
      && physicsTaskStatus.value.allList.length < 1;
  });

  // 等待任务状态接口 / 轮询结果时，下一步按钮展示 loading
  const isNextLoading = computed(() => !isFinished.value && !isEmpty.value);

  // 开启轮询并监听任务状态
  const startLoopAndWatch = (loopFn: () => () => void) => {
    if (!cancelLoop) {
      cancelLoop = loopFn();
      if (!statusWatchStop) {
        statusWatchStop = watch(collectorTaskStatus, () => {
          setTimeout(() => {
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

  // 失败重试
  const {
    loading: isRetryTaskLoading,
    run: retryStask,
  } = useRequest(CollectorManageService.retryStask);

  const getSmartActionOffsetTarget = () => document.querySelector('.status-operation-box');

  // 失败批量重试
  const handleRetryFaildTask = () => {
    if (isContainer.value) {
      const instanceIdList = bcsTaskStatus.value.failedList.map(item => item.container_collector_config_id);
      retryStask({
        id: collectorConfigId,
        instance_id_list: instanceIdList,
      });
      return;
    }
    const targetNodes = physicsTaskStatus.value.failedList.map(item => ({
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
        emits('previous', 2);
        removeSearchParam([
          'collector_config_id',
          'task_id_list',
          'environment',
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

  const startStatusPolling = () => {
    if (isContainer.value) {
      fetchBcsTaskStatus({
        collector_config_id: collectorConfigId,
        task_id_list: [],
      }).finally(() => {
        isPageReady.value = true;
        startLoopAndWatch(loopBcsTaskStatus);
      });
      return;
    }
    fetchPhysicsTaskStatus({
      collector_config_id: collectorConfigId,
      task_id_list: taskIdList,
    }).finally(() => {
      isPageReady.value = true;
      startLoopAndWatch(loopPhysicsTaskStatus);
    });
  };

  onMounted(async () => {
    // URL 未带 environment 时，用采集详情兜底识别容器
    if (!isContainer.value && collectorConfigId) {
      try {
        const detail = await fetchCollectorDetail({
          id: String(collectorConfigId),
        });
        if (detail.environment === 'container') {
          isContainer.value = true;
          appendSearchParams({
            environment: 'container',
            collector_config_id: collectorConfigId,
          });
        }
      } catch (e) {
        console.error(e);
      }
    }
    startStatusPolling();
  });
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
