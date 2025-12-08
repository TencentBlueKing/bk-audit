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
  <div class="log-report-list">
    <div class="header">
      <div class="title">
        <span class="title-text">日志数据上报</span>
        <span class="title-desc-line" />
        <span class="title-desc">所有采集任务将合并为一份系统在审计中心的日志</span>
      </div>
      <bk-button
        icon="plus-line"
        theme="primary"
        @click="handleCreateLogReport">
        新建日志上报
      </bk-button>
    </div>
    <!-- 列表 -->
    <div
      ref="listRef"
      :style="{ height: `${listHeight}px` }">
      <bk-loading
        class="log-report-skeleton"
        :loading="isListLoading"
        :style="{ height: `${listHeight}px` }">
        <scroll-faker class="data-list">
          <!-- 如果有采集任务或api推送才显示 -->
          <template
            v-if="hasCollectorData || data.enabled">
            <!-- 有api推送才显示 -->
            <div
              v-if="data.enabled"
              class="data-card">
              <div class="card-main">
                <audit-icon
                  class="card-icon"
                  svg
                  type="api-4" />
                <div class="card-info">
                  <div class="card-title">
                    <span class="name">{{ token.collector_config_name }}</span>
                    <span class="sub-name">{{ token.collector_config_name_en }}</span>
                  </div>
                  <div class="card-api-push-info">
                    <!-- token -->
                    <div class="field-token">
                      <span class="field-label">Token：</span>
                      <template v-if="isHide">
                        <span
                          v-bk-tooltips="{content: token.token, placement: 'top', extCls:'token-tooltips'}"
                          class="field-value">{{ token.token }}</span>
                      </template>
                      <div v-else>
                        <span
                          v-for="i in 7"
                          :key="i"
                          class="encryption" />
                      </div>
                      <span
                        class="operation-icon">
                        <auth-component
                          action-id="edit_system"
                          :resource="route.params.id">
                          <audit-icon
                            :type="isHide?'view':'hide'"
                            @click.stop="() => isHide = !isHide" />
                        </auth-component>
                        <auth-component
                          action-id="edit_system"
                          :resource="route.params.id">
                          <audit-icon
                            v-bk-tooltips="t('复制')"
                            class="ml12"
                            type="copy"
                            @click.stop="() => execCopy(token.token, t('复制成功'))" />
                        </auth-component>
                      </span>
                    </div>
                    <!-- endpoint -->
                    <div
                      v-if="data.hosts.length"
                      class="field-endpoint">
                      <span class="field-label">EndPoint：</span>
                      <div style="display: flex; gap: 6px;">
                        <span
                          v-for="value in data.hosts"
                          :key="value">{{ value }}</span>
                      </div>
                      <div class="operation-icon">
                        <audit-icon
                          v-bk-tooltips="t('复制')"
                          class="ml12"
                          type="copy"
                          @click.stop="execCopy(data.hosts.map((item: string)=>item).join('\n'))" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div class="card-footer">
                <!-- 只有成功和失败 -->
                <div
                  class="card-status"
                  :class="[
                    apiPushStatusMap[token.collector_config_id]?.icon === 'cuo' ? 'status-danger' : 'status-success'
                  ]">
                  <audit-icon
                    style="font-size: 14px;"
                    svg
                    :type="apiPushStatusMap[token.collector_config_id]?.icon" />
                  <span
                    class="status-text">
                    {{ statusTextMap[apiPushStatusMap[token.collector_config_id]?.icon] }}
                  </span>
                </div>
                <!-- 最新一条数据 -->
                <div class="card-extra">
                  <template v-if="token.tail_log_time">
                    <span class="latest-label">最新一条数据 {{ token.tail_log_time }}</span>
                    <bk-button
                      style="font-size: 12px;"
                      text
                      theme="primary"
                      @click="handleApiPushTaillog()">
                      {{ t('查看') }}
                    </bk-button>
                  </template>
                  <template v-else>
                    <span class="latest-label">{{ t('无最新数据') }}</span>
                  </template>
                </div>
              </div>
              <div class="collector-item-operation">
                <api-push-render-operation
                  :data="{
                    token: token.token,
                    hosts: data.hosts,
                    collector_config_name: token.collector_config_name,
                  }" />
              </div>
              <recent-data
                v-if="showRecentDataMap['api']"
                :data="collectorDataMap['api']"
                @fold="showRecentDataMap['api'] = false" />
            </div>

            <!-- log 列表 -->
            <template v-if="collectorLists.length">
              <div
                v-for="item in collectorLists"
                :key="item.collector_config_id"
                class="data-card">
                <div class="card-main">
                  <audit-icon
                    class="card-icon"
                    svg
                    type="pull" />
                  <div class="card-info">
                    <div class="card-title">
                      <span class="name">{{ item.custom_type }}</span>
                      <span class="sub-name">{{ item.collector_config_name }}</span>
                    </div>
                  </div>
                </div>
                <div class="card-footer">
                  <!-- 失败、成功、未完成 -->
                  <div
                    class="card-status"
                    :class="[
                      statusMap[item.collector_config_id]?.icon === 'cuo'
                        ? 'status-danger'
                        : statusMap[item.collector_config_id]?.icon === 'completed'
                          ? 'status-success'
                          : 'status-warning',
                    ]">
                    <audit-icon
                      :class="{
                        'rotate-loading': statusMap[item.collector_config_id]?.isRunning,
                      }"
                      style="font-size: 14px;"
                      svg
                      :type="statusMap[item.collector_config_id]?.icon" />
                    <span
                      class="status-text">
                      {{ statusTextMap[statusMap[item.collector_config_id]?.icon] }}
                    </span>
                    <bk-button
                      v-if="statusMap[item.collector_config_id]?.icon === 'weiwancheng'"
                      text
                      theme="primary"
                      @click="handleCollectorConfig(item.collector_config_id)">
                      {{ t('继续配置') }}
                    </bk-button>
                  </div>
                  <!-- 最新一条数据 -->
                  <div class="card-extra">
                    <template v-if="item.tail_log_time">
                      <span class="latest-label">最新一条数据 {{ item.tail_log_time }}</span>
                      <bk-button
                        style="font-size: 12px;"
                        text
                        theme="primary"
                        @click="handleCollectorTaillog(item.collector_config_id, item.collector_config_name)">
                        {{ t('查看') }}
                      </bk-button>
                    </template>
                    <template v-else>
                      <span class="latest-label">{{ t('无最新数据') }}</span>
                    </template>
                  </div>
                </div>
                <div class="collector-item-operation">
                  <component
                    :is="statusCom[statusMap[item.collector_config_id]?.operation]"
                    :data="item"
                    @get-collector-lists="handleFetchLists" />
                </div>
                <recent-data
                  v-if="showRecentDataMap[`collector_${item.collector_config_id}`]"
                  :data="collectorDataMap[`collector_${item.collector_config_id}`]"
                  @fold="showRecentDataMap[`collector_${item.collector_config_id}`] = false" />
              </div>
            </template>

            <!-- bkbase 列表 -->
            <template v-if="dataIdList.length">
              <div
                v-for="item in dataIdList"
                :key="item.bk_data_id"
                class="data-card">
                <div class="card-main">
                  <audit-icon
                    class="card-icon"
                    svg
                    type="pull" />
                  <div class="card-info">
                    <div class="card-title">
                      <span class="name">bkbase</span>
                      <span class="sub-name">{{ item.collector_config_name }}</span>
                    </div>
                  </div>
                </div>
                <div class="card-footer">
                  <!-- 只有成功和未完成 -->
                  <div
                    class="card-status"
                    :class="[
                      dataIdStatusMap[item.bk_data_id]?.icon === 'completed'
                        ? 'status-success'
                        : 'status-warning',
                    ]">
                    <audit-icon
                      style="font-size: 14px;"
                      svg
                      :type="dataIdStatusMap[item.bk_data_id]?.icon" />
                    <span
                      class="status-text">
                      {{ statusTextMap[dataIdStatusMap[item.bk_data_id]?.icon] }}
                    </span>
                    <bk-button
                      v-if="dataIdStatusMap[item.bk_data_id]?.icon === 'weiwancheng'"
                      text
                      theme="primary"
                      @click="handleDataIdConfig(item.bk_data_id)">
                      {{ t('继续配置') }}
                    </bk-button>
                  </div>
                  <!-- 最新一条数据 -->
                  <div class="card-extra">
                    <template v-if="item.tail_log_time">
                      <span class="latest-label">最新一条数据 {{ item.tail_log_time }}</span>
                      <bk-button
                        style="font-size: 12px;"
                        text
                        theme="primary"
                        @click="handleDataIdTaillog(item.bk_data_id, item.collector_config_name, 'bkbase')">
                        {{ t('查看') }}
                      </bk-button>
                    </template>
                    <template v-else>
                      <span class="latest-label">{{ t('无最新数据') }}</span>
                    </template>
                  </div>
                </div>
                <div class="collector-item-operation">
                  <component
                    :is="dataIdStatusCom[dataIdStatusMap[item.bk_data_id].operation]"
                    ref="dataIdStatusComRef"
                    :data="item"
                    @get-collector-lists="handleDataIdList" />
                </div>
                <recent-data
                  v-if="showRecentDataMap[`dataid_${item.bk_data_id}`]"
                  :data="collectorDataMap[`dataid_${item.bk_data_id}`]"
                  @fold="showRecentDataMap[`dataid_${item.bk_data_id}`] = false" />
              </div>
            </template>
          </template>
          <!-- 暂无数据 -->
          <div
            v-else
            class="empty-content">
            <bk-exception
              description="暂无数据"
              type="empty" />
          </div>
        </scroll-faker>
      </bk-loading>
    </div>
  </div>
