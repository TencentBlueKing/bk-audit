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
        class="collector-form"
        :model="localFormData">
        <div class="content-section">
          <div class="section-header">
            <span class="section-title">{{ t('前置：记录日志') }}</span>
            <span class="section-divider" />
            <span class="section-desc">{{ t('可用于在上报列表进行区分') }}</span>
          </div>
          <bk-form-item
            class="is-required"
            :label="t('任务名称')"
            property="collector_config_name">
            <bk-input
              v-model="localFormData.collector_config_name"
              class="form-item-common"
              :maxlength="32"
              :placeholder="t('请输入任务名称')"
              show-word-limit />
          </bk-form-item>

          <bk-form-item
            class="is-required"
            :label="t('英文名称')"
            property="collector_config_name_en">
            <bk-input
              v-model="localFormData.collector_config_name_en"
              class="form-item-common"
              :placeholder="t('请输入英文名称')"
              :readonly="isEditMode" />
          </bk-form-item>
        </div>

        <div class="content-section">
          <div class="section-header">
            <span class="section-title">{{ t('源日志信息') }}</span>
            <span class="section-divider" />
            <span class="section-desc">{{ t('源日志存的服务器、路径等配置') }}</span>
          </div>

          <bk-form-item
            :label="t('环境选择')"
            property="environment"
            required>
            <container-environment-type
              v-model:collectorEnvironment="localFormData.environment"
              :readonly="isEditMode"
              @change="handleCollectorEnvironment" />
          </bk-form-item>

          <bk-form-item
            class="is-required"
            :label="t('所属空间')"
            property="bk_biz_id">
            <bk-loading
              class="form-item-common"
              :loading="isBizListLoading">
              <bk-select
                v-model="localFormData.bk_biz_id"
                :clearable="false"
                :disabled="isEditMode"
                display-key="displayName"
                enable-virtual-render
                filterable
                id-key="id"
                :input-search="false"
                :list="bizList"
                :no-match-text="t('无匹配数据')"
                :placeholder="t('请选择所属空间')"
                :popover-options="{
                  extCls: 'bk-biz-id-select',
                }"
                :search-placeholder="t('请输入关键字')"
                @change="handleBizIdChange">
                <template #virtualScrollRender="{ item }">
                  <auth-component
                    action-id="view_business_v2_bk_log"
                    :label="`${item.name}(${item.id})`"
                    :permission="item.permission.view_business_v2_bk_log"
                    :resource="item.id"
                    :value="item.id">
                    <div style="display: flex;">
                      <span>{{ item.name }}({{ item.id }})</span>
                      <bk-tag
                        :style="{
                          'margin-left': '12px',
                          'background': item.space_type_id !== 'bkcc' ? '#f0f1f5' : ''
                        }"
                        theme="danger">
                        {{ item.space_type_name }}
                      </bk-tag>
                    </div>
                  </auth-component>
                </template>
              </bk-select>
            </bk-loading>
          </bk-form-item>

          <component
            :is="renderComponent"
            ref="componentRef"
            :data="localFormData"
            :is-edit-mode="isEditMode"
            :space-type-id="spaceTypeId"
            @change="handeUpdate"
            @check-yaml="handleCheckYaml" />
        </div>

        <div
          v-if="renderCom === 'physics'"
          class="content-section">
          <div class="section-header">
            <span class="section-title">{{ t('日志过滤') }}</span>
            <span class="section-divider" />
            <span class="section-desc">{{ t('过滤掉不符合要求日志内容') }}</span>
          </div>

          <bk-form-item :label="t('过滤内容')">
            <log-filter v-model="localFormData.params.conditions" />
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
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import BizService from '@service/biz-manage';
  import CollectorManageService from '@service/collector-manage';

  import type BizModel from '@model/biz/biz';
  import CollectorCreateResultModel from '@model/collector/collector-create-result';
  import CollectorDetailModel from '@model/collector/collector-detail';

  import useUrlSearch from '@hooks/use-url-search';

  import ContainerEnvironmentType from './components/container/environment-type.vue';
  import RenderContainer from './components/container/render-container.vue';
  import RenderPhysics from './components/container/render-physics.vue';
  import LogFilter from './components/log-filer/index.vue';
  import { compareEditData } from './components/utils';

  import useRequest from '@/hooks/use-request';

  export type TFormData = typeof props.formData;

  interface Props {
    formData: Record<string, any>
  }
  interface Emits {
    (e: 'next', step?: number): void;
    (e: 'previous', step?: number): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const formRef = ref();
  const { t } = useI18n();
  const route = useRoute();
  const router = useRouter();
  const { appendSearchParams } = useUrlSearch();

  const getSmartActionOffsetTarget = () => document.querySelector('.step1-action');
  const isEditMode = route.name === 'collectorEdit' || route.name === 'dataIdEdit';
  const comMap = {
    physics: RenderPhysics,
    container: RenderContainer,
  };

  const isSubmiting = ref(false);
  const initBizList = ref<Array<BizModel>>([]);
  const renderCom = ref('physics');
  const localFormData = ref({ ...props.formData });

  let editCollectorData: CollectorDetailModel | undefined;
  let editCollectorFormDataClone: typeof localFormData.value | undefined;

  const renderComponent = computed(() => comMap[renderCom.value as keyof typeof comMap]);
  const spaceTypeId = computed(() => {
    if (localFormData.value.bk_biz_id && bizList.value.length) {
      return bizList.value.filter(item => Number(item.id) === localFormData.value.bk_biz_id)[0].space_type_id;
    }
    return '';
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
        item.id = Number(item.id);
      });
      // 所属空间的下拉列表里把用户有权限的展示在前面
      handleFilterBizList();
    },
  });

  const handleFilterBizList = () => {
    const onAuthList = bizList.value.filter(item => item.permission.view_business_v2_bk_log); // 有权限
    const unAuthList = bizList.value.filter(item => !item.permission.view_business_v2_bk_log); // 无权限
    bizList.value = onAuthList.concat(unAuthList);
    initBizList.value = _.cloneDeep(bizList.value);
  };

  const {
    run: handleSubmitCollectorBcs,
  } = useRequest(isEditMode ? CollectorManageService.updateBcs : CollectorManageService.createBcs, {
    defaultValue: new CollectorCreateResultModel(),
    onSuccess(data) {
      window.changeConfirm = false;
      appendSearchParams({
        collector_config_id: data.collector_config_id,
        task_id_list: data.task_id_list ? data.task_id_list.join(',') : '',
        environment: 'container',
      });
      emit('next', 4);
    },
  });

  const {
    run: handleSubmitCollector,
  } = useRequest(isEditMode ? CollectorManageService.update : CollectorManageService.create, {
    defaultValue: new CollectorCreateResultModel(),
    onSuccess(data) {
      window.changeConfirm = false;
      appendSearchParams({
        collector_config_id: data.collector_config_id,
        task_id_list: data.task_id_list.join(','),
      });
      emit('next', 4);
    },
  });

  // 切换业务时需要重置采集目标数据
  const handleBizIdChange = () => {
    localFormData.value.target_node_type = '';
    localFormData.value.target_nodes = [];
  };

  // 动态校验yaml
  const handleCheckYaml = () => {
    // localFormData.value.yaml_config = value;
    formRef.value.validate('yaml_config');
  };

  // 同步值
  const handeUpdate = (modelValue: TFormData) => {
    localFormData.value.target_node_type = modelValue.target_node_type || localFormData.value.target_node_type;
    localFormData.value.target_nodes = modelValue.target_nodes || localFormData.value.target_nodes;
    localFormData.value.data_encoding = modelValue.data_encoding || localFormData.value.data_encoding;
    localFormData.value.params = modelValue.params || localFormData.value.params;
    localFormData.value.bcs_cluster_id = modelValue.bcs_cluster_id;
    localFormData.value.yaml_config = modelValue.yaml_config;
  };

  const handleCollectorEnvironment = (value: string) => {
    renderCom.value = value;
    // emits('changeEnvironment', value);
  };

  const handlePrevious = () => {
    emit('previous');
  };

  // 提交采集
  const handleNext = () => {
    isSubmiting.value = true;
    formRef.value.validate()
      .then(() => {
        const params = { ...localFormData.value };
        // BCS
        if (renderCom.value !== 'physics') {
          if (isEditMode && editCollectorFormDataClone && compareEditData(editCollectorFormDataClone, params)) {
            window.changeConfirm = false;
            appendSearchParams({
              collector_config_id: localFormData.value.collector_config_id,
              task_id_list: '',
              environment: 'container',
            });
            emit('next', 4);
            return;
          }
          const bcsData = {
            collector_config_name: localFormData.value.collector_config_name,
            collector_config_name_en: localFormData.value.collector_config_name_en,
            bcs_cluster_id: localFormData.value.bcs_cluster_id,
            yaml_config: btoa(unescape(encodeURIComponent(localFormData.value.yaml_config))),
            bk_biz_id: localFormData.value.bk_biz_id,
            collector_config_id: localFormData.value.collector_config_id,
          };
          return handleSubmitCollectorBcs({
            system_id: route.params.systemId as string,
            ...bcsData,
          });
        }
        // 物理机
        if (localFormData.value.params?.conditions?.type === 'match' || localFormData.value.params?.conditions?.type === 'none') {
          params.params.conditions.separator = '';
          params.params.conditions.separator_filters = [];
        }
        // 编辑采集时
        // 如果用户没有修改过数据
        // 点击下一步直接调转到字段清洗（第4步）
        if (isEditMode
          && editCollectorFormDataClone
          && editCollectorData
          && compareEditData(editCollectorFormDataClone, params)) {
          appendSearchParams({
            collector_config_id: editCollectorData.collector_config_id,
            task_id_list: editCollectorData.task_id_list.join(','),
          });
          emit('next', 4);
          return;
        }
        return handleSubmitCollector({
          ...localFormData.value,
          system_id: route.params.systemId as string,
        });
      })
      .finally(() => {
        isSubmiting.value = false;
      });
  };

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

.collector-form {
  width: 66%;

  .recommend-text {
    padding: 2px 4px;
    font-size: 10px;
    color: #fff;
    background: #f59500;
    border-radius: 2px;
  }

  .description-box {
    width: 300px;
    padding: 0 8px;
    margin-top: 8px;
    font-size: 12px;
    color: #979ba5;
    background: #f5f7fa;
  }

  .sdk-support {
    display: flex;
    flex-direction: column;
    gap: 6px;

    .sdk-support-desc {
      font-size: 12px;
      color: #979ba5;
    }

    .sdk-support-footer {
      padding: 0 12px;
      margin-top: 6px;
      font-size: 12px;
      color: #4d4f56;
      background-color: #f5f7fa;
    }
  }

  .log-create-notice {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
}
</style>
