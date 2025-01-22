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
          <template #extension>
            <div
              class="refresh"
              @click="fetchLinkTableAll">
              <audit-icon
                type="refresh" />
              {{ t('刷新联表') }}
            </div>
          </template>
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
  import { useRoute } from 'vue-router';

  import LinkDataManageService from '@service/link-data-manage';

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
  const route = useRoute();
  const { t } = useI18n();

  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';
  const isUpgradeMode = route.name === 'strategyUpgrade';
  let isInit = false;
  if (!isEditMode && !isCloneMode && !isUpgradeMode) {
    isInit = true;
  }

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
  } = useRequest(LinkDataManageService.fetchLinkDataDetail, {
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
    run: fetchLinkTableAll,
  } = useRequest(LinkDataManageService.fetchLinkTableAll, {
    defaultValue: [],
    manual: true,
    onSuccess: () => {
      // 编辑首次进入不置空
      if (!isInit) {
        isInit = true;
        return;
      }
      formData.value.configs.data_source.link_table = {
        uid: '',
        version: 0,
      };
      emits('updateDataSource', formData.value.configs.data_source);
    },
  });

  defineExpose<Expose>({
    refreshLinkData: () => {
      fetchLinkDataSheetDetail({
        uid: formData.value.configs.data_source.link_table.uid,
      }).then(() => {
        // 更新version
        formData.value.configs.data_source.link_table.version = LinkDataDetail.value.version;
        emits('updateDataSource', formData.value.configs.data_source);
      });
    },
    resetFormData: () => {
      formData.value.configs.data_source.link_table = {
        uid: '',
        version: 0,
      };
    },
    setConfigs(configs: IFormData['configs']) {
      if (!configs.data_source.link_table.uid) {
        return;
      }
      formData.value.configs.data_source.link_table = configs.data_source.link_table;
      // 编辑是传入当前联表版本，用于判断是否需要提示更新
      fetchLinkDataSheetDetail({
        uid: formData.value.configs.data_source.link_table.uid,
        version: formData.value.configs.data_source.link_table.version,
      });
      emits('updateDataSource', formData.value.configs.data_source);
      // 设置为初始化
      isInit = false;
    },
  });
</script>
<style lang="postcss" scoped>
.refresh {
  padding: 0 12px;
  margin: auto;
  color: #979ba5;
  cursor: pointer;
}
</style>
