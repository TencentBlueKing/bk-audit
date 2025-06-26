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
  <div class="system-detail-box">
    <img
      class="app-logo"
      :src="data.logo_url">
    <div class="system-base-box">
      <div class="system-name">
        {{ data.name }}
        <bk-tag :theme="data.system_status === 'normal' ? 'success' : 'warning'">
          {{ t(systemStatusText(data.system_status) || '') }}
        </bk-tag>
      </div>
      <div>
        <a
          v-if="data.system_url"
          class="system-site"
          :href="data.system_url"
          target="_blank">
          {{ data.system_url }}
        </a>
        <span v-else>--</span>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import MetaManageService from '@service/meta-manage';

  import SystemModel from '@model/meta/system';

  import useRequest from '@hooks/use-request';

  interface Exposes {
    loading: boolean
  }

  interface Props {
    data?: SystemModel;  // 改为可选属性
    id: string
  }

  const props = withDefaults(defineProps<Props>(), {
    id: '',
    data: undefined,  // 默认值设为undefined
  });
  const { t } = useI18n();

  const route = useRoute();

  const {
    data,
    loading,
  } = useRequest(MetaManageService.fetchSystemDetail, {
    defaultParams: {
      id: route.params.id || props.id,
    },
    defaultValue: new SystemModel(),
    manual: true,
  });

  const {
    data: GlobalChoices,
  } = useRequest(MetaManageService.fetchGlobalChoices, {
    defaultValue: {},
    manual: true,
  });

  const systemStatusText = (val: string) => {
    if (!GlobalChoices.value?.meta_system_status) return val;
    const statusItem = GlobalChoices.value.meta_system_status.find(item => item.id === val);
    return statusItem?.name || val; // 如果找不到对应状态，返回原值
  };

  defineExpose<Exposes>({
    loading: loading.value,  // 使用.value获取实际布尔值
  });

</script>
<style lang="postcss">
  .system-detail-box {
    position: relative;
    display: flex;
    padding: 24px;
    overflow: hidden;
    background-color: #fff;
    align-items: flex-start;

    .app-logo {
      flex: 0;
      width: 48px;
      height: 48px;
      margin-right: 12px;
    }

    .system-base-box {
      .system-name {
        font-size: 20px;
        font-weight: bold;
        line-height: 26px;
        color: #313238;
        word-break: keep-all;
      }

      .system-site {
        display: block;
        max-width: 350px;
        overflow: hidden;
        line-height: 26px;
        text-overflow: ellipsis;
        word-break: keep-all;
        white-space: nowrap;
      }
    }

    .system-delete {
      position: absolute;
      top: 24px;
      right: 24px;
      color: #c5c7cd;
      cursor: pointer;

      .bk-button-primary {
        background-color: red;
        border-color: red;
      }
    }
  }
</style>
