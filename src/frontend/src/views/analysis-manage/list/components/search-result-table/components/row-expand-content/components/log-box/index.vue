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
  <auth-button
    v-bk-tooltips="{
      disabled: data.extend_data !== '******',
      content: t('暂无查看权限')
    }"
    :action-id="sensitiveData ? 'access_audit_sensitive_info' :''"
    :permission="data.extend_data !== '******'"
    :resource="sensitiveData ? sensitiveData.id : ''"
    text
    theme="primary"
    @click="handleShowLog">
    <span>{{ t('完整日志') }}</span>
  </auth-button>
  <audit-sideslider
    v-model:is-show="isShow"
    class="analysis-log-dialog"
    :show-footer="false"
    show-header-slot
    :title="logType==='logWhole'? t('完整日志') : t('原始日志')"
    :width="640">
    <template #header>
      <div class="flex mr24">
        <div>{{ logType==='logWhole'? t('完整日志') : t('原始日志') }}</div>
        <div
          class="log-operation">
          <div class="log-tab">
            <div
              v-bk-tooltips="t('在来源系统上报的日志基础上，叠加了审计加工补充的数据')"
              class="log-tab-item"
              :class="{active: logType === 'logWhole'}"
              @click="handleLogChange('logWhole')">
              {{ t('完整日志') }}
            </div>
            <div
              v-bk-tooltips="t('来源系统上报时的日志数据原貌')"
              class="log-tab-item"
              :class="{
                active: logType === 'logOriginal'
              }"
              @click="handleLogChange('logOriginal')">
              {{ t('原始日志') }}
            </div>
          </div>
          <div
            class="cursor mr24"
            @click="handleCopyLog">
            <audit-icon
              style="color: #979ba5;"
              type="copy" />
            {{ t('复制日志') }}
          </div>
          <div>
            {{ t('深色模式') }}
            <bk-switcher
              size="small"
              theme="primary"
              :value="theme === 'vs-dark'"
              @change="handleChangeTheme" />
          </div>
        </div>
      </div>
    </template>
    <render-log
      ref="renderLogRef"
      :data="jsonData"
      :descriptions="descriptions"
      :theme="theme" />
  </audit-sideslider>
</template>
<script setup lang="ts">
  import {
    computed,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';

  import useRequest from '@hooks/use-request';

  import {
    execCopy,
  } from '@utils/assist';

  import RenderLog from './components/render-log.vue';

  interface Props{
    data: Record<string, any>;
  }
  interface Descriptions {
    [key:string]: string
  }
  const props = defineProps<Props>();

  const { t } = useI18n();

  const renderLogRef = ref();
  const isShow = ref(false);
  const theme = ref('vs-dark');

  const logType = ref('logWhole');
  // eslint-disable-next-line vue/no-setup-props-destructure, @typescript-eslint/no-unused-vars
  const { __table_row_index, __$uuid, __row_expand, ...dataNew } = props.data;
  const jsonData = computed(() => (logType.value === 'logWhole' ? dataNew : props.data.log));

  const descriptions = computed(() => {
    const descriptionObj = {} as Descriptions;
    sourceList.value.forEach((item) => {
      descriptionObj[item.field_name] = item.description;
    });
    return descriptionObj;
  });

  /**
   * 获取全量字段
   */
  const {
    data: sourceList,
    run: fetchStandardField,
  } = useRequest(MetaManageService.fetchStandardField, {
    defaultParams: {
      is_etl: false,
    },
    defaultValue: [],
  });
  // 获取敏感信息列表
  const {
    data: sensitiveData,
    run: fetchSensitiveList,
  } = useRequest(MetaManageService.fetchSensitiveList, {
    defaultValue: null,
  });

  const handleShowLog = () => {
    isShow.value = true;
    fetchStandardField({
      is_etl: false,
    });
  };

  const handleCopyLog = () => {
    execCopy(renderLogRef.value.getValue(), t('复制成功'));
  };

  const handleLogChange = (value: string) => {
    logType.value = value;
  };
  const handleChangeTheme = (value: boolean) => {
    theme.value = value ? 'vs-dark' : 'vs';
  };

  // eslint-disable-next-line vue/no-setup-props-destructure
  watch(props.data, () => {
    if (!sensitiveData.value && props.data.extend_data === '******') {
      const { system_id: systemId, action_id: actionId } = props.data;
      fetchSensitiveList({
        system_id: systemId,
        resource_type: 'sensitive_action_object',
        resource_id: actionId,
      });
    }
  }, {
    immediate: true,
  });
</script>
<style lang="postcss">
  .analysis-log-dialog {
    .log-operation {
      display: flex;
      margin-left: auto;
      font-size: 12px;
      color: #63656e;
    }

    .log-tab {
      display: flex;
      height: 32px;
      padding: 3px;
      margin: auto;
      margin-right: 32px;
      font-size: 12px;
      color: #63656e;
      background: #f0f1f5;
      border-radius: 2px;
    }

    .log-tab-item {
      display: flex;
      height: 26px;
      padding: 0 8px;
      cursor: pointer;
      border-radius: 2px;
      align-items: center;
      justify-content: center;
      transition: all 0.15s;

      &.active {
        color: #3a84ff;
        background: #fff;
        box-shadow: 0 1px 2px 0 rgb(0 0 0 / 8%);
      }
    }
  }
</style>
