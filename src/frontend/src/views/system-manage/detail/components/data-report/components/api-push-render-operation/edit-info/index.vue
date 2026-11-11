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
    <div class="base-content">
      <render-info-block>
        <render-info-item :label="t('采集方式')">
          API PUSH {{ t('接入') }}
        </render-info-item>
      </render-info-block>
      <render-info-block>
        <render-info-item :label="t('认证授权')">
          <div class="auth-wrapper">
            <div class="auth-field">
              <span class="auth-label">Token：</span>
              <template v-if="isHide">
                <span class="auth-value">{{ data.token }}</span>
              </template>
              <div v-else>
                <span
                  v-for="i in 7"
                  :key="i"
                  class="encryption-dot" />
              </div>
              <div class="auth-icons">
                <audit-icon
                  v-bk-tooltips="t(isHide ? '隐藏' : '查看')"
                  :type="isHide ? 'view' : 'hide'"
                  @click="isHide = !isHide" />
                <audit-icon
                  v-bk-tooltips="t('复制')"
                 
                  type="copy"
                  @click="execCopy(data.token, t('复制成功'))" style="margin-left: var(--bk-theme-space-8)" />
              </div>
            </div>
            <div class="auth-field">
              <span class="auth-label">EndPoint：</span>
              <div class="endpoint-list">
                <div
                  v-for="(host, index) in data.hosts"
                  :key="index"
                  class="endpoint-item">
                  {{ host }}
                </div>
              </div>
              <div class="auth-icons">
                <audit-icon
                  v-bk-tooltips="t('复制')"
                  class="copy-icon"
                  type="copy"
                  @click="execCopy(data.hosts.join('\n'), t('复制成功'))" />
              </div>
            </div>
          </div>
        </render-info-item>
      </render-info-block>
    </div>
    <p
      class="title"
      style="margin-top: 24px;">
      {{ t('日志记录信息') }}
    </p>
    <div class="log-record-content">
      <render-info-block>
        <render-info-item :label="t('SDK类型')">
          <a
            :href="selectedSdkUrl"
            target="_blank">{{ selectedSdkUrl }}</a>
        </render-info-item>
      </render-info-block>
      <render-info-block>
        <render-info-item :label="t('上报日志须知')">
          <div>
            <div>
              {{ t('我已阅读') }}
              <a
                :href="configData.audit_doc_config?.audit_access_guide"
                target="_blank">{{ t('《审计中心接入要求》') }}</a>
            </div>
            <div>
              {{ t('我已了解') }}
              <a
                :href="configData.audit_doc_config?.audit_operation_log_record_standards"
                target="_blank">{{ t('《审计中心操作日志记录标准》') }}</a>
            </div>
          </div>
        </render-info-item>
      </render-info-block>
    </div>
  </div>
</template>
<script setup lang="ts">
  import {
    computed,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import RootManageService from '@service/root-manage';

  import ConfigModel from '@model/root/config';

  import useRequest from '@hooks/use-request';

  import {
    execCopy,
  } from '@utils/assist';

  import RenderInfoBlock from '../../render-operation/edit-info/components/render-info-block.vue';
  import RenderInfoItem from '../../render-operation/edit-info/components/render-info-item.vue';

  interface Props {
    data: {
      token: string;
      hosts: string[];
      collector_config_name: string;
      select_sdk_type?: string;
    };
  }

  const props = defineProps<Props>();

  const { t } = useI18n();
  const isHide = ref(false);

  const selectSdkTypeList = [
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
    },
  ];

  // 根据选中的 SDK 类型获取对应的 URL
  const selectedSdkUrl = computed(() => {
    const selectedSdk = selectSdkTypeList.find(item => item.label === props.data.select_sdk_type);
    return selectedSdk?.url || 'https://github.com/TencentBlueKing/bk-audit-python-sdk';
  });

  const {
    data: configData,
  } = useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
  });
</script>
<style lang="postcss" scoped>
.log-collection-detail-box {
  margin-bottom: var(--bk-theme-space-24);

  :deep(.base-content) {
    .render-info-block {
      display: block;

      .auth-field {
        width: 600px;
      }
    }
  }

  .log-record-content {
    :deep(.render-info-item) {
      flex: 1;
    }
  }

  .title {
    padding-bottom: var(--bk-theme-space-16);
    font-size: 14px;
    font-weight: bold;
    color: var(--bk-theme-text-strong);
  }

  .auth-wrapper {
    .auth-field {
      display: flex;
      padding: var(--bk-theme-space-8) var(--bk-theme-space-12);
      margin-bottom: var(--bk-theme-space-12);
      font-size: 12px;
      background-color: var(--bk-theme-surface-subtle);
      border-radius: var(--bk-theme-tag-radius);
      align-items: center;

      &:last-child {
        margin-bottom: 0;
      }

      .auth-label {
        min-width: 70px;
        color: var(--bk-theme-text-default);
      }

      .auth-value {
        display: inline-block;
        width: 251px;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .encryption-dot {
        display: inline-block;
        width: 5px;
        height: 5px;
        margin-right: var(--bk-theme-space-4);
        background-color: var(--bk-theme-text-default);
        border-radius: 50%;
      }

      .auth-icons {
        display: none;
        gap: var(--bk-theme-space-8);
        margin-left: var(--bk-theme-space-12);
        font-size: 14px;
        color: var(--bk-theme-color-brand-2);
        cursor: pointer;
      }

      .endpoint-list {
        flex: 1;

        .endpoint-item {
          margin-bottom: var(--bk-theme-space-4);
          line-height: 20px;
          color: var(--bk-theme-text-strong);

          &:last-child {
            margin-bottom: 0;
          }
        }
      }

      &:hover {
        .auth-icons {
          display: flex;
        }
      }
    }
  }
}
</style>

