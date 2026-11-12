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
  <smart-action
    class="collector-field-extraction-page"
    :offset-target="getSmartActionOffsetTarget">
    <div class="step2-content">
      <div
        class="content-section"
        style="width: calc(100% - 450px);">
        <div class="section-header">
          <span class="section-title">{{ t('字段映射') }}</span>
          <span class="section-divider" />
          <span class="section-desc">{{ t('配置审计中心日志的规范字段与原始日志的映射关系，用以清洗成标准化日志') }}</span>
        </div>
        <audit-form>
          <bk-form-item
            class="field-map-item"
            label=""
            label-width="0">
            <field-map
              ref="fieldMapRef"
              v-model:field-map="tFieldMap"
              :data="previewDataList" />
          </bk-form-item>
        </audit-form>
      </div>

      <div
        class="content-section"
        style="width: 460px; padding-left: 24px; border-left: 1px solid rgb(0 0 0 / 16%);"
        v-bk-tooltips="t('输入数据')">
        <div class="section-header">
          <span class="section-title">{{ t('原始日志') }}</span>
          <span class="section-divider" />
          <span class="section-desc">{{ t('获取需标准化的原始日志，可手动编辑') }}</span>
          <bk-button
            v-if="formData.data"
            class="refresh-btn"
            style="padding-left: 92px;"
            text
            @click="handleRefreshTailLog">
            <audit-icon
              style="margin-right: 5px;"
              type="refresh" />
            <span>{{ t('刷新') }}</span>
          </bk-button>
        </div>
        <bk-loading :loading="isTailLogLoading">
          <audit-form
            ref="inputDataFormRef"
            :model="formData">
            <bk-form-item
              label=""
              label-width="0"
              property="data"
              required>
              <div
                class="original-data-box"
                :class="{ 'bg-color': !formData.data }">
                <div
                  v-if="formData.data"
                  class="original-data">
                  <div class="original-data-text">
                    {{ formData.data }}
                  </div>
                </div>
                <div
                  v-else
                  class="no-data">
                  <img
                    :src="noLogDataSvg"
                    style="width: 68px; margin-left: 16px;">
                  <div
                   
                    style="line-height: 50px; margin-left: var(--bk-theme-space-8)">
                    <span>{{ t('获取数据中') }}</span>
                    <bk-button
                      class="refresh-btn"
                      text
                      @click="handleRefreshTailLog">
                      <audit-icon
                        style="margin-right: 5px;"
                        type="refresh" />
                      <span>{{ t('刷新') }}</span>
                    </bk-button>
                  </div>
                </div>
              </div>
            </bk-form-item>

            <div class="section-content">
              <div class="section-header">
                <span class="section-title">{{ t('提起字段') }}</span>
                <span class="section-divider" />
                <span class="section-desc">{{ t('根据原始日志，按规则提取字段列表') }}</span>
              </div>

              <bk-form-item
                :label="t('字段提取')"
                label-width="72"
                property="etl_config"
                required>
                <bk-radio-group v-model="formData.etl_config">
                  <bk-radio-button
                    v-for="item in dataIdEtlConfigList"
                    :key="item.id"
                    :label="item.id">
                    {{ item.name }}
                  </bk-radio-button>
                </bk-radio-group>
              </bk-form-item>

              <bk-form-item
                label=""
                label-width="0">
                <bk-button
                  v-if="hasLogData"
                  v-bk-tooltips="t('请先刷新，以获取原始数据')"
                  class="is-disabled"
                  :loading="isPreviewLoading"
                  style="width: 80px;"
                  theme="primary">
                  {{ t('提取字段') }}
                </bk-button>
                <bk-button
                  v-else
                  :loading="isPreviewLoading"
                  style="width: 80px;"
                  theme="primary"
                  @click="handleDebug">
                  {{ t('提取字段') }}
                </bk-button>
              </bk-form-item>
            </div>
          </audit-form>
        </bk-loading>
        <!-- previewDataList: 调试后解析的字段 -->
        <render-alternative-field
          :data="previewDataList"
          :related-field-map="tFieldMap" />
      </div>
    </div>
    <template #action>
      <bk-button
        @click="handleLast">
        {{ t('上一步') }}
      </bk-button>
      <bk-button
        v-if="isPreview"
        v-bk-tooltips="t('请先调试并映射字段')"
        class="w88 is-disabled"
        theme="primary" style="margin-left: var(--bk-theme-space-8)">
        {{ t('下一步') }}
      </bk-button>
      <bk-button
        v-else
        class="w88"
        :loading="isSubmiting"
        theme="primary"
        @click="handleSubmit" style="margin-left: var(--bk-theme-space-8)">
        {{ t('下一步') }}
      </bk-button>
      <bk-button
       
        @click="handleCancle" style="margin-left: var(--bk-theme-space-8)">
        {{ t('取消') }}
      </bk-button>
    </template>
  </smart-action>
