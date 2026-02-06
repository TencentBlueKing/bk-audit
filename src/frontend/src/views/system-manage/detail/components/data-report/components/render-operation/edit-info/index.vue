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
  <div class="log-collection-detail-box">
    <p class="title">
      {{ t('基本信息') }}
    </p>
    <bk-loading :loading="loading">
      <div class="base-content">
        <render-info-block>
          <render-info-item :label="t('任务名称')">
            {{ detailData.collector_config_name }}
          </render-info-item>
          <render-info-item :label="t('更新人')">
            {{ detailData.updated_by }}
          </render-info-item>
        </render-info-block>
        <render-info-block>
          <render-info-item :label="t('采集状态')">
            <audit-icon
              :class="{
                'rotate-loading': type ==='running'
              }"
              svg
              :type="detailData.Icon[type]" />
            {{ detailData.statusText[type] }}
          </render-info-item>
          <render-info-item :label="t('更新时间')">
            {{ detailData.updated_at }}
          </render-info-item>
        </render-info-block>
        <render-info-block>
          <render-info-item :label="t('数据 ID')">
            {{ detailData.bk_data_id }}
          </render-info-item>
          <render-info-item :label="t('创建人')">
            {{ detailData.created_by }}
          </render-info-item>
        </render-info-block>
        <render-info-block>
          <render-info-item :label="t('日志路径')">
            <template v-if="detailData.params?.paths">
              <div
                v-for="(item, index) in detailData.params.paths"
                :key="index"
                style="line-height: 20px;">
                {{ item }}
              </div>
            </template>
          </render-info-item>
          <render-info-item :label="t('创建时间')">
            {{ detailData.created_at }}
          </render-info-item>
        </render-info-block>
        <render-info-block>
          <render-info-item :label="t('日志字符集')">
            {{ detailData.data_encoding }}
          </render-info-item>
        </render-info-block>
        <render-info-block>
          <render-info-item
            v-if="detailData.params.conditions.type === 'match'"
            :label="t('过滤内容')">
            <template v-if="detailData.params.conditions.match_content">
              <span>{{ t('字符串过滤') }}:
                {{ detailData.params.conditions.match_content }}({{ detailData.params.conditions.match_type }})
              </span>
            </template>
            <span v-else>
              --
            </span>
          </render-info-item>
          <render-info-item
            v-if="detailData.params.conditions.type === 'separator'"
            :label="t('过滤内容')">
            {{ t('分隔符过滤') }}: {{ detailData.params.conditions.separator }}
          </render-info-item>
          <render-info-item
            v-if="detailData.params.conditions.type === 'separator'"
            :label="t('过滤条件')">
            <template
              v-for="(item, index) in detailData.params.conditions.separator_filters"
              :key="index">
              <span
                class="logic-expression">
                第{{ item.fieldindex }}列 {{ item.op }} {{ item.word }}
              </span>
              <span class="logic-op">{{ item.logic_op }}</span>
            </template>
          </render-info-item>
        </render-info-block>
      </div>
    </bk-loading>
    <p
      class="title"
      style="margin-top: 24px;">
      {{ t('日志记录信息') }}
    </p>
    <bk-loading :loading="loading">
      <div class="log-record-content">
        <render-info-block>
          <render-info-item :label="t('日志记录方式')">
            {{ detailData.record_log_type }}
          </render-info-item>
        </render-info-block>
        <render-info-block>
          <render-info-item :label="t('SDK类型')">
            <a
              v-if="detailData.select_sdk_type"
              :href="selectedSdkUrl"
              target="_blank">{{ selectedSdkUrl }}</a>
            <span v-else>
              --
            </span>
          </render-info-item>
        </render-info-block>
        <render-info-block>
          <render-info-item :label="t('上报日志须知')">
            <div>
              <div
                :label="Boolean(true)">
                {{ t('我已阅读') }}
                <a
                  :href="configData.audit_doc_config?.audit_access_guide"
                  target="_blank">{{ t('《审计中心接入要求》') }}</a>
              </div>
              <div
                :label="Boolean(true)">
                {{ t('我已了解') }}
                <a
                  :href="configData.audit_doc_config?.audit_operation_log_record_standards"
                  target="_blank">{{ t('《审计中心操作日志记录标准》') }}</a>
              </div>
            </div>
          </render-info-item>
        </render-info-block>
      </div>
    </bk-loading>
  </div>
</template>
<script setup lang="ts">

  import {
    computed,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import CollectorManageService from '@service/collector-manage';
  import RootManageService from '@service/root-manage';

  import type CollectorModel from '@model/collector/collector';
  import CollectorDetailModel from '@model/collector/collector-detail';
  import type Content from '@model/collector/task-status';
  import ConfigModel from '@model/root/config';

  import useRequest from '@hooks/use-request';

  import RenderInfoBlock from './components/render-info-block.vue';
  import RenderInfoItem from './components/render-info-item.vue';

  interface Props {
    data: CollectorModel;
    status: Content|undefined;
  }
  interface Emits{
    (e: 'change', value: string): void
  }
  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  const type = ref<string>('success');
  const selectSdkTypeList = ref([
    {
      label: 'PYTHON_SDK',
      name: 'Python SDK',
      url: 'https://github.com/TencentBlueKing/bk-audit-python-sdk',
    },
    {
      label: 'JAVA_SDK',
      name: 'Java SDK',
      url: 'https://github.com/TencentBlueKing/bk-audit-java-sdk',
    },
    {
      label: 'GO_SDK',
      name: 'Go SDK',
      url: 'https://github.com/TencentBlueKing/bk-audit-go-sdk',
    }]);

  // 根据选中的 SDK 类型获取对应的 URL
  const selectedSdkUrl = computed(() => {
    const selectedSdk = selectSdkTypeList.value.find(item => item.label === detailData.value.select_sdk_type);
    return selectedSdk?.url || 'https://github.com/TencentBlueKing/bk-audit-sdk';
  });

  const {
    data: configData,
  } =  useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
  });

  const {
    loading,
    data: detailData,
  // eslint-disable-next-line vue/no-setup-props-destructure
  } = useRequest(CollectorManageService.fetchCollectorsById, {
    defaultParams: {
      id: props.data.collector_config_id,
    },
    defaultValue: new CollectorDetailModel(),
    manual: true,
    onSuccess: (data: CollectorDetailModel) => {
      emits('change', data.environment);
    },
  });
  watch(() => props.status, (value) => {
    if (value) {
      if (value.runningList.length) {
        type.value = 'running';
        return;
      } if (value.failedList.length) {
        type.value = 'failed';
        return;
      } if (value.successList.length) {
        type.value = 'success';
        return;
      }
      type.value = 'unknown';
    }
  });
</script>
<style lang="postcss" scoped>
  .log-collection-detail-box {
    margin-bottom: 24px;

    .log-record-content {
      :deep(.render-info-item) {
        flex: 1;
      }
    }

    .title {
      padding-bottom: 16px;
      font-size: 14px;
      font-weight: bold;
      color: #313238;
    }

    .logic-expression {
      display: inline-block;
      padding: 0 8px;
      line-height: 22px;
      background: #f0f1f5;
      border-radius: 2px;
    }

    .logic-op {
      display: inline-block;
      padding: 0 8px;
      margin: 0 4px;
      line-height: 22px;
      color: #3a84ff;
      background: #edf4ff;
      border-radius: 2px;
    }

    .logic-op:last-child {
      display: none;
    }
  }
</style>
