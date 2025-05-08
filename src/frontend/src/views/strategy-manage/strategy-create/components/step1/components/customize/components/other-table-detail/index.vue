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
  <div class="other-table-detail">
    <div class="title">
      <span>{{ t('数据预览') }}</span>
      <bk-button
        text
        theme="primary"
        @click="dataStructurePreview">
        <audit-icon
          style="margin-right: 6px;"
          type="view" />
        {{ t('数据结构预览') }}
      </bk-button>
    </div>
    <div class="detail-form">
      <render-info-block class="info-block">
        <render-info-item
          :label="t('数据名称')">
          {{ rtMeta.result_table_name || '--' }}
        </render-info-item>
        <render-info-item
          :label="t('数据ID')">
          {{ rtMeta.result_table_id || '--' }}
        </render-info-item>
        <render-info-item
          :label="t('中文名称')">
          {{ rtMeta.result_table_name_alias || '--' }}
        </render-info-item>
      </render-info-block>
      <render-info-block class="info-block">
        <render-info-item
          :label="t('数据管理员')">
          {{ rtMeta.managers?.join(',') || '--' }}
        </render-info-item>
        <render-info-item
          :label="t('业务运维人员')">
          <edit-tag :data="rtMeta.sensitivity_info?.biz_role_memebers || []" />
        </render-info-item>
        <render-info-item
          :label="t('表类型')">
          {{ rtMeta.processing_type || '--' }}
        </render-info-item>
      </render-info-block>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import RtMetaModel from '@model/strategy/rt-meta';

  import EditTag from '@components/edit-box/tag.vue';

  import RenderInfoBlock from '@views/strategy-manage/list/components/render-info-block.vue';
  import RenderInfoItem from '@views/strategy-manage/list/components/render-info-item.vue';

  import useRequest from '@/hooks/use-request';

  interface Props {
    rtId: string | Array<string>;
  }
  interface Emits {
    (e: 'show-structure-preview', rtId: string | Array<string>, currentViewField: string): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();

  const { t } = useI18n();

  // 获取表格信息
  const {
    data: rtMeta,
    run: fetchTableRtMeta,
  } = useRequest(StrategyManageService.fetchTableRtMeta, {
    defaultValue: new RtMetaModel(),
  });

  const dataStructurePreview = () => {
    emit('show-structure-preview', props.rtId, '');
  };

  watch(() => props.rtId, () => {
    fetchTableRtMeta({
      table_id: props.rtId,
    });
  }, {
    immediate: true,
  });
</script>
<style scoped lang="postcss">
  .other-table-detail {
    padding: 8px 16px;
    margin-top: 8px;
    background-color: #f5f7fa;

    .title {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .info-block {
      display: grid;
      margin-bottom: 12px;
      grid-template-columns: repeat(3, 1fr);
      grid-gap: 12px;
    }
  }
</style>