</template>
<script setup lang="ts">
  // import _ from 'lodash';
  import {
    reactive,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
    useRouter,
  } from 'vue-router';

  import DataIdManageService from '@service/dataid-manage';

  import type StandardField from '@model/meta/standard-field';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';
  import useUrlSearch from '@hooks/use-url-search';

  import noLogDataSvg from '@images/no-log-data.svg?inline';

  // import Card from '@/views/system-manage/log-create/components/field-cleaning/components/card.vue';
  import RenderAlternativeField from '@/views/system-manage/log-create/components/field-cleaning/components/field-map/alternative-field.vue';
  import FieldMap from '@/views/system-manage/log-create/components/field-cleaning/components/field-map/index.vue';

  type TFieldMap = Record<string, string>

  const emits = defineEmits<Emits>();
  interface Emits {
    (e: 'previous'): void
    (e: 'next'): void
  }

  const tFieldMap = ref<TFieldMap>({});

  const inputDataFormRef = ref();
  const fieldMapRef = ref();
  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const formData = reactive({
    data: '',
    etl_config: 'bk_log_json',
    etl_params: {
      delimiter: '',
      regexp: '',
    },
  });
  const dataIdEtlConfigList = [
    { id: 'bk_log_json', name: 'JSON' },
  ];

  const router = useRouter();
  const route = useRoute();
  const hasLogData = ref(true); // 是否又最近日志 无数据禁止调试
  const isPreview = ref(true); // 调试完毕才可提交
  const isError = ref(true); // 调试是否报错

  const isEditMode = route.name === 'logDataIdEdit';
  const {
    searchParams,
    removeSearchParam,
  } = useUrlSearch();
  const bkDataID = searchParams.get('bk_data_id') || route.params.bkDataId;
  const getSmartActionOffsetTarget = () => document.querySelector('.bk-form-content');

  // 原始数据
  const {
    loading: isTailLogLoading,
    refresh: handleRefreshTailLog,
  } = useRequest(DataIdManageService.fetchTail, {
    defaultParams: {
      bk_data_id: bkDataID,
    },
    defaultValue: [],
    manual: true,
    onSuccess(data) {
      if (data.length > 0) {
        hasLogData.value = false;
        formData.data = data[0].value;
        fetchEtlPreview({
          ...formData,
        }).then(() => {
          fieldMapRef.value.getFieldHistory();
        });
      }
    },
  });

  // 调试
  const {
    loading: isPreviewLoading,
    data: previewDataList,
    run: fetchEtlPreview,
  } = useRequest(DataIdManageService.fetchDataIdEtlPreview, {
    defaultValue: [],
    onSuccess: () => {
      isPreview.value = false;
      isError.value = false;
    },
  });

  const {
    loading: isSubmiting,
    run: createDataIdEtl,
  } = useRequest(DataIdManageService.createDataIdEtl, {
    defaultValue: '',
    onSuccess() {
      window.changeConfirm = false;
      isEditMode ? messageSuccess(t('编辑成功')) : messageSuccess(t('新建成功'));
      emits('next');
    },
  });

  // 调试
  const handleDebug = () => {
    isError.value = true;
    inputDataFormRef.value.validate()
      .then(() => {
        window.changeConfirm = false;
        fieldMapRef.value.clearFiledDebug();
        fetchEtlPreview({
          // ...formData,
          data: formData.data,
        }).finally(() => {
          if (isError.value) {
            previewDataList.value = [];
          }
        });
      });
  };

  // 提交字段提取
  const handleSubmit = () => {
    fieldMapRef.value.getValue()
      .then((fields: Array<StandardField>) => {
        const params = {
          bk_data_id: bkDataID,
          etl_params: formData.etl_params,
          fields,
        };
        createDataIdEtl(params);
      })
      .catch(() => {
        const errorEl = fieldMapRef.value.$el.querySelector('.is-errored');
        if (errorEl) {
          errorEl.scrollIntoView({
            behavior: 'smooth',
            block: 'center',
          });
        }
      });
  };

  // 上一步
  const handleLast = () => {
    removeSearchParam('bk_data_id');
    emits('previous');
  };

  // 取消
  const handleCancle = () => {
    router.push({
      name: 'systemDetail',
      params: {
        id: route.params.systemId,
      },
      query: {
        contentType: 'dataReport',
      },
    });
  };
</script>
<style lang="postcss">
.collector-field-extraction-page {
  .step2-content {
    display: flex;
    gap: var(--bk-theme-space-24);
  }

  .content-section {
    .section-header {
      display: flex;
      align-items: center;
      margin-bottom: var(--bk-theme-space-16);

      .section-title {
        font-size: 14px;
        font-weight: 600;
        color: var(--bk-theme-text-strong);
      }

      .section-divider {
        width: 1px;
        height: 12px;
        margin: 0 var(--bk-theme-space-12);
        background: var(--bk-theme-text-weak);
      }

      .section-desc {
        font-size: 12px;
        color: var(--bk-theme-text-weak);
      }
    }
  }

  .original-data-box {
    display: flex;
    min-height: 86px;
    overflow: hidden;
    color: var(--bk-theme-text-default);
    border-radius: var(--bk-theme-tag-radius);

    .original-data {
      display: flex;
      flex: 1;

      .original-data-text {
        flex: 1;
        padding: var(--bk-theme-space-12);
        line-height: 18px;
        word-break: break-all;
        background: var(--bk-theme-surface-subtle);
      }
    }

    .no-data {
      display: flex;
      margin: auto;
      color: var(--bk-theme-text-default);
      background: var(--bk-theme-surface-subtle);
    }
  }

  .bg-color {
    background: var(--bk-theme-surface-subtle);
  }

  .refresh-btn {
    height: 16px;
    padding-left: var(--bk-theme-space-8);
    line-height: 16px;
    color: var(--bk-theme-color-brand-2);
    word-break: keep-all;
    white-space: nowrap;
    cursor: pointer;
    user-select: none;
  }

  .field-map-item {
    .bk-form-content {
      overflow: hidden;
    }
  }
}
</style>
