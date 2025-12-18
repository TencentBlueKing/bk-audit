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
  padding: 24px 32px;

  .receiver-item {
    padding: 3px 8px;
    margin-right: 4px;
    background: #f0f1f5;
    border-radius: 2px;
  }

  .notice-table-content {
    width: 100%;

    .notice-table-value {
      padding: 5px 12px;
      color: #63656e;
      text-align: center;

      td {
        padding: 10px;
      }

      .check-icon {
        font-size: 14px;
        color: #63656e;
      }
    }

    .notice-table-title {
      height: 42px;
      color: #63656e;
      text-align: center;
      background-color: #fafbfd;
    }

    tr {
      td {
        border-top: 1px solid #dcdee5;
        border-right: 1px solid #dcdee5;
        border-left: 1px solid #dcdee5;
      }
    }
  }

  .notice-table-content tr:last-child td {
    border-bottom: 1px solid #dcdee5;
  }

  .check-icon {
    font-size: 14px;
    color: #63656e;
  }
}
</style>
