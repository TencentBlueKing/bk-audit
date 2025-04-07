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
  <bk-loading :loading="loading">
    <div class="system-detail-box">
      <img
        class="app-logo"
        :src="data.logo_url">
      <div class="system-base-box">
        <div class="system-name">
          {{ data.name }}
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
      <div class="item">
        <div class="item-title">
          {{ t('系统ID') }}
        </div>
        <div>
          {{ data.system_id }}
        </div>
      </div>
      <div class="item">
        <div class="item-title">
          {{ t('系统负责人') }}
        </div>
        <div>
          <edit-tag
            :data="data.managers"
            :max="3" />
        </div>
      </div>
      <div class="item">
        <div class="item-title">
          {{ t('系统来源') }}
        </div>
        <div>
          {{ GlobalChoices.meta_system_source_type.find(item => item.id === data.source_type)?.name || '--' }}
        </div>
      </div>
      <div class="item app-description">
        <div class="item-title">
          {{ t('系统描述') }}
        </div>
        <div class="description-value">
          {{ data.description || '--' }}
        </div>
      </div>
    </div>
  </bk-loading>
</template>
<script setup lang="ts">
  import type { Ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import MetaManageService from '@service/meta-manage';

  import SystemModel from '@model/meta/system';

  import useRequest from '@hooks/use-request';

  import EditTag from '@components/edit-box/tag.vue';

  interface Exposes {
    loading: Ref<boolean>
  }
  const { t } = useI18n();

  const route = useRoute();
  const {
    data,
    loading,
  } = useRequest(MetaManageService.fetchSystemDetail, {
    defaultParams: {
      id: route.params.id,
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

  defineExpose<Exposes>({
    loading,
  });

</script>
<style lang="postcss">
  .system-detail-box {
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

    .item {
      padding-left: 64px;
      font-size: 12px;
      line-height: 26px;
      color: #63656e;

      .item-title {
        color: #979ba5;
      }
    }

    .app-description {
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
  }
</style>
