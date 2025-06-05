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
    <bk-dropdown
      class="system-delete"
      trigger="click">
      <bk-button text>
        <audit-icon type="more" />
      </bk-button>
      <template #content>
        <bk-dropdown-menu>
          <bk-dropdown-item>
            <bk-button
              text
              @click="handleRemove(data)">
              {{ t('删除') }}
            </bk-button>
          </bk-dropdown-item>
        </bk-dropdown-menu>
      </template>
    </bk-dropdown>
  </div>
</template>
<script setup lang="ts">
  import { InfoBox } from 'bkui-vue';
  import { h } from 'vue';
  import { useI18n } from 'vue-i18n';

  import SystemModel from '@model/meta/system';

  interface Props {
    data: SystemModel
  }
  defineProps<Props>();
  const { t } = useI18n();

  const handleRemove = (data: SystemModel) => {
    InfoBox({
      title: () => h('div', [
        h('div', t('确认删除该联表数据？')),
      ]),
      subTitle: () => h('div', {
        style: {
          fontSize: '14px',
          textAlign: 'left',
        },
      }, [
        h('div', `${t('系统')}: ${data.name}`),
        h('div', {
          style: {
            color: '#4D4F56',
            backgroundColor: '#f5f6fa',
            padding: '12px 16px',
            borderRadius: '2px',
            marginTop: '10px',
          },
        }, t('删除操作无法撤回，请谨慎操作！')),
      ]),
      confirmText: t('删除'),
      cancelText: t('取消'),
      headerAlign: 'center',
      contentAlign: 'center',
      footerAlign: 'center',
      class: 'link-data-delete',
      onConfirm() {
        //
      },
    });
  };
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
