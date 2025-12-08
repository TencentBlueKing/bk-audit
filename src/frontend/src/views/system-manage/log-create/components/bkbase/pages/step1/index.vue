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
    class="step1-action"
    :offset-target="getSmartActionOffsetTarget">
    <div class="step1-content">
      <audit-form
        ref="formRef"
        class="bkbase-form"
        :model="localFormData">
        <!-- 源日志信息 -->
        <div class="content-section">
          <div class="section-header">
            <span class="section-title">{{ t('源日志信息') }}</span>
            <span class="section-divider" />
            <span class="section-desc">{{ t('选择计算平台对应的具体数据') }}</span>
          </div>
          <!-- 所属业务 -->
          <bk-form-item
            class="is-required"
            :label="t('所属业务')"
            property="bk_biz_id">
            <bk-loading
              class="form-item-common"
              :loading="isBizListLoading">
              <bk-select
                v-model="localFormData.bk_biz_id"
                v-bk-tooltips="{ content: t('暂不支持跨业务数据源，仅可选择审计中心业务') }"
                :clearable="false"
                disabled
                filterable
                :input-search="false"
                :no-data-text="t('无数据')"
                :no-match-text="t('无匹配数据')"
                :placeholder="t('请选择所属业务')"
                :search-placeholder="t('请输入关键字')">
                <bk-option
                  v-for="item in dataSourceBizList"
                  :key="item.id"
                  :label="item.name"
                  :value="item.id" />
              </bk-select>
            </bk-loading>
          </bk-form-item>

          <!-- 数据源 -->
          <bk-form-item
            class="is-required"
            :label="t('数据源')"
            property="bk_data_id"
            required>
            <bk-loading
              class="form-item-common"
              :loading="isDataIdListLoading">
              <bk-select
                v-model="localFormData.bk_data_id"
                :clearable="false"
                :disabled="isEditMode"
                filterable
                :input-search="false"
                :no-data-text="t('无数据')"
                :no-match-text="t('无匹配数据')"
                :placeholder="t('请选择数据源')"
                :search-placeholder="t('请输入关键字')">
                <bk-option
                  v-for="item in dataIdList"
                  :key="item.bk_data_id"
                  v-bk-tooltips="{
                    content: t('该数据源已接入'),
                    disabled: !item.is_applied || isMouseWheelMoving,
                    delay: 400,
                    placement: 'left-start'
                  }"
                  :disabled="item.is_applied"
                  :label="item.raw_data_alias"
                  :value="item.bk_data_id"
                  @wheel="onWheelMove" />
              </bk-select>
            </bk-loading>
            <!-- 其他数据表详情 -->
            <table-detail
              v-if="localFormData.bk_data_id"
              :rt-id="localFormData.bk_data_id" />
          </bk-form-item>
        </div>

        <!-- 基本信息 -->
        <div class="content-section">
          <div class="section-header">
            <span class="section-title">{{ t('基本信息') }}</span>
          </div>

          <bk-form-item
            :label="t('任务名称')"
            property="custom_collector_ch_name"
            required>
            <bk-input
              v-model="localFormData.custom_collector_ch_name"
              :maxlength="50"
              :placeholder="t('支持汉字、数字、字母、下划线,长短5~50字符')"
              show-word-limit />
          </bk-form-item>

          <bk-form-item
            :label="t('英文名称')"
            property="custom_collector_en_name"
            required>
            <bk-input
              v-model="localFormData.custom_collector_en_name"
              :maxlength="50"
              :placeholder="t('支持数字、字母、下划线,长短5~50字符')"
              show-word-limit />
          </bk-form-item>
        </div>

        <!-- 上报须知-->
        <div class="content-section">
          <div class="section-header">
            <span class="section-title">{{ t('上报须知') }}</span>
          </div>

          <bk-form-item
            :label="t('上报日志须知')"
            property="notice"
            required
            :rules="[
              {
                message: t('请先阅读上报日志须知'),
                trigger: 'change',
                validator: (value: any) => {
                  return !!value.read_requirement && !!value.read_standard;
                },
              },
            ]">
            <div class="log-create-notice">
              <bk-radio
                v-model="localFormData.notice.read_requirement"
                :label="Boolean(true)">
                {{ t('我已阅读') }}
                <a
                  :href="configData?.audit_doc_config?.audit_access_guide"
                  target="_blank">{{ t('《审计中心接入要求》') }}</a>
              </bk-radio>
              <div>
                <bk-radio
                  v-model="localFormData.notice.read_standard"
                  :label="Boolean(true)">
                  {{ t('我已了解') }}
                  <a
                    :href="configData?.audit_doc_config?.audit_operation_log_record_standards"
                    target="_blank">{{ t('《审计中心操作日志记录标准》') }}</a>
                </bk-radio>
              </div>
            </div>
          </bk-form-item>
        </div>
      </audit-form>
    </div>
    <template #action>
      <bk-button @click="handlePrevious">
        {{ t('上一步') }}
      </bk-button>
      <bk-button
        class="ml8"
        :loading="isSubmiting"
        theme="primary"
        @click="handleNext">
        {{ t('下一步') }}
      </bk-button>
      <bk-button
        class="ml8"
        @click="handleCancel">
        {{ t('取消') }}
      </bk-button>
    </template>
  </smart-action>
</template>

