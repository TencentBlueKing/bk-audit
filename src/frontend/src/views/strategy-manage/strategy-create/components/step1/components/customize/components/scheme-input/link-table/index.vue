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
          v-model="dataSource.link_table.uid"
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
              @click="refreshLinkTable">
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
  import { InfoBox } from 'bkui-vue';
  import { h, onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute } from 'vue-router';

  import LinkDataManageService from '@service/link-data-manage';

  import LinkDataDetailModel from '@model/link-data/link-data-detail';

  import useRequest from '@hooks/use-request';

  interface IDataSource {
    link_table: {
      uid: string,
      version: number,
    },
  }

  interface Props {
    hasData: boolean,
  }
  interface Expose {
    refreshLinkData: () => void,
  }
  interface Emits {
    (e: 'updateLinkDataDetail', value: LinkDataDetailModel): void,
    (e: 'resetConfig'): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const dataSource = defineModel<IDataSource>('dataSource', {
    required: true,
  });
  const { t } = useI18n();
  const route = useRoute();
  const prevValue = ref({
    uid: '',
    version: 0,
  });

  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';

  // 获取关联表详情
  const {
    data: LinkDataDetail,
    run: fetchLinkDataSheetDetail,
  } = useRequest(LinkDataManageService.fetchLinkDataDetail, {
    defaultValue: new LinkDataDetailModel(),
    onSuccess: () => {
      emit('updateLinkDataDetail', LinkDataDetail.value);
    },
  });

  const createInfoBoxConfig = (overrides: {
    onConfirm: () => void
    onClose: () => void
  }): any => ({
    type: 'warning',
    title: t('切换数据源请注意'),
    subTitle: () => h(
      'div',
      {
        style: {
          color: '#4D4F56',
          backgroundColor: '#f5f6fa',
          padding: '12px 16px',
          borderRadius: '2px',
          fontSize: '14px',
          textAlign: 'left',
        },
      },
      t('切换后，已配置的数据将被清空。是否继续？'),
    ),
    confirmText: t('继续切换'),
    cancelText: t('取消'),
    headerAlign: 'center',
    contentAlign: 'center',
    footerAlign: 'center',
    ...overrides,
  });

  // 选择数据表
  const handleChangeLinkDataSheet = (id: string) => {
    // 首次选择时，直接更新数据并保存prevValue
    if (!prevValue.value.uid || !props.hasData) {
      if (id !== '') {
        fetchLinkDataSheetDetail({ uid: id });
        const selectItem = data.value.find(data => data.uid === id);
        dataSource.value.link_table.version = selectItem ? selectItem.version : 0;
        dataSource.value.link_table.uid = id;
      }
      // 保存当前值作为prevValue
      prevValue.value = {
        uid: dataSource.value.link_table.uid,
        version: dataSource.value.link_table.version,
      };
      return;
    }

    // 非首次选择时，显示确认对话框
    InfoBox(createInfoBoxConfig({
      onConfirm() {
        // 先更新dataSource
        dataSource.value.link_table.uid = id;
        const selectItem = data.value.find(data => data.uid === id);
        dataSource.value.link_table.version = selectItem ? selectItem.version : 0;

        if (id !== '') {
          // 获取详情
          fetchLinkDataSheetDetail({ uid: id });
        }

        // 更新prevValue
        prevValue.value = {
          uid: dataSource.value.link_table.uid,
          version: dataSource.value.link_table.version,
        };

        emit('resetConfig');
      },
      onClose() {
        // 恢复到之前的值
        dataSource.value.link_table.uid = prevValue.value.uid;
        dataSource.value.link_table.version = prevValue.value.version;
      },
    }));
  };

  const refreshLinkTable = () => {
    fetchLinkTableAll();
  };

  // 获取全部联表
  const {
    loading,
    data,
    run: fetchLinkTableAll,
  } = useRequest(LinkDataManageService.fetchLinkTableAll, {
    defaultValue: [],
    manual: true,
  });

  onMounted(() => {
    if (isEditMode || isCloneMode) {
      // 更新prevValue
      prevValue.value = {
        uid: dataSource.value.link_table.uid,
        version: dataSource.value.link_table.version,
      };
      fetchLinkDataSheetDetail({
        uid: dataSource.value.link_table.uid,
        version: dataSource.value.link_table.version,
      });
    }
  });

  defineExpose<Expose>({
    refreshLinkData: () => {
      fetchLinkDataSheetDetail({
        uid: dataSource.value.link_table.uid,
      }).then(() => {
        // 更新version
        dataSource.value.link_table.version = LinkDataDetail.value.version;
      });
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
