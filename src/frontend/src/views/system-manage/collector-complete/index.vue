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
  <div class="collector-complete-page">
    <bk-loading :loading="loading">
      <audit-icon
        style="font-size: 64px;"
        svg
        type="completed" />
      <div style="margin-top: 36px; font-size: 24px; line-height: 32px;color: #313238;">
        {{ t('采集配置创建完成') }}
      </div>
      <div
        v-if="!environment"
        class="result-text">
        <div>
          <span> {{ t('本次共下发') }}</span>
          <router-link
            class="number"
            :to="{
              name: 'collectorCreate',
              params: {
                systemId
              },
              query: {
                step: 2,
                collector_config_id: collectorConfigId,
                task_id_list: taskIdList
              }
            }">
            {{ collectorTaskStatus.allList.length }}
          </router-link>
          <span> {{ t('台主机') }}</span>
        </div>
        <div v-if="collectorTaskStatus.successList.length > 0">
          <span>，成功</span>
          <router-link
            class="number"
            style="color: #2dcb56;"
            :to="{
              name: 'collectorCreate',
              params: {
                systemId
              },
              query: {
                step: 2,
                collector_config_id: collectorConfigId,
                task_id_list: taskIdList,
                status: 'successed'
              }
            }">
            {{ collectorTaskStatus.successList.length }}
          </router-link>
          <span>{{ t('台主机') }}</span>
        </div>
        <div v-if="collectorTaskStatus.failedList.length">
          <span>，失败</span>
          <router-link
            class="number"
            style="color: #ea3636;"
            :to="{
              name: 'collectorCreate',
              params: {
                systemId
              },
              query: {
                step: 2,
                collector_config_id: collectorConfigId,
                task_id_list: taskIdList,
                status: 'failed'
              }
            }">
            {{ collectorTaskStatus.failedList.length }}
          </router-link>
          <span> {{ t('台主机') }}</span>
        </div>
      </div>
      <div>
        <router-link
          class="go-app-detail"
          :to="{
            name: 'systemDetail',
            params: {
              id: systemId
            },
            query: {
              contentType: 'dataReport',
            },
          }">
          {{ t('返回系统详情') }}
        </router-link>
      </div>
    </bk-loading>
  </div>
</template>
<script setup lang="ts">
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import CollectorManageService from '@service/collector-manage';

  import CollectorTaskStatusModel from '@model/collector/task-status';

  import useRequest from '@hooks/use-request';
  import useUrlSearch from '@hooks/use-url-search';

  const { t } = useI18n();
  const { searchParams } = useUrlSearch();
  const environment = searchParams.get('environment');
  const route = useRoute();

  const {
    systemId,
    collectorConfigId,
    taskIdList,
  } = route.params;

  const {
    loading,
    data: collectorTaskStatus,
    run: handleFetchCollectorTaskStatus,
  } = useRequest(CollectorManageService.fetchCollectorTaskStatus, {
    defaultParams: {
      collector_config_id: collectorConfigId,
      task_id_list: taskIdList,
    },
    defaultValue: new CollectorTaskStatusModel(),
  });

  if (taskIdList) {
    handleFetchCollectorTaskStatus({
      collector_config_id: collectorConfigId,
      task_id_list: taskIdList,
    });
  }
</script>
<style lang="postcss">
  .collector-complete-page {
    padding-top: 148px;
    font-size: 14px;
    line-height: 22px;
    color: #63656e;
    text-align: center;

    .result-text {
      display: flex;
      justify-content: center;
      margin-top: 16px;
    }

    .go-app-detail {
      display: inline-flex;
      width: 120px;
      height: 32px;
      margin-top: 24px;
      font-size: 14px;
      color: #fff;
      cursor: pointer;
      background: #3a84ff;
      border-radius: 2px;
      justify-content: center;
      align-items: center;
    }
  }
</style>
