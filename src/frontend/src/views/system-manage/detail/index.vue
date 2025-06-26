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
    :loading="loading"
    :name="skeletonLoadingName">
    <div class="system-manage-detail-header">
      <system-info
        ref="appRef"
        :data="data" />
    </div>
    <bk-tab
      v-model:active="contentType"
      class="system-manage-detail-tab"
      type="card-grid"
      @change="handleChange">
      <bk-tab-panel
        v-for="(item, index) in panels"
        :key="index"
        :label="item.label"
        :name="item.name">
        <template #label>
          <div class="customize-label">
            <span
              v-if="(item.name === 'accessModel' && !data.model_count) ||
                (item.name === 'dataReport' && !data.collector_count)">
              <audit-icon
                v-bk-tooltips="{
                  content: item.name === 'accessModel' ? t('未完成权限模型配置，请尽快配置') : t('未完成日志数据上报，请尽快配置，避免影响后续策略使用'),
                }"
                style="font-size: 16px; color: #f59500;"
                type="alert" />
            </span>
            <div class="label-name">
              <div style="display: flex; align-items: center;">
                <h3>
                  {{ item.label }}
                </h3>
                <span
                  v-if="item.name !== 'basicInfo'"
                  v-bk-tooltips="{
                    content: t(`资源数据: ${data.resource_type_count}，操作数据: ${data.action_count}`),
                    disabled: item.name !== 'accessModel'
                  }"
                  class="count">{{ item.name === 'accessModel' ? data.model_count : data.collector_count }}</span>
              </div>
              <span class="label-describe">{{ item.describe }}</span>
            </div>
          </div>
        </template>
        <component
          :is="renderContentComponent"
          :can-edit-system="canEditSystem"
          :data="data"
          @update-system-detail="handleUpdateSystemDetail" />
      </bk-tab-panel>
    </bk-tab>
  </skeleton-loading>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import {
    computed,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import MetaManageService from '@service/meta-manage';

  import SystemModel from '@model/meta/system';

  import useEventBus from '@hooks/use-event-bus';
  import useRouterBack from '@hooks/use-router-back';
  import useUrlSearch from '@hooks/use-url-search';

  import AccessModel from './components/access-model/index.vue';
  import BasicInfo from './components/basic-info/index.vue';
  import DataReport from './components/data-report/index.vue';
  import SystemInfo from './components/system-info/index.vue';

  import useRequest from '@/hooks/use-request';

  const { t } = useI18n();
  const router = useRouter();
  const route = useRoute();
  const { emit } = useEventBus();

  const contentComponentMap = {
    basicInfo: BasicInfo,
    accessModel: AccessModel,
    dataReport: DataReport,
  };
  const panels = [
    {
      name: 'basicInfo',
      label: t('系统信息'),
      describe: t('产品创建审计中心的系统信息'),
    },
    {
      name: 'accessModel',
      label: t('权限模型'),
      describe: t('产品或研发注册资源与操作'),
    },
    {
      name: 'dataReport',
      label: t('日志上报'),
      describe: t('研发通过SDK上报日志数据'),

    },
  ];

  const contentType = ref<keyof typeof contentComponentMap>('basicInfo');
  const appRef = ref();

  const { getSearchParams, appendSearchParams } = useUrlSearch();
  const searchParams = getSearchParams();
  if (searchParams.contentType
    && _.has(contentComponentMap, searchParams.contentType)) {
    contentType.value = searchParams.contentType as keyof typeof contentComponentMap;
  }

  const renderContentComponent = computed(() => contentComponentMap[contentType.value]);

  const skeletonLoadingName = computed(() => (contentType.value === 'accessModel'
    ? 'systemDetailList'
    : 'systemDetail'));

  const canEditSystem = computed(() => data.value.source_type !== 'iam_v3' && data.value.source_type !== 'iam_v4');

  const handleChange = (value: 'basicInfo' | 'accessModel' | 'dataReport' | 'systemDiagnosis') => {
    appendSearchParams({
      contentType: value,
    });
  };

  const {
    data,
    loading,
    run: fetchSystemDetail,
  } = useRequest(MetaManageService.fetchSystemDetail, {
    defaultParams: {
      id: route.params.id,
    },
    defaultValue: new SystemModel(),
    manual: true,
    onSuccess: (result) => {
      emit('get-system-info', result);
    },
  });

  const handleUpdateSystemDetail = () => {
    fetchSystemDetail({
      id: route.params.id,
    });
  };

  useRouterBack(() => {
    router.push({
      name: 'systemList',
    });
  });
</script>
<style lang="postcss">
  .system-manage-detail-header {
    background: #fff;
    box-shadow: 0 2px 4px 0 rgb(25 25 41 / 5%);
  }

  .system-manage-detail-tab {
    margin-top: 16px;

    .bk-tab-header-item {
      height: 54px;

      .customize-label {
        display: flex;
        line-height: 22px;

        .label-name {
          margin-left: 5px;

          .count {
            width: 23px;
            height: 16px;
            margin-left: 5px;
            line-height: 16px;
            text-align: center;
            background: #f0f1f5;
            border-radius: 8px;
          }

          .label-describe {
            font-size: 12px;
            line-height: 16px;
            color: #c4c6cc;
          }
        }
      }
    }
  }
</style>
