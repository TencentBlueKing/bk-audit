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
  <smart-action
    class="bkbase-step"
    :offset-target="getSmartActionOffsetTarget">
    <div class="bkbase-step-content">
      <!-- 完成提示区域 -->
      <div class="complete-section">
        <audit-icon
          class="complete-icon"
          svg
          type="completed" />
        <div class="complete-title">
          {{ t('采集配置创建完成') }}
        </div>
        <div class="complete-actions">
          <bk-button
            theme="primary"
            @click="handleBackToList">
            {{ t('返回上报列表') }}
          </bk-button>
          <bk-button
            class="ml8"
            @click="handleViewDetail">
            {{ t('查看数据详情') }}
          </bk-button>
        </div>
      </div>

      <!-- 数据验证部分 -->
      <div class="validation-section">
        <div class="validation-header">
          <div class="validation-title">
            {{ t('数据验证 (可选)') }}
          </div>
          <div class="validation-line" />
          <div class="validation-desc">
            {{ t('验证上报数据是否已上传和是否正确,可先"完成"后再次进入任务进行验证') }}
          </div>
        </div>
        <bk-button
          class="validation-btn"
          outline
          theme="primary"
          @click="handleOneClickValidation">
          {{ t('一键验证') }}
        </bk-button>
      </div>

      <div class="validation-section">
        <div class="validation-header">
          <div class="validation-title">
            {{ t('验证结果') }}
          </div>
        </div>
        <span
          class="steps-vertical">
          <span
            v-for="item in steps"
            :key="item.title"
            class="step-item">
            <audit-icon
              class="step-item-icon"
              :class="{ 'step-item-icon-loading': item.index === 0 && step1Loading }"
              svg
              :type="item.index === 0 && step1Loading ? 'loading' : item.icon" />
            <span class="step-item-title">
              {{ item.title }}
              <div
                v-if="item.description"
                class="step-item-description">
                {{ item.description }}
              </div>
            </span>
          </span>
        </span>
      </div>
    </div>

    <div class="validation-section">
      <div class="validation-header">
        <div class="validation-title">
          {{ t('详细结果') }}
        </div>
      </div>
      <bk-table
        :border="['outer', 'row']"
        :columns="tableColumn"
        :data="tableData"
        :max-height="530">
        <template #empty>
          <bk-exception
            scene="part"
            style="padding-top: 130px;color: #63656e;"
            type="empty">
            {{ t('暂无数据') }}
          </bk-exception>
        </template>
      </bk-table>
    </div>

    <!-- 侧边栏 - BKBase 数据源 -->
    <bk-sideslider
      v-if="dataSourceType === 'bkbase'"
      v-model:isShow="isShowDetail"
      :title="t('查看详情')"
      :width="960">
      <template #default>
        <div class="check-detail-content">
          <!-- 基本信息 -->
          <data-id-edit-info
            :data="detailDataForData"
            width="50%" />
        </div>
      </template>
    </bk-sideslider>

    <!-- 侧边栏 - Collector 数据源 -->
    <bk-sideslider
      v-if="dataSourceType === 'collector'"
      v-model:isShow="isShowDetail"
      :title="t('节点管理特殊采集任务')"
      :width="960">
      <template #default>
        <div class="check-detail-content">
          <!-- 基本信息 -->
          <collector-edit-info
            :data="detailDataForCollector"
            :status="collectorTaskStatus"
            width="50%"
            @change="handleType" />
          <!-- 采集状态 -->
          <delivery-info
            :data="detailDataForCollector"
            :environment="environment"
            @get-status="handleGetCollectorTaskStatus" />
        </div>
      </template>
    </bk-sideslider>

    <!-- 侧边栏 - API Push 数据源 -->
    <bk-sideslider
      v-if="dataSourceType === 'api'"
      v-model:isShow="isShowDetail"
      :title="t('日志采集详情')"
      :width="960">
      <template #default>
        <div class="check-detail-content">
          <api-push-edit-info :data="detailDataForApiPush" />
        </div>
      </template>
    </bk-sideslider>
  </smart-action>
</template>

