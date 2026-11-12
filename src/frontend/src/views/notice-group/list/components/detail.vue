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
  <div class="notice-group-detail">
    <render-info-block>
      <render-info-item :label="t('通知组名称')">
        {{ data.group_name }}
      </render-info-item>
    </render-info-block>
    <render-info-block>
      <render-info-item :label="t('通知对象')">
        <span v-if="data.group_member.length">
          <span
            v-for="item in data.group_member"
            :key="item"
            class="receiver-item"> {{ item }}</span>
        </span>
        <span v-else>
          --
        </span>
      </render-info-item>
    </render-info-block>
    <render-info-block>
      <render-info-item
        :label="t('通知方式')">
        <bk-loading :loading="isLoading">
          <table
            class="notice-table-content"
            :loading="true">
            <tr class="notice-table-title">
              <td
                v-for="item in msgType"
                :key="item.id">
                {{ t(item.name) }}
              </td>
            </tr>
            <tr
              class="notice-table-value">
              <td
                v-for="msg in msgType"
                :key="msg.id">
                <audit-icon
                  class="check-icon"
                  :type="noticeWay.indexOf(msg.id) !== -1 ?'check-line':''" />
              </td>
            </tr>
          </table>
        </bk-loading>
      </render-info-item>
    </render-info-block>
    <render-info-block>
      <render-info-item :label="t('说明')">
        {{ data.description || '--' }}
      </render-info-item>
    </render-info-block>
  </div>
</template>
<script setup lang="ts">
  import {
    computed,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import NoticeManageService from '@service/notice-group';

  import type NoticeGroupsModel from '@model/notice/notice-group';

  import useRequest from '@hooks/use-request';

  import RenderInfoBlock from './render-info-block.vue';
  import RenderInfoItem from './render-info-item.vue';

  interface Props{
    data: NoticeGroupsModel
  }
  const props = defineProps<Props>();
  const { t } = useI18n();
  const noticeWay = computed(() => props.data.notice_config && props.data.notice_config.map(item => item.msg_type));


  // 获取通知方式
  const {
    loading: isLoading,
    data: msgType,
  } = useRequest(NoticeManageService.fetchMsgType, {
    defaultValue: {},
    manual: true,
  });
</script>
<style lang="postcss">
.notice-group-detail {
  padding: var(--bk-theme-space-24) var(--bk-theme-space-32);

  .receiver-item {padding: var(--bk-theme-space-2) var(--bk-theme-space-8);
    margin-right: var(--bk-theme-space-4);
    background: var(--bk-theme-surface-muted);
    border-radius: var(--bk-theme-tag-radius);
  }

  .notice-table-content {
    width: 100%;

    .notice-table-value {padding: var(--bk-theme-space-4) var(--bk-theme-space-12);
      color: var(--bk-theme-text-default);
      text-align: center;

      td {
        padding: var(--bk-theme-space-12);
      }

      .check-icon {
        font-size: 14px;
        color: var(--bk-theme-text-default);
      }
    }

    .notice-table-title {
      height: 42px;
      color: var(--bk-theme-text-default);
      text-align: center;
      background-color: var(--bk-theme-table-header-bg);
    }

    tr {
      td {
        border-top: 1px solid var(--bk-theme-border-default);
        border-right: 1px solid var(--bk-theme-border-default);
        border-left: 1px solid var(--bk-theme-border-default);
      }
    }
  }

  .notice-table-content tr:last-child td {
    border-bottom: 1px solid var(--bk-theme-border-default);
  }

  .check-icon {
    font-size: 14px;
    color: var(--bk-theme-text-default);
  }
}
</style>