</template>

<script setup lang="ts">
  import {
    type Component,
    computed,
    nextTick,
    onMounted,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import CollectorManageService from '@service/collector-manage';
  import DataIdManageService from '@service/dataid-manage';

  import BatchSubscriptionStatusModel from '@model/collector/batch-subscription-status';
  import type CollectorModel from '@model/collector/collector';
  import CollectorDetailModel from '@model/collector/collector-detail';

  import {
    execCopy,
    getOffset,
  } from '@utils/assist';

  import ApiPushRenderOperation from './components/api-push-render-operation/index.vue';
  import RenderDataIdConfig from './components/dataid-render-config.vue';
  import RenderDataIdOperation from './components/dataid-render-operation/index.vue';
  import RecentData from './components/recent-data.vue';
  import RenderConfig from './components/render-config.vue';
  import RenderDetail from './components/render-detail.vue';
  import RenderOperation from './components/render-operation/index.vue';

  import useRequest from '@/hooks/use-request';

  interface IStatus {
    [status: string]: Component
  }
  interface CollectorData {
    id: number|string;
    name: string;
    type?: string;
  }

  const { t } = useI18n();
  const router = useRouter();
  const route = useRoute();

  const listRef = ref();
  const dataIdStatusComRef = ref();
  const isHide = ref(false);
  const listHeight = ref(0);
  const isListLoading = ref(true);

  const showRecentDataMap = ref<Record<string, boolean>>({});
  const collectorDataMap = ref<Record<string, CollectorData>>({});

  const statusMap = ref<Record<string, BatchSubscriptionStatusModel>>({});
  const dataIdStatusMap =  ref<Record<string, BatchSubscriptionStatusModel>>({});
  const apiPushStatusMap = ref<Record<string, BatchSubscriptionStatusModel>>({});

  const statusTextMap = ref<Record<string, string>>({
    cuo: t('数据上报异常'),
    completed: t('数据上报正常'),
    weiwancheng: t('未完成配置，请'),
  });
  const statusCom: IStatus = {
    config: RenderConfig,
    operation: RenderOperation,
    defailt: RenderDetail,
  };
  const dataIdStatusCom: IStatus = {
    config: RenderDataIdConfig,
    operation: RenderDataIdOperation,
  };

  const hasCollectorData = computed(() => collectorLists.value.length > 0 || dataIdList.value.length > 0);

  const handleCreateLogReport = () => {
    const url = router.resolve({
      name: 'logCreate',
      params: {
        systemId: route.params.id,
      },
    }).href;
    window.open(url, '_blank');
  };

  const handleApiPushTaillog = () => {
    const key = 'api';
    showRecentDataMap.value[key] = !showRecentDataMap.value[key];
    if (showRecentDataMap.value[key]) {
      collectorDataMap.value[key] = { id: 'api', name: 'API' };
    }
  };

  // 查看上报数据log
  const handleCollectorTaillog = (collectorConfigId: number, collectorConfigName: string) => {
    const key = `collector_${collectorConfigId}`;
    showRecentDataMap.value[key] = !showRecentDataMap.value[key];
    if (showRecentDataMap.value[key]) {
      collectorDataMap.value[key] = { id: collectorConfigId, name: collectorConfigName };
    }
  };

  // 查看上报数据bkbase
  const handleDataIdTaillog = (bkDataId: number, collectorConfigName: string, type: string) => {
    const key = `dataid_${bkDataId}`;
    showRecentDataMap.value[key] = !showRecentDataMap.value[key];
    if (showRecentDataMap.value[key]) {
      collectorDataMap.value[key] = { id: bkDataId, name: collectorConfigName, type };
    }
  };

  const {
    run: fecthDetail,
  } = useRequest(DataIdManageService.fecthDetail, {
    defaultValue: null,
  });

  // 继续配置bkbase
  const handleDataIdConfig = (bkDataId: number) => {
    fecthDetail({
      bk_data_id: bkDataId,
    }).then(() => {
      router.push({
        name: 'logDataIdEdit',
        params: {
          systemId: route.params.id,
          bkDataId,
        },
        query: {
          step: 2, // 字段清洗
          type: 'bkbase',
        },
      });
    });
  };

  const {
    run: fetchCollectorsById,
  } = useRequest(CollectorManageService.fetchCollectorsById, {
    defaultValue: new CollectorDetailModel(),
  });

  // 继续配置log
  const handleCollectorConfig = (collectorConfigId: number) => {
    fetchCollectorsById({
      id: collectorConfigId,
    }).then((result) => {
      router.push({
        name: 'logCollectorEdit',
        params: {
          systemId: route.params.id,
          collectorConfigId,
        },
        query: {
          collector_config_id: collectorConfigId,
          task_id_list: result.task_id_list.join(','),
          step: 4, // 字段清洗
          environment: result.environment,
          type: 'newLogCollector',
        },
      });
    });
  };

  const handleFetchLists = () => {
    fetchList({
      system_id: route.params.id,
    });
  };

  const handleDataIdList = () => {
    fetchSystemDataIdList({
      system_id: route.params.id,
    });
  };

  // 获取token
  const {
    run: fetchApiPush,
    data: token,
  }  = useRequest(CollectorManageService.fetchApiPush, {
    defaultValue: {},
    onSuccess: () => {
      // 获取apipush最新数据用于判断状态
      fetchApiPushTailLog({
        system_id: route.params.id,
      });
    },
  });

  // 获取启用状态&上报host （无需单独鉴权）
  const {
    data,
    run: fetchApiPushHost,
  }  = useRequest(CollectorManageService.fetchApiPushHost, {
    defaultValue: {
      enabled: true,
      hosts: [],
    },
    defaultParams: {
      system_id: route.params.id,
    },
  });

  // 用于判断apipush的状态和数据获取
  const {
    run: fetchApiPushTailLog,
    // data: apiPushTailLogData,
  } = useRequest(CollectorManageService.fetchApiPushTailLog, {
    defaultParams: {
      system_id: route.params.id,
    },
    defaultValue: [],
    onSuccess: (data) => {
      apiPushStatusMap.value[token.value.collector_config_id] = new BatchSubscriptionStatusModel();
      // apipush 只有成功和失败
      if (data.length) {
        apiPushStatusMap.value[token.value.collector_config_id].status = 'SUCCESS';
        // 最新一条数据时间
        token.value.tail_log_time = data[0].origin.datetime;
      } else {
        apiPushStatusMap.value[token.value.collector_config_id].status = 'FAILED';
      }
    },
  });

  /**
   * 批量获取下发状态
   */
  const {
    run: fetchBatchSubscriptionStatus,
  } = useRequest(CollectorManageService.fetchBatchSubscriptionStatus, {
    defaultValue: [],
    onSuccess: (result) => {
      result.forEach((item) => {
        statusMap.value[item.collector_id] = item;
      });
      // log 有成功、失败和未完成
      collectorLists.value.forEach((item: CollectorModel) => {
        if (statusMap.value[item.collector_config_id].status === 'SUCCESS') {
          if (!item.bkbase_table_id) {
            statusMap.value[item.collector_config_id].status = 'WARNING';
          }
        }
      });
    },
  });

  const {
    data: collectorLists,
    run: fetchList,
  } = useRequest(CollectorManageService.fetchList, {
    defaultValue: [],
    onSuccess: (result) => {
      if (result.length) {
        const collectorIdLists = result.map(item => item.collector_config_id).join(',');
        result.forEach((item) => {
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
        // bkbase 只有成功和未完成
        if (!item.bkbase_table_id) {
          dataIdStatusMap.value[item.bk_data_id].status = 'WARNING';
        } else {
          dataIdStatusMap.value[item.bk_data_id].status = 'SUCCESS';
        }
      });
    },
  });

  onMounted(() => {
    const systemId = route.params.id;
    const apiPushPromise = fetchApiPush({
      system_id: systemId,
    });
    const apiPushHostPromise = fetchApiPushHost({
      system_id: systemId,
    });
    const collectorPromise = fetchList({
      system_id: systemId,
    });
    const dataIdPromise = fetchSystemDataIdList({
      system_id: systemId,
    });

    Promise.all([apiPushPromise, apiPushHostPromise, collectorPromise, dataIdPromise]).finally(() => {
      isListLoading.value = false;
    });

    nextTick(() => {
      const { top } = getOffset(listRef.value);
      listHeight.value = window.innerHeight - top - 80;
    });
  });

</script>

<style scoped lang="postcss">
.log-report-list {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 14px 6px;
  background: #fff;
}

.log-report-skeleton {
  flex: 1;
}

.header {
  margin-bottom: 16px;

  .title {
    display: flex;
    margin-bottom: 14px;
    align-items: center;

    .title-text {
      font-size: 18px;
      font-weight: 600;
      line-height: 26px;
      color: #313238;
    }

    .title-desc {
      font-size: 12px;
      color: #979ba5;
      vertical-align: middle;
    }

    .title-desc-line {
      width: 1px;
      height: 12px;
      margin: 0 10px;
      background: #979ba5;
    }
  }
}


.empty-content {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

:deep(.data-list) {
  height: 100%;
  padding: 20px 16px;
  background: #f5f7fa;

  .scroll-faker-content {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .data-card {
    position: relative;
    display: flex;
    padding: 16px;
    background: #fff;
    border-radius: 8px;

    /* box-shadow: 0 2px 4px 0 #0d191929; */
    flex-direction: column;
    gap: 16px;

    .card-main {
      display: flex;
      gap: 16px;

      .card-icon {
        display: flex;
        width: 50px;
        height: 50px;
        justify-content: center;
      }

      .card-info {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 8px;

        .card-title .name {
          font-size: 14px;
          font-weight: 700;
          color: #313238;
        }

        .card-title .sub-name {
          display: block;
          margin-top: 4px;
          font-size: 14px;
          line-height: 18px;
          color: #979ba5;
        }

        .card-api-push-info {
          display: flex;
          gap: 8px;

          .field-token,
          .field-endpoint {
            display: flex;
            min-width: 400px;
            padding: 6px 12px;
            font-size: 12px;
            color: #63656e;
            background-color: #f5f7fa;
            align-items: center;
            flex-wrap: wrap;
            gap: 6px;

            .encryption {
              display: inline-block;
              width: 5px;
              height: 5px;
              margin-right: 5px;
              cursor: pointer;
              background-color: #63656e;
              border-radius: 50%;
            }

            .operation-icon {
              display: none;
              padding: 0 12px;
              font-size: 14px;
              color: #3a84ff;
              cursor: pointer;

              .ml12 {
                margin-left: 12px;
              }
            }

            .field-value {
              display: inline-block;
              width: 251px;
              overflow: hidden;
              text-overflow: ellipsis;
            }

            &:hover {
              .operation-icon {
                display: inline-block;
              }
            }
          }

          .field-endpoint {
            flex: 1;
          }
        }
      }
    }

    .card-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;

      .card-status {
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .status-text {
        font-size: 12px;

        /* color: #63656e; */
      }

      .status-success {
        color: #2caf5e;
      }

      .status-warning {
        color: #f59500;
      }

      .status-danger {
        color: #ea3636;
      }

      .card-extra {
        display: flex;
        align-items: center;
        gap: 8px;
        color: #63656e;
      }

      .latest-label {
        font-size: 12px;
      }

      .pending-label {
        font-size: 12px;
        color: #63656e;
      }
    }

    .collector-item-operation {
      position: absolute;
      top: 8px;
      right: 0;
      display: none;
    }

    &:hover {
      .collector-item-operation {
        display: block;
      }
    }
  }
}
</style>