<script setup lang="tsx">
  import type { Column } from 'bkui-vue/lib/table/props';
  import {
    computed,
    nextTick,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import CollectorManageService from '@service/collector-manage';
  import DataIdManageService from '@service/dataid-manage';

  import CollectorDetailModel from '@model/collector/collector-detail';
  import type CollectorTailLogModel from '@model/collector/collector-tail-log';
  import DataIdDetailModel from '@model/dataid/dataid-detail';

  import useRequest from '@hooks/use-request';
  import useUrlSearch from '@hooks/use-url-search';

  import {
    execCopy,
  } from '@utils/assist';

  import type DataIdTopicLogModel from '@/domain/model/dataid/dataid-tail';
  import ApiPushEditInfo from '@/views/system-manage/detail/components/data-report/components/api-push-render-operation/edit-info/index.vue';
  import DataIdEditInfo from '@/views/system-manage/detail/components/data-report/components/dataid-render-operation/edit-info/index.vue';
  import DeliveryInfo from '@/views/system-manage/detail/components/data-report/components/render-operation/delivery-info/index.vue';
  import CollectorEditInfo from '@/views/system-manage/detail/components/data-report/components/render-operation/edit-info/index.vue';

  const { t } = useI18n();
  const route = useRoute();
  const router = useRouter();
  const { searchParams } = useUrlSearch();

  // 判断数据源类型
  const dataSourceType = computed(() => {
    // API Push: 通过 route.name 判断
    if (route.name === 'logApiPushCreate' || route.name === 'logApiPushEdit') {
      return 'api';
    }
    // BKBase: 通过 bk_data_id 参数判断
    if (searchParams.get('bk_data_id') || route.params.bkDataId) {
      return 'bkbase';
    }
    // Collector: 通过 collector_config_id 参数判断
    if (searchParams.get('collector_config_id')) {
      return 'collector';
    }
    return 'api'; // 默认
  });

  // 获取对应的 ID
  const dataId = computed(() => {
    if (dataSourceType.value === 'api') {
      return route.params.systemId;
    }
    if (dataSourceType.value === 'bkbase') {
      return searchParams.get('bk_data_id') || route.params.bkDataId;
    }
    if (dataSourceType.value === 'collector') {
      return searchParams.get('collector_config_id');
    }
    return null;
  });

  const getSmartActionOffsetTarget = () => document.querySelector('.bkbase-step-content') as HTMLElement | null;

  const poverWidth = ref<number>();
  const tableData = ref<(CollectorTailLogModel | DataIdTopicLogModel)[]>([]);

  const steps = ref([
    {
      index: 0,
      title: t('验证上报是否成功'),
      description: '',
      icon: 'play-fill',
    },
    {
      index: 1,
      title: t('验证字段清洗是否异常'),
      description: '',
      icon: 'play-fill',
    },
  ]);

  // 表格列配置 - 根据数据源类型动态生成
  const tableColumn = computed(() => {
    if (dataSourceType.value === 'bkbase') {
      // BKBase 数据源
      return [
        {
          label: () => t('上报信息'),
          width: '180px',
          render: ({ data }: {data: DataIdTopicLogModel}) => (
            <span style="display:block; font-size:12px; font-weight:bold; color:#63656E;">
              {data.topic}
            </span>
          ),
        },
        {
          label: () => t('原始日志'),
          render: ({ data }: {data:DataIdTopicLogModel}) => (
            <bk-popover
              placement="top-end"
              width={poverWidth.value || 1200}
              id="log-cell">
              {{
                default: () => (
                  <span class="log-cell" style={{  width: poverWidth.value }}>
                    {data.value}
                  </span>
                ),
                content: () => (
                  <div  style={{  width: poverWidth.value || 1200, 'word-break': 'break-all' }}>
                    {data.value}
                  </div>
                ),
              }}
            </bk-popover>
            ),
        },
        {
          label: () => t('操作'),
          width: 60,
          render: ({ data }: {data: DataIdTopicLogModel}) => (
            <span
              style="cursor: pointer;width: 25px; height:25px;display:inline-block"
              onClick={() => handleCopyData(data)}>
              <audit-icon
                v-bk-tooltips={t('复制')}
                type="copy"/>
            </span>
          ),
        },
      ] as Column[];
    }
    // API Push 和 Collector 数据源
    return [
      {
        label: () => t('上报信息'),
        width: '180px',
        render: ({ data }: {data: CollectorTailLogModel}) => (
          <span style="display:block; font-size:12px; font-weight:bold; color:#63656E;">
            {data.origin.datetime}
          </span>
        ),
      },
      {
        label: () => t('原始日志'),
        render: ({ data }: {data: CollectorTailLogModel}) => (
          <bk-popover
            placement="top-end"
            width={ poverWidth.value || 1200 }
            id="log-cell">
            {{
              default: () => (
                <span class="log-cell" style={{  width: poverWidth.value }}>
                  {data.originData}
                </span>
              ),
              content: () => (
                <div  style={{  width: poverWidth.value || 1200, 'word-break': 'break-all' }}>
                  {data.originData}
                </div>
              ),
            }}
          </bk-popover>
          ),
      },
      {
        label: () => t('操作'),
        width: 60,
        render: ({ data }: {data: CollectorTailLogModel}) => (
          <span
            style="cursor: pointer;width: 25px; height:25px;display:inline-block"
            onClick={() => handleCopyData(data)}>
            <audit-icon
              v-bk-tooltips={t('复制')}
              type="copy"/>
          </span>
        ),
      },
    ] as Column[];
  });

  const handleBackToList = () => {
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

  // 统一的成功处理函数
  const handleFetchSuccess = (data: any[]) => {
    // 更新表格数据
    tableData.value = Array.isArray(data) ? data : [];
    const dataLength = Array.isArray(data) ? data.length : 0;

    // 如果数据长度为 0，视为异常
    if (dataLength === 0) {
      steps.value[0].icon = 'cuo';
      steps.value[0].description = t('数据上报失败，暂未获取到最新数据；请重新点击检测或检查数据上报链路');
      return;
    }

    // 重置错误状态
    step1Error.value = false;
    // 成功后更新第一个步骤的图标为 completed
    steps.value[0].icon = 'completed';
    // 更新成功描述，包含数据长度
    steps.value[0].description = t('数据上报成功，已取 {count} 条数据上报，见下方详细结果', { count: dataLength });
    // 计算 popover 宽度
    nextTick(() => {
      const node = document.getElementById('log-cell')?.parentElement;
      poverWidth.value = node ? node.clientWidth - 30 : 1200;
    });
  };

  // BKBase 数据源
  const {
    loading: bkbaseLoading,
    error: bkbaseError,
    run: fetchDataIdTail,
  } = useRequest(DataIdManageService.fetchTail, {
    defaultValue: [],
    onSuccess: handleFetchSuccess,
  });

  // Collector 数据源
  const {
    loading: collectorLoading,
    error: collectorError,
    run: fetchCollectorTail,
  } = useRequest(CollectorManageService.fetchTailLog, {
    defaultValue: [],
    onSuccess: handleFetchSuccess,
  });

  // API Push 数据源
  const {
    loading: apiLoading,
    error: apiError,
    run: fetchApiPushTail,
  } = useRequest(CollectorManageService.fetchApiPushTailLog, {
    defaultValue: [],
    onSuccess: handleFetchSuccess,
  });

  // 统一的 loading 和 error 状态
  const step1Loading = computed(() => {
    if (dataSourceType.value === 'bkbase') return bkbaseLoading.value;
    if (dataSourceType.value === 'collector') return collectorLoading.value;
    return apiLoading.value;
  });

  const step1Error = computed({
    get: () => {
      if (dataSourceType.value === 'bkbase') return bkbaseError.value;
      if (dataSourceType.value === 'collector') return collectorError.value;
      return apiError.value;
    },
    set: (value) => {
      if (dataSourceType.value === 'bkbase') bkbaseError.value = value;
      else if (dataSourceType.value === 'collector') collectorError.value = value;
      else apiError.value = value;
    },
  });

  const handleOneClickValidation = () => {
    // 重置错误状态
    step1Error.value = false;
    // 清空描述
    steps.value[0].description = '';

    // 根据数据源类型调用不同的接口
    if (dataSourceType.value === 'bkbase') {
      fetchDataIdTail({
        bk_data_id: dataId.value,
      });
    } else if (dataSourceType.value === 'collector') {
      fetchCollectorTail({
        collector_config_id: dataId.value,
      });
    } else if (dataSourceType.value === 'api') {
      fetchApiPushTail({
        system_id: dataId.value,
      });
    }
  };

  const isShowDetail = ref(false);
  const detailDataForCollector = ref<any>(new CollectorDetailModel());
  const detailDataForData = ref<any>(new DataIdDetailModel());
  const detailDataForApiPush = ref<any>({ token: '', hosts: [], collector_config_name: '' });
  const collectorTaskStatus = ref<any>({});
  const environment = ref('');

  // 获取 Collector 详情
  const {
    run: fetchCollectorDetail,
  } = useRequest(CollectorManageService.fetchCollectorsById, {
    defaultValue: new CollectorDetailModel(),
    onSuccess(data) {
      detailDataForCollector.value = data;
      environment.value = data.environment || 'linux';
      // 接口完成后打开侧边栏
      isShowDetail.value = true;
    },
  });

  // 获取 DataId 详情
  const {
    run: fetchDataIdDetail,
  } = useRequest(DataIdManageService.fecthDetail, {
    defaultValue: new DataIdDetailModel(),
    onSuccess(data) {
      console.log('data', data);
      detailDataForData.value = data;
      // 接口完成后打开侧边栏
      isShowDetail.value = true;
    },
  });

  // 获取 API Push Token
  const {
    run: fetchApiPushToken,
  } = useRequest(CollectorManageService.fetchApiPush, {
    defaultValue: {},
  });

  // 获取 API Push Hosts
  const {
    run: fetchApiPushHost,
  } = useRequest(CollectorManageService.fetchApiPushHost, {
    defaultValue: { enabled: false, hosts: [] },
    onSuccess(hostData) {
      fetchApiPushToken({
        system_id: dataId.value,
      }).then((tokenData: any) => {
        detailDataForApiPush.value = {
          token: tokenData.token,
          hosts: hostData.hosts,
          collector_config_name: tokenData.collector_config_name,
        };
        // 接口完成后打开侧边栏
        isShowDetail.value = true;
      });
    },
  });

  const handleViewDetail = () => {
    // 根据数据源类型获取详情数据，接口完成后会自动打开侧边栏
    if (dataSourceType.value === 'collector') {
      fetchCollectorDetail({
        id: dataId.value,
      });
    } else if (dataSourceType.value === 'bkbase') {
      fetchDataIdDetail({
        bk_data_id: dataId.value,
      });
    } else if (dataSourceType.value === 'api') {
      fetchApiPushHost({
        system_id: dataId.value,
      });
    }
  };

  const handleType = (value: string) => {
    environment.value = value;
  };

  const handleGetCollectorTaskStatus = (value: any) => {
    collectorTaskStatus.value = value;
  };

  const handleCopyData = (data: CollectorTailLogModel | DataIdTopicLogModel) => {
    if ('value' in data) {
      // BKBase 数据
      execCopy(data.value, t('复制成功'));
    } else if ('originData' in data) {
      // Collector/API 数据
      execCopy(data.originData, t('复制成功'));
    }
  };

  // 监听各个数据源的错误状态
  watch([bkbaseError, collectorError, apiError], ([bkErr, collErr, apiErr]) => {
    const isError = (dataSourceType.value === 'bkbase' && bkErr)
      || (dataSourceType.value === 'collector' && collErr)
      || (dataSourceType.value === 'api' && apiErr);

    if (isError) {
      // 失败后更新第一个步骤的图标为 cuo
      steps.value[0].icon = 'cuo';
      // 更新错误描述
      steps.value[0].description = t('数据上报失败，暂未获取到最新数据；请重新点击检测或检查数据上报链路');
    }
  });
</script>

<style scoped lang="postcss">
.bkbase-step {
  height: 100%;
}

.bkbase-step-content {
  min-height: 400px;
  padding: 40px 0;
  padding-right: 20px;
}

.complete-section {
  display: flex;
  flex-direction: column;
  align-items: center;

  .complete-icon {
    font-size: 64px;
    color: #2dcb56;
  }

  .complete-title {
    margin-top: 36px;
    font-size: 24px;
    font-weight: 600;
    line-height: 32px;
    color: #313238;
  }

  .complete-actions {
    display: flex;
    gap: 8px;
    margin-top: 32px;
  }
}

.check-detail-content {
  height: calc(100vh - 114px);
  padding: 22px 40px;
}

.validation-section {
  padding: 32px;
  margin-top: 24px;
  border-top: 1px solid #e5e5e5;

  .validation-header {
    display: flex;
    align-items: center;
    margin-bottom: 24px;

    .validation-line {
      width: 1px;
      height: 12px;
      margin: 0 10px;
      background: #979ba5;
    }

    .validation-title {
      font-size: 14px;
      font-weight: 600;
      color: #313238;
    }

    .validation-desc {
      font-size: 12px;
      color: #979ba5;
      vertical-align: middle;
    }
  }

  .steps-vertical {
    display: inline-flex;
    height: 150px;
    flex-direction: column;

    .step-item {
      position: relative;
      display: inline-flex;
      height: 44px;
      padding: 2px 26px 2px 6px;
      margin-bottom: 32px;
      background-color: #f5f7fa;
      border-radius: 24px;
      align-items: center;

      &:not(:last-child)::after {
        position: absolute;
        top: 100%;
        left: 20px;
        width: 1px;
        height: 32px;
        border-left: 1.5px dashed #dcdee5;
        content: '';
      }

      .step-item-icon {
        margin-right: 10px;
        font-size: 32px;
        color: currentcolor;

        &.step-item-icon-loading {
          color: #3a84ff;
        }
      }

      .step-item-title {
        font-size: 12px;
        font-weight: 700;
        line-height: 16px;
        color: #4d4f56;

        .step-item-description {
          margin-top: 4px;
          font-size: 12px;
          font-weight: 400;
        }
      }
    }
  }
}
</style>
