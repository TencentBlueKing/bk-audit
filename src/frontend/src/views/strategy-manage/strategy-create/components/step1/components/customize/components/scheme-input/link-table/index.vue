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
  <div class="strategy-customize-eventlog-wrap">
    <bk-form-item
      class="no-label"
      label-width="0"
      property="configs.data_source.link_data_sheet_id">
      <span>
        <bk-select
          v-model="formData.configs.data_source.link_data_sheet_id"
          filterable
          :loading="isLinkDataSheetLoading"
          :no-match-text="t('无匹配数据')"
          :placeholder="t('请选择')"
          @change="handleChangeLinkDataSheet">
          <bk-option
            v-for="(dataSheet, dataSheetIndex) in dataSheetList"
            :key="dataSheetIndex"
            :label="dataSheet.name"
            :value="dataSheet.id" />
        </bk-select>
      </span>
    </bk-form-item>
  </div>
</template>

<script setup lang='ts'>
  import {
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import linkDataManageService from '@service/link-data-manage';
  import MetaManageService from '@service/meta-manage';

  import LinkDataDetailModel from '@model/link-data/link-data-detail';

  import useRequest from '@hooks/use-request';

  interface Expose {
    refreshLinkData: () => void,
    resetFormData: () => void,
  }
  interface Emits {
    (e: 'updateDataSource', value: IFormData['configs']['data_source']): void,
    (e: 'updateLinkDataDetail', value: LinkDataDetailModel): void,
  }
  interface IFormData {
    configs: {
      data_source: {
        link_data_sheet_id: string,
      },
    },
  }
  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const formData = ref<IFormData>({
    configs: {
      data_source: {
        link_data_sheet_id: '',
      },
    },
  });

  // 获取关联数据表
  const {
    loading: isLinkDataSheetLoading,
    data: dataSheetList,
  } = useRequest(MetaManageService.fetchLinkDataSheet, {
    defaultValue: [],
    manual: true,
  });

  // 获取关联表详情
  const {
    data: LinkDataDetail,
    run: fetchLinkDataSheetDetail,
  } = useRequest(linkDataManageService.fetchLinkDataDetail, {
    defaultValue: new LinkDataDetailModel(),
    onSuccess: () => {
      emits('updateLinkDataDetail', LinkDataDetail.value);
    },
  });

  // 选择数据表
  const handleChangeLinkDataSheet = (id: string) => {
    if (id !== '') {
      fetchLinkDataSheetDetail({
        id,
      });
    }
    emits('updateDataSource', formData.value.configs.data_source);
  };

  defineExpose<Expose>({
    refreshLinkData: () => {
      fetchLinkDataSheetDetail({ id: formData.value.configs.data_source.link_data_sheet_id });
    },
    resetFormData: () => {
      formData.value.configs.data_source.link_data_sheet_id = '';
    },
  });
</script>
