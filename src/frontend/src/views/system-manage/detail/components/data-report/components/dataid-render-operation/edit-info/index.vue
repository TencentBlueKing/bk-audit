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
    <bk-loading :loading="loading || isBizListLoading">
      <div class="base-content">
        <render-info-block>
          <render-info-item :label="t('任务名称')">
            {{ detailData.raw_data_alias }}
          </render-info-item>
          <render-info-item :label="t('更新人')">
            {{ detailData.updated_by }}
          </render-info-item>
        </render-info-block>
        <render-info-block>
          <render-info-item
            class="status-info-item"
            :label="t('任务状态')">
            <audit-icon
              class="icon mr4"
              svg
              :type="statusIconType" />
            <span>{{ statusTip }}</span>
          </render-info-item>
          <render-info-item :label="t('更新时间')">
            {{ detailData.updated_at }}
          </render-info-item>
        </render-info-block>
        <render-info-block>
          <render-info-item :label="t('所属业务')">
            {{ bkBizId }}
          </render-info-item>
          <render-info-item :label="t('创建人')">
            {{ detailData.created_by }}
          </render-info-item>
        </render-info-block>
        <render-info-block>
          <render-info-item :label="t('数据源')">
            {{ detailData.raw_data_name }}
          </render-info-item>
          <render-info-item :label="t('创建时间')">
            {{ detailData.created_at }}
          </render-info-item>
        </render-info-block>
        <render-info-block>
          <render-info-item :label="t('数据ID')">
            <span class="mr8"> {{ detailData.bk_data_id }}</span>
            <bk-button
              clas="detail-btn"
              text
              theme="primary"
              @click="handleViewDetail">
              <span class="mr4">{{ t('查看详情') }}</span>
              <audit-icon
                class="ml4"
                type="jump-link" />
            </bk-button>
          </render-info-item>
        </render-info-block>
      </div>
    </bk-loading>
  </div>
</template>
<script setup lang="ts">

  import {
    computed,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import BizService from '@service/biz-manage';
  import DataIdManageService from '@service/dataid-manage';

  import type CollectorModel from '@model/collector/collector';

  import useRequest from '@hooks/use-request';

  import RenderInfoBlock from '../../render-operation/edit-info/components/render-info-block.vue';
  import RenderInfoItem from '../../render-operation/edit-info/components/render-info-item.vue';

  import DataIdDetailModel from '@/domain/model/dataid/dataid-detail';

  interface Props {
    data: CollectorModel;
  }
  const props = defineProps<Props>();
  const { t } = useI18n();
  const statusIconType = computed(() => (detailData.value.active ? 'normal' : 'abnormal'));
  const statusTip = computed(() => (detailData.value.active ? t('成功') : t('失败')));
  const bkBizId = computed(() => bizList.value.find(item => item.id === props.data.bk_biz_id)?.name);

  const {
    loading,
    data: detailData,
  // eslint-disable-next-line vue/no-setup-props-destructure
  } = useRequest(DataIdManageService.fecthDetail, {
    defaultParams: {
      bk_data_id: props.data.bk_data_id,
    },
    defaultValue: new DataIdDetailModel(),
    manual: true,
  });
  // 业务列表
  const {
    loading: isBizListLoading,
    data: bizList,
  } = useRequest(BizService.fetchList, {
    defaultValue: [],
    manual: true,
    onSuccess: () => {
      bizList.value.forEach((item) => {
        // eslint-disable-next-line no-param-reassign
        item.id =  Number(item.id);
      });
    },
  });

  const handleViewDetail = () => {
    window.open(detailData.value.bkbase_url);
  };
</script>
<style lang="postcss" scoped>
.log-collection-detail-box {
  margin-bottom: 24px;

  .status-info-item {
    .info-value {
      display: flex;
      align-items: center;
    }
  }

  .mr4 {
    margin-right: 4px;
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