<script setup lang="ts">
  import _ from 'lodash';
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import BizService from '@service/biz-manage';
  import DataIdManageService from '@service/dataid-manage';
  import RootManageService from '@service/root-manage';

  import type BizModel from '@model/biz/biz';
  import ConfigModel from '@model/root/config';

  import TableDetail from './components/table-detail.vue';

  import DataIdDetailModel from '@/domain/model/dataid/dataid-detail';
  import useRequest from '@/hooks/use-request';
  import useUrlSearch from '@/hooks/use-url-search';

  interface Props {
    formData: Record<string, any>
  }
  interface Emits {
    (e: 'update:formData', value: Record<string, any>): void
    (e: 'next'): void
    (e: 'previous'): void
    (e: 'cancel'): void
  }
  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();

  const { t } = useI18n();
  const route = useRoute();
  const router = useRouter();
  const {
    appendSearchParams,
    searchParams,
    removeSearchParam,
  } = useUrlSearch();

  const isEditMode = route.name === 'logDataIdEdit';
  const body = document.getElementsByTagName('body')[0];
  const getSmartActionOffsetTarget = () => document.querySelector('.step1-content') as HTMLElement;

  const formRef = ref();
  const localFormData = ref({ ...props.formData });
  const initBizList = ref<Array<BizModel>>([]);
  const isMouseWheelMoving = ref(false);
  const isSubmiting = ref(false);

  const dataSourceBizList = computed(() => bizList.value.filter(item => item.space_type_id === 'bkcc'));

  const {
    run: fecthDetail,
  } = useRequest(DataIdManageService.fecthDetail, {
    defaultParams: {
      bk_data_id: route.params.id,
    },
    defaultValue: new DataIdDetailModel(),
    onSuccess(data) {
      localFormData.value.bk_biz_id = data.bk_biz_id;
      localFormData.value.bk_data_id = data.bk_data_id;
      localFormData.value.custom_collector_ch_name = data.collector_config_name;
      localFormData.value.custom_collector_en_name = data.collector_config_name_en;
      localFormData.value.notice.read_requirement = true;
      localFormData.value.notice.read_standard = true;
    },
  });

  if (isEditMode) {
    fecthDetail({
      bk_data_id: route.params.bkDataId,
    });
  } else if (!isEditMode && searchParams.get('isCreate')) {
    fecthDetail({
      bk_data_id: searchParams.get('bk_data_id'),
    });
    removeSearchParam(['isCreate']);
  }

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
        item.id = Number(item.id);
      });
      // 所属空间的下拉列表里把用户有权限的展示在前面
      handleFilterBizList();
    },
  });

  const {
    loading: isDataIdListLoading,
    data: dataIdList,
    run: fetchDataIDList,
  } = useRequest(DataIdManageService.fetchDataIDList, {
    defaultValue: [],
  });

  const {
    data: configData,
  } = useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
    onSuccess(data) {
      localFormData.value.bk_biz_id = data.bk_biz_id;

      fetchDataIDList({
        bk_biz_id: localFormData.value.bk_biz_id,
      });
    },
  });

  const {
    run: applyDataIdSource,
  } = useRequest(DataIdManageService.applyDataIdSource, {
    defaultValue: {},
    onSuccess() {
      window.changeConfirm = false;
      emit('next');
    },
  });

  const handleFilterBizList = () => {
    const onAuthList = bizList.value.filter(item => item.permission.view_business_v2_bk_log); // 有权限
    const unAuthList = bizList.value.filter(item => !item.permission.view_business_v2_bk_log); // 无权限
    bizList.value = onAuthList.concat(unAuthList);
    initBizList.value = _.cloneDeep(bizList.value);
  };

  let popper: HTMLElement;
  let timeout: number;
  const onWheelMove = () => {
    if (!isMouseWheelMoving.value) {
      isMouseWheelMoving.value = true;
      popper = body.getElementsByClassName('bk-popper')[0] as HTMLElement;
      if (popper) {
        popper.style.display = 'none';
      }
    }
    clearTimeout(timeout);
    timeout = setTimeout(() => {
      isMouseWheelMoving.value = false;
      if (popper) {
        popper.style.display = '';
      }
    }, 1000);
  };

  const handlePrevious = () => {
    emit('previous');
  };

  const handleNext = () => {
    isSubmiting.value = true;
    formRef.value.validate().then(() => {
      appendSearchParams({
        bk_data_id: localFormData.value.bk_data_id,
      });
      return applyDataIdSource({
        bk_data_id: localFormData.value.bk_data_id,
        system_id: route.params.systemId,
        custom_collector_ch_name: localFormData.value.custom_collector_ch_name,
        custom_collector_en_name: localFormData.value.custom_collector_en_name,
      });
    })
      .finally(() => {
        isSubmiting.value = false;
      });
  };

  // 取消-返回接入详情
  const handleCancel = () => {
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

  watch(() => props.formData, (newVal) => {
    // 只在外部数据真正改变时更新本地数据
    if (JSON.stringify(localFormData.value) !== JSON.stringify(newVal)) {
      localFormData.value = { ...newVal };
    }
  }, { deep: true });

  watch(localFormData, (newVal) => {
    // 触发更新事件，让父组件同步数据
    emit('update:formData', { ...newVal });
  }, { deep: true, immediate: false });

</script>

<style scoped lang="postcss">
.step1-action {
  height: 100%;
}

.step1-content {
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

  .bkbase-form {
    width: 66%;

    :deep(.bk-radio-label) {
      font-size: 12px;
    }
  }

  .select-tip {
    position: absolute;
    top: 50%;
    right: 8px;
    z-index: 10;
    transform: translateY(-50%);

    .tip-number {
      display: inline-flex;
      width: 20px;
      height: 20px;
      font-size: 12px;
      color: #fff;
      background: #6366f1;
      border-radius: 50%;
      align-items: center;
      justify-content: center;
    }
  }
}
</style>
