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
      property="configs.data_source.link_table.uid">
      <span>
        <bk-select
          v-model="formData.configs.data_source.link_table.uid"
          filterable
          :loading="loading"
          :no-match-text="t('无匹配数据')"
          :placeholder="t('请选择')"
          @change="handleChangeLinkDataSheet">
          <bk-option
            v-for="(dataSheet, dataSheetIndex) in data"
            :key="dataSheetIndex"
            :label="dataSheet.name"
            :value="dataSheet.uid" />
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

  import LinkDataDetailModel from '@model/link-data/link-data-detail';

  import useRequest from '@hooks/use-request';

  interface Expose {
    refreshLinkData: () => void,
    resetFormData: () => void,
    setConfigs: (config: IFormData['configs']) => void;
  }
  interface Emits {
    (e: 'updateDataSource', value: IFormData['configs']['data_source']): void,
    (e: 'updateLinkDataDetail', value: LinkDataDetailModel): void,
  }
  interface IFormData {
    configs: {
      data_source: {
        link_table: {
          uid: string,
          version: number,
        },
      },
    },
  }
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const formData = ref<IFormData>({
    configs: {
      data_source: {
        link_table: {
          uid: '',
          version: 0,
        },
      },
    },
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
        uid: id,
      });
    }
    const selectItem = data.value.find(data => data.uid === id);
    formData.value.configs.data_source.link_table.version = selectItem ? selectItem.version : 0;
    emits('updateDataSource', formData.value.configs.data_source);
  };

  // 获取全部联表
  const {
    loading,
    data,
  } = useRequest(linkDataManageService.fetchLinkTableAll, {
    defaultValue: [],
    manual: true,
    onSuccess: () => {
      formData.value.configs.data_source.link_table = {
        uid: '',
        version: 0,
      };
      emits('updateDataSource', formData.value.configs.data_source);
    },
  });

  defineExpose<Expose>({
    refreshLinkData: () => {
      fetchLinkDataSheetDetail({ id: formData.value.configs.data_source.link_table });
    },
    resetFormData: () => {
      formData.value.configs.data_source.link_table = {
        uid: '',
        version: 0,
      };
    },
    setConfigs(configs: IFormData['configs']) {
      if (!configs.data_source.link_table) {
        return;
      }
      formData.value.configs.data_source.link_table = configs.data_source.link_table;
    },
  });
</script>
