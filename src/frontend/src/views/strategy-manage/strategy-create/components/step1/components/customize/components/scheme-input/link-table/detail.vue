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
  <div
    v-if="linkDataDetail.config?.links && linkDataDetail.config.links.length"
    class="link-data-detail">
    <bk-alert
      v-if="!(linkDataDetail.version >= (linkTableMaxVersionMap[linkDataDetail.uid] || 1))"
      theme="warning">
      <template #title>
        {{ t('该联表数据有更新，请确认是否刷新同步') }}
        <bk-button
          style="margin: 0 16px;"
          text
          theme="primary"
          @click="handleRefreshLinkData">
          {{ t('刷新') }}
        </bk-button>
        <router-link
          target="_blank"
          :to="{
            name: 'linkDataManage',
            query: {
              name: linkDataDetail.name,
            },
          }">
          {{ t('前往查看详情') }}
        </router-link>
      </template>
    </bk-alert>
    <div class="detail-wrapper">
      <div style="display: flex; justify-content: space-between;">
        <div>
          <span>{{ t('连表预览') }}</span>
          <audit-icon
            v-bk-tooltips="t('联表中，将自动生成各个原始表的字母别名，用于后续选择字段的简略标识')"
            style=" margin-left: 9px; font-size: 14px;color: #c4c6cc; cursor: pointer;"
            type="help-fill" />
        </div>
        <div class="operation">
          <span>{{ t('找不到合适的数据？') }}</span>
          <bk-button
            style="margin: 0 16px;"
            text
            theme="primary"
            @click="create">
            {{ t('立即新建联表') }}
          </bk-button>
          <router-link
            target="_blank"
            :to="{
              name: 'linkDataManage',
            }">
            {{ t('前往联表管理') }}
          </router-link>
        </div>
      </div>
      <div
        v-for="(item, index) in linkDataDetail.config.links"
        :key="index"
        style="margin-bottom: 10px;">
        <div class="detail-table">
          <div class="detail-table-head">
            <div class="left-name">
              <span
                style="
                  color: #3a84ff;
                  background: #f0f1f5;
                  border-radius: 2px;">
                {{ item.left_table.display_name }}
              </span>
              {{ item.left_table.rt_id }}
            </div>
            <div class="join-type">
              <relation-ship :join-type="item.join_type" />
            </div>
            <div class="right-name">
              <span
                style="
                  color: #3a84ff;
                  background: #f0f1f5;
                  border-radius: 2px;">
                {{ item.right_table.display_name }}
              </span>
              {{ item.right_table.rt_id }}
            </div>
          </div>
          <template
            v-for="(field, fieldIndex) in item.link_fields"
            :key="fieldIndex">
            <div class="detail-table-body">
              <div class="left-field">
                {{ field.left_field }}
              </div>
              <div style="width: 40px; text-align: center;">
                =
              </div>
              <div class="right-field">
                {{ field.right_field }}
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
    <create-link-data
      ref="createRef" />
  </div>
</template>
<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import LinkDataManageService from '@service/link-data-manage';

  import LinkDataDetailModel from '@model/link-data/link-data-detail';

  import CreateLinkData from '@views/link-data-manage/link-data-create/index.vue';

  import useRequest from '@/hooks/use-request';

  interface Emits {
    (e: 'refreshLinkData'): void;
  }
  interface Props {
    linkDataDetail: LinkDataDetailModel
  }

  defineProps<Props>();
  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const createRef = ref();
  const linkTableMaxVersionMap = ref<Record<string, number>>({});

  // 获取全部联表版本信息
  useRequest(LinkDataManageService.fetchLinkTableAll, {
    defaultValue: [],
    manual: true,
    onSuccess(data) {
      linkTableMaxVersionMap.value = data.reduce((res, item) => {
        res[item.uid] = item.version;
        return res;
      }, {} as Record<string, number>);
    },
  });

  const create = () => {
    createRef.value.show();
  };

  const handleRefreshLinkData = () => {
    emit('refreshLinkData');
  };
</script>
<style scoped lang="postcss">
.link-data-detail {
  margin-top: 8px;

  .detail-wrapper {
    padding: 16px;
    margin-top: 8px;
    background-color: #f5f7fa;

    .detail-table {
      display: flex;
      flex-direction: column;
    }

    .detail-table-head,
    .detail-table-body {
      display: grid;
      grid-template-columns: 1fr auto 1fr;
      gap: 8px;
      flex: 1;

      .right-name,
      .left-name {
        padding: 5px 8px;
        background-color: #eaebf0;
        border: 1px solid #dcdee5;
      }

      .right-field,
      .left-field {
        padding: 5px 8px;
        background-color: #fff;
        border: 1px solid #dcdee5;
      }

      .join-type {
        display: flex;
        height: 80%;
        padding: 0 5px;
        margin: auto;
        background-color: #e1ecff;
        align-items: center
      }
    }
  }
}
</style>
