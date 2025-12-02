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
    <div class="step4-content">
      <!-- 字段映射 -->
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

      <!-- 输入数据 -->
      <div
        class="content-section"
        style="width: 460px; padding-left: 24px; border-left: 1px solid rgb(0 0 0 / 16%);"
        :title="t('输入数据')">
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

        <bk-loading :loading="isTailLogLoading || isGlobalsLoading">
          <audit-form
            ref="inputDataFormRef"
            :model="formData"
            :rules="rules">
            <bk-form-item
              :label="t('原始数据')"
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
                    src="@images/no-log-data.svg"
                    style="width: 68px; margin-left: 16px;">
                  <div
                    class="ml8"
                    style="line-height: 50px;">
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
                property="etl_config"
                required>
                <bk-radio-group v-model="formData.etl_config">
                  <bk-radio-button
                    v-for="item in globalsData.etl_config"
                    :key="item.id"
                    :label="item.id">
                    {{ item.name }}
                  </bk-radio-button>
                </bk-radio-group>
              </bk-form-item>

              <bk-form-item
                v-if="formData.etl_config === 'bk_log_delimiter'"
                class="is-required"
                :label="t('分隔符')"
                property="etl_params.delimiter">
                <bk-select
                  v-model="formData.etl_params.delimiter"
                  :clearable="false"
                  :placeholder="t('请选择分隔符')"
                  style="width: 205px;">
                  <bk-option
                    v-for="item in globalsData.data_delimiter"
                    :key="item.id"
                    :label="item.name"
                    :value="item.id" />
                </bk-select>
              </bk-form-item>

              <div v-if="formData.etl_config === 'bk_log_regexp'">
                <bk-form-item
                  class="form-item-common is-required"
                  :label="t('正则表达式')"
                  :label-width="155"
                  property="etl_params.regexp"
                  style="flex: 1;margin-left: -5px;">
                  <bk-input
                    v-model="formData.etl_params.regexp"
                    :placeholder="t('请输入正则表达式')"
                    :rows="5"
                    style="width: 100%;"
                    type="textarea" />
                </bk-form-item>
                <bk-button
                  style="width: 53px;"
                  text />
              </div>

              <bk-form-item>
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
        v-if="isPreview"
        v-bk-tooltips="t('请先调试并映射字段')"
        class="w88 is-disabled"
        theme="primary">
        {{ isEditMode ? t('保存') : t('提交') }}
      </bk-button>
      <bk-button
        v-else
        class="w88"
        :loading="isSubmiting"
        theme="primary"
        @click="handleSubmit">
        {{ isEditMode ? t('保存') : t('提交') }}
      </bk-button>
      <bk-button
        class="ml8"
        @click="handleLast">
        {{ t('上一步') }}
      </bk-button>
      <bk-button
        class="ml8"
        @click="handleCancle">
        {{ t('取消') }}
      </bk-button>
    </template>
  </smart-action>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import {
    reactive,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
    useRouter,
  } from 'vue-router';

  import CollectorManageService from '@service/collector-manage';
  import MetaManageService from '@service/meta-manage';

  import CollectorDetailModel from '@model/collector/collector-detail';
  import GlobalsModel from '@model/meta/globals';
  import type StandardField from '@model/meta/standard-field';

  import useMessage from '@hooks/use-message';
  import useRequest from '@hooks/use-request';
  import useUrlSearch from '@hooks/use-url-search';

  import RenderAlternativeField from '@/views/system-manage/log-create/components/field-cleaning/components/field-map/alternative-field.vue';
  import FieldMap from '@/views/system-manage/log-create/components/field-cleaning/components/field-map/index.vue';

  type TFieldMap = Record<string, string>

  interface Emits {
    (e: 'next', step?: number): void;
    (e: 'previous', step?: number): void;
  }
  const emits = defineEmits<Emits>();

  const tFieldMap = ref<TFieldMap>({});

  const inputDataFormRef = ref();
  const fieldMapRef = ref();
  const { t } = useI18n();
  const { messageSuccess } = useMessage();
  const formData = reactive({
    data: '',
    etl_config: '',
    etl_params: {
      delimiter: '',
      regexp: '',
    },
  });
  const etlParams = ref();
  const router = useRouter();
  const route = useRoute();
  const hasLogData = ref(true); // 是否又最近日志 无数据禁止调试
  const isPreview = ref(true); // 调试完毕才可提交
  const isError = ref(true); // 调试是否报错

  const isEditMode = route.name === 'logCollectorEdit';
  const {
    searchParams,
    removeSearchParam,
  } = useUrlSearch();
  const collectorConfigId = searchParams.get('collector_config_id');
  console.log('collectorConfigId', collectorConfigId);
  const environment = searchParams.get('environment');
  const getSmartActionOffsetTarget = () => document.querySelector('.bk-form-content');
  const rules = {
    'etl_params.regexp': [
      {
        validator: (value: number) => !!value,
        message: t('正则表达式不能为空'),
        trigger: 'blur',
      },
    ],
    'etl_params.delimiter': [
      {
        validator: (value: number) => !!value,
        message: t('分隔符不能为空'),
        trigger: 'blur',
      },
    ],
  };
  // 字段提取
  const {
    loading: isGlobalsLoading,
    data: globalsData,
  } = useRequest(MetaManageService.fetchGlobals, {
    defaultValue: new GlobalsModel(),
    manual: true,
    onSuccess(data) {
      formData.etl_config = data.etl_config[0].id;
    },
  });
  // 编辑数据
  if (isEditMode) {
    useRequest(CollectorManageService.fetchCollectorsById, {
      defaultParams: {
        id: collectorConfigId || route.params.id,
      },
      manual: true,
      defaultValue: new CollectorDetailModel(),
      onSuccess: (data) => {
        etlParams.value = data.etl_params;
        formData.etl_params.regexp = data.etl_params.regexp;
        formData.etl_params.delimiter = data.etl_params.delimiter;
        formData.etl_config = data.environment === 'container' ? data.etl_config || 'bk_log_json' : data.etl_config;
      },
    });
  }

  // 原始数据
  const {
    loading: isTailLogLoading,
    refresh: handleRefreshTailLog,
  } = useRequest(CollectorManageService.fetchTailLog, {
    defaultParams: {
      collector_config_id: collectorConfigId,
    },
    defaultValue: [],
    manual: true,
    onSuccess(data) {
      if (data.length > 0) {
        hasLogData.value = false;
        formData.data = data[0].originData;
        if (!_.isEmpty(etlParams.value)) {
          fetchEtlPreview({
            ...formData,
          }).then(() => {
            fieldMapRef.value.getFieldHistory();
          });
        }
      }
    },
  });

  // 调试
  const {
    loading: isPreviewLoading,
    data: previewDataList,
    run: fetchEtlPreview,
  } = useRequest(CollectorManageService.fetchEtlPreview, {
    defaultValue: [],
    onSuccess: () => {
      isPreview.value = false;
      isError.value = false;
    },
  });

  const {
    loading: isSubmiting,
    run: createCollectorEtl,
  } = useRequest(CollectorManageService.createCollectorEtl, {
    defaultValue: '',
    onSuccess() {
      window.changeConfirm = false;
      isEditMode ? messageSuccess(t('编辑成功')) : messageSuccess(t('新建成功'));
      emits('next', 5);
      // router.push({
      //   name: 'collectorComplete',
      //   params: {
      //     systemId: route.params.systemId,
      //     collectorConfigId,
      //     taskIdList: searchParams.get('task_id_list') ? searchParams.get('task_id_list') : '',
      //   },
      //   query: {
      //     environment,
      //   },
      // });
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
          ...formData,
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
        createCollectorEtl({
          collector_config_id: collectorConfigId,
          etl_config: formData.etl_config,
          etl_params: formData.etl_params,
          fields,
        });
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
    Promise.resolve()
      .then(() => {
        // 容器类型编辑状态——回退到第一步
        if (environment) {
          if (isEditMode) {
            emits('previous', 2);
            removeSearchParam([
              'collector_config_id',
              'task_id_list',
            ]);
            return;
          }
          // 新建状态——跳转到采集编辑页
          router.push({
            name: 'collectorEdit',
            params: {
              systemId: route.params.systemId,
              collectorConfigId,
            },
          });
        } else {
          emits('previous', 3);
        }
      });
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
  .step4-content {
    display: flex;
    gap: 24px;
  }

  .content-section {
    .section-header {
      display: flex;
      align-items: center;
      margin-bottom: 16px;

      .section-title {
        font-size: 14px;
        font-weight: 600;
        color: #313238;
      }

      .section-divider {
        width: 1px;
        height: 12px;
        margin: 0 10px;
        background: #979ba5;
      }

      .section-desc {
        font-size: 12px;
        color: #979ba5;
      }
    }
  }

  .original-data-box {
    display: flex;
    min-height: 86px;
    overflow: hidden;
    color: #63656e;
    border-radius: 2px;

    .original-data {
      display: flex;
      flex: 1;

      .original-data-text {
        flex: 1;
        padding: 10px;
        line-height: 18px;
        word-break: break-all;
        background: #f5f7fa;
      }
    }

    .no-data {
      display: flex;
      margin: auto;
      color: #63656e;
      background: #f5f7fa;
    }
  }

  .bg-color {
    background: #f5f7fa;
  }

  .refresh-btn {
    height: 16px;
    padding-left: 8px;
    line-height: 16px;
    color: #3a84ff;
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
