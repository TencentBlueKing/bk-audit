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
    class="create-collector-step1"
    :offset-target="getSmartActionOffsetTarget">
    <bk-loading :loading="isEditDataLoading">
      <audit-form
        ref="formRef"
        :model="formData"
        :rules="rules">
        <card :title="t('基本信息')">
          <bk-form-item
            class="is-required"
            :label="t('上报方式')"
            property="test">
            <bk-radio-group v-model="reportMethod">
              <bk-radio-button
                v-for="item in reportMethodRadioList.filter(item => showBkbase.enabled || item.id !== 'bkbase')"
                :key="item.id"
                class="form-raido-common"
                :disabled="isEditMode"
                :label="item.id"
                @change="changeReportMethod">
                {{ t(item.name) }}
              </bk-radio-button>
            </bk-radio-group>
          </bk-form-item>
          <template v-if="reportMethod === 'newlog'">
            <bk-form-item
              class="is-required"
              :label="t('任务名称')"
              property="collector_config_name">
              <bk-input
                v-model="formData.collector_config_name"
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
                v-model="formData.collector_config_name_en"
                class="form-item-common"
                :placeholder="t('请输入英文名称')"
                :readonly="isEditMode" />
            </bk-form-item>
            <bk-form-item
              :label="t('环境选择')"
              property="environment"
              required>
              <container-environment-type
                v-model:collectorEnvironment="formData.environment"
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
                  v-model="formData.bk_biz_id"
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
              :data="formData"
              :is-edit-mode="isEditMode"
              :space-type-id="spaceTypeId"
              @change="handeUpdate"
              @check-yaml="handleCheckYaml" />
          </template>
          <template v-else>
            <bk-form-item
              class="is-required"
              :label="t('所属业务')"
              property="bk_biz_id">
              <bk-loading
                class="form-item-common"
                :loading="isBizListLoading">
                <bk-select
                  v-model="formData.bk_biz_id"
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
            <bk-form-item
              class="is-required"
              :label="t('数据源')"
              property="bk_data_id">
              <bk-loading
                class="form-item-common"
                :loading="isDataIdListLoading">
                <bk-select
                  v-model="formData.bk_data_id"
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
                    :label="`${item.raw_data_alias}(${item.raw_data_name})`"
                    :value="item.bk_data_id"
                    @wheel="onWheelMove" />
                </bk-select>
              </bk-loading>
            </bk-form-item>
          </template>
        </card>
        <card
          v-if="renderCom === 'physics' && reportMethod === 'newlog'"
          :title="t('日志内容过滤')">
          <bk-form-item :label="t('过滤内容')">
            <log-filter v-model="formData.params.conditions" />
          </bk-form-item>
        </card>
      </audit-form>
    </bk-loading>
    <template #action>
      <bk-button
        class="w88"
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
<script lang="ts">
  import {
    computed,
    provide,
    reactive,
    ref,
  } from 'vue';

  import useFeature from '@hooks/use-feature';

  let formData = reactive({
    // 计算平台数据
    bk_data_id: '',
    system_id: '',
    bk_biz_id: undefined as number | undefined,
    collector_config_id: 0,
    collector_config_name: '',
    collector_config_name_en: '',
    environment: 'linux',
    target_node_type: '',
    target_nodes: [] as Array<Record<string, any>>,
    data_encoding: '',
    params: {
      paths: [''],
      conditions: {
        type: 'match',
        match_type: '',
        match_content: '',
        separator: '',
        separator_filters: [
          {
            logic_op: 'AND',
            fieldindex: '',
            word: '',
          },
        ],
      },
    },
    bcs_cluster_id: '',
    yaml_config: '',
  });
  export type TFormData = typeof formData;
</script>
<script setup lang="ts">
  import _ from 'lodash';
  import { useI18n } from 'vue-i18n';
  import {
    useRoute,
    useRouter,
  } from 'vue-router';

  import BizService from '@service/biz-manage';
  import CollectorManageService from '@service/collector-manage';
  import DataIdManageService from '@service/dataid-manage';
  import RootManageService from '@service/root-manage';

  import type BizModel from '@model/biz/biz';
  import CollectorCreateResultModel from '@model/collector/collector-create-result';
  import CollectorDetailModel from '@model/collector/collector-detail';
  import ConfigModel from '@model/root/config';

  import useRequest from '@hooks/use-request';
  import useUrlSearch from '@hooks/use-url-search';

  import Card from '../../components/card.vue';

  import ContainerEnvironmentType from './components/container/environment-type.vue';
  import RenderContainer from './components/container/render-container.vue';
  import RenderPhysics from './components/container/render-physics.vue';
  import LogFilter from './components/log-filer/index.vue';
  import { compareEditData } from './components/utils';

  import DataIdDetailModel from '@/domain/model/dataid/dataid-detail';

  interface Emits {
    (e: 'changeEnvironment', value: string): void,
    (e: 'change', step: number): void;
    (e: 'changeReportMethod', value: string): void
  }
  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const route = useRoute();
  const router = useRouter();
  const {
    appendSearchParams,
    searchParams,
    removeSearchParam,
  } = useUrlSearch();
  const { feature: showBkbase } = useFeature('bkbase_data_source');
  const comMap = {
    physics: RenderPhysics,
    container: RenderContainer,
  };
  formData = reactive({
    // 计算平台数据
    bk_data_id: '',
    system_id: '',
    bk_biz_id: undefined as number | undefined,
    collector_config_id: 0,
    collector_config_name: '',
    collector_config_name_en: '',
    environment: 'linux',
    target_node_type: '',
    target_nodes: [] as Array<Record<string, any>>,
    data_encoding: '',
    params: {
      paths: [''],
      conditions: {
        type: 'match',
        match_type: '',
        match_content: '',
        separator: '',
        separator_filters: [
          {
            logic_op: 'AND',
            fieldindex: '',
            word: '',
          },
        ],
      },
    },
    bcs_cluster_id: '',
    yaml_config: '',
  });
  const reportMethod = ref('newlog');
  const reportMethodRadioList = ref([
    {
      id: 'newlog',
      name: t('新建日志采集'),
    },
    {
      id: 'bkbase',
      name: t('计算平台已有数据源'),
    },
  ]);
  type environmentType = keyof typeof comMap
  const isEditMode = route.name === 'collectorEdit' || route.name === 'dataIdEdit';
  const formRef = ref();
  const isSubmiting = ref(false);
  const isMouseWheelMoving = ref(false);
  const dataSourceBizList = computed(() => bizList.value.filter(item => item.space_type_id === 'bkcc'));
  const isEditDataLoading = ref(false);
  const initBizList = ref<Array<BizModel>>([]);
  const yaml = ref('');
  const body = document.getElementsByTagName('body')[0];


  const renderCom = ref('physics');
  const componentRef = ref();
  const renderComponent = computed(() => comMap[renderCom.value as environmentType]);
  const spaceTypeId = computed(() => {
    if (formData.bk_biz_id && bizList.value.length) {
      return bizList.value.filter(item => Number(item.id) === formData.bk_biz_id)[0].space_type_id;
    }
    return '';
  });
  let editCollectorData: CollectorDetailModel;
  let editCollectorFormDataClone: typeof formData;
  // 提供给ip-selector使用，如果isShow处于打开状态，不校验target_nodes
  const isShow = ref(false);
  provide('isShow', isShow);
  const rules = {
    system_id: [
      {
        validator: (value: number) => !!value,
        message: t('所属业务不能为空'),
        trigger: 'change',
      },
    ],
    bk_data_id: [
      {
        validator: (value: number) => !!value,
        message: t('数据源不能为空'),
        trigger: 'change',
      },
    ],
    bk_biz_id: [
      {
        validator: (value: number) => !!value,
        message: t('所属业务不能为空'),
        trigger: 'change',
      },
    ],
    collector_config_name: [
      {
        validator: (value: string) => !!value,
        message: t('任务名称不能为空'),
        trigger: 'blur',
      },
      {
        validator: (value: string) => value.length <= 32,
        message: t('任务名称不超过 32 个字符'),
        trigger: 'blur',
      },
      {
        validator: (value: string) => /^[\u4e00-\u9fa5A-Za-z0-9_]+$/.test(value),
        message: t('任务名称仅支持：中文A-Za-z0-9_'),
        trigger: 'blur',
      },
    ],
    collector_config_name_en: [
      {
        validator: (value: string) => !!value,
        message: t('英文名称不能为空'),
        trigger: 'blur',
      },
      {
        validator: (value: string) => value.length >= 5,
        message: t('英文名称至少包含 5 个字符'),
        trigger: 'blur',
      },
      {
        validator: (value: string) => /^[A-Za-z0-9_]+$/.test(value),
        message: t('英文名称仅支持：A-Za-z0-9_'),
        trigger: 'blur',
      },
      {
        validator: (value: string) => CollectorManageService.preCheck({
          collector_config_name_en: value,
        }),
        message: t('英文名称已存在，请重新输入'),
        trigger: 'blur',
      },
    ],
    data_encoding: [
      {
        validator: (value: string) => !!value,
        message: t('日志字符集不能为空'),
        trigger: 'blur',
      },
    ],
    target_nodes: [
      {
        validator: (targetNodes: Array<any>) => {
          if (isShow.value) return;
          return targetNodes.length > 0;
        },
        message: t('采集目标不能为空'),
        trigger: 'change',
      },
    ],
    'params.paths': [
      {
        validator: (paths: Array<string>) => _.findIndex(paths, item => item === '') < 0,
        message: t('采集路径不能为空'),
        trigger: 'change',
      },
    ],
    bcs_cluster_id: [
      {
        validator: (value: number) => !!value,
        message: t('集群选择不能为空'),
        trigger: 'change',
      },
    ],
    yaml_config: [
      {
        validator: () => componentRef.value.getCheckConfigYaml(),
        message: '',
        trigger: 'change',
      },
      {
        validator: (value: string) => !!value,
        message: '',
        trigger: 'change',
      },
    ],
  };

  if (isEditMode && route.name === 'collectorEdit') {
    // 编辑状态 collector_config_name_en 不可编辑，不需要验证
    delete (rules as { collector_config_name_en?: any }).collector_config_name_en;

    isEditDataLoading.value = true;
    useRequest(CollectorManageService.fetchCollectorsById, {
      defaultParams: {
        id: route.params.collectorConfigId,
      },
      defaultValue: new CollectorDetailModel(),
      manual: true,
      onSuccess: (data) => {
        formData.collector_config_id = data.collector_config_id;
        formData.collector_config_name = data.collector_config_name;
        formData.collector_config_name_en = data.collector_config_name_en;
        formData.bk_biz_id = data.bk_biz_id;
        formData.target_node_type = data.target_node_type;
        formData.target_nodes = data.target;
        formData.data_encoding = data.data_encoding;
        formData.params.paths = data.params.paths;
        // 后端返回conditions只有type字段时，把缺少的字段补上，故是合并，不是直接赋值
        formData.params.conditions = Object.assign({}, formData.params.conditions, data.params.conditions);
        formData.bcs_cluster_id = data.bcs_cluster_id;
        formData.yaml_config = decodeURIComponent(escape(atob(data.yaml_config)));
        yaml.value = data.yaml_config;
        formData.environment = data.environment || 'linux';
        if (data.environment === 'container') {
          formData.environment = data.configs[0].collector_type;
          renderCom.value = data.environment;
        }
        editCollectorData = data;
        editCollectorFormDataClone = _.cloneDeep(formData);
        isEditDataLoading.value = false;

        // 触发更改steps
        emits('changeEnvironment', data.environment);
      },
    });
  }

  const {
    run: fecthDetail,
  } = useRequest(DataIdManageService.fecthDetail, {
    defaultParams: {
      bk_data_id: route.params.bkDataId,
    },
    defaultValue: new DataIdDetailModel(),
    onSuccess(data) {
      formData.bk_biz_id = data.bk_biz_id;
      formData.bk_data_id = data.bk_data_id;
    },
  });

  if (isEditMode && route.name === 'dataIdEdit') {
    reportMethod.value = 'bkbase';
    fecthDetail({
      bk_data_id: route.params.bkDataId,
    });
  } else if (!isEditMode && searchParams.get('isCreate')) {
    reportMethod.value = 'bkbase';
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
    data: configData,
  } = useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
    onSuccess(data) {
      if (reportMethod.value === 'bkbase') {
        formData.bk_biz_id = data.bk_biz_id;
      }
      fetchDataIDList({
        bk_biz_id: formData.bk_biz_id,
      });
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
    run: applyDataIdSource,
  } = useRequest(DataIdManageService.applyDataIdSource, {
    defaultValue: {},
    onSuccess() {
      window.changeConfirm = false;
      emits('change', 3);
    },
  });
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
      emits('change', 3);
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
      emits('change', 2);
    },
  });

  const handleFilterBizList = () => {
    const onAuthList = bizList.value.filter(item => item.permission.view_business_v2_bk_log); // 有权限
    const unAuthList = bizList.value.filter(item => !item.permission.view_business_v2_bk_log); // 无权限
    bizList.value = onAuthList.concat(unAuthList);
    initBizList.value = _.cloneDeep(bizList.value);
  };

  const getSmartActionOffsetTarget = () => document.querySelector('.bk-form-content');

  const changeReportMethod = (val: boolean | string | number) => {
    formData.bk_biz_id = val === 'bkbase' ? Number(configData.value.bk_biz_id) : undefined;
    emits('changeReportMethod', val.toString());
  };
  // 切换业务时需要重置采集目标数据
  const handleBizIdChange = () => {
    formData.target_node_type = '';
    formData.target_nodes = [];
  };
  // 动态校验yaml
  const handleCheckYaml = () => {
    // formData.yaml_config = value;
    formRef.value.validate('yaml_config');
  };
  const handleCollectorEnvironment = (value: string) => {
    renderCom.value = value;
    emits('changeEnvironment', value);
  };
  // 同步值
  const handeUpdate = (modelValue: TFormData) => {
    formData.target_node_type = modelValue.target_node_type || formData.target_node_type;
    formData.target_nodes = modelValue.target_nodes || formData.target_nodes;
    formData.data_encoding = modelValue.data_encoding || formData.data_encoding;
    formData.params = modelValue.params || formData.params;
    formData.bcs_cluster_id = modelValue.bcs_cluster_id;
    formData.yaml_config = modelValue.yaml_config;
  };
  // 提交采集
  const handleNext = () => {
    isSubmiting.value = true;
    formRef.value.validate()
      .then(() => {
        const params = { ...formData };
        // 计算平台
        if (reportMethod.value === 'bkbase') {
          if (isEditMode) {
            emits('change', 3);
            appendSearchParams({
              bk_data_id: formData.bk_data_id,
            });
            return;
          }
          appendSearchParams({
            bk_data_id: formData.bk_data_id,
          });
          return applyDataIdSource({
            bk_data_id: formData.bk_data_id,
            system_id: route.params.systemId,
          });
        }
        // BCS
        if (renderCom.value !== 'physics') {
          if (isEditMode && compareEditData(editCollectorFormDataClone, params)) {
            window.changeConfirm = false;
            appendSearchParams({
              collector_config_id: formData.collector_config_id,
              task_id_list: '',
              environment: 'container',
            });
            emits('change', 3);
            return;
          }
          const bcsData = {
            collector_config_name: formData.collector_config_name,
            collector_config_name_en: formData.collector_config_name_en,
            bcs_cluster_id: formData.bcs_cluster_id,
            yaml_config: btoa(unescape(encodeURIComponent(formData.yaml_config))),
            bk_biz_id: formData.bk_biz_id,
            collector_config_id: formData.collector_config_id,
          };
          return handleSubmitCollectorBcs({
            system_id: route.params.systemId,
            ...bcsData,
          });
        }
        // 物理机
        if (formData.params.conditions.type === 'match' || formData.params.conditions.type === 'none') {
          params.params.conditions.separator = '';
          params.params.conditions.separator_filters = [];
        }
        // 编辑采集时
        // 如果用户没有修改过数据
        // 点击下一步直接调转到上一次采集下发
        if (isEditMode && compareEditData(editCollectorFormDataClone, params)) {
          appendSearchParams({
            collector_config_id: editCollectorData.collector_config_id,
            task_id_list: editCollectorData.task_id_list.join(','),
          });
          emits('change', 2);
          return;
        }
        return handleSubmitCollector({
          ...formData,
          system_id: route.params.systemId,
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
</script>
<style lang="postcss">
.create-collector-step1 {
  .form-item-common {
    width: 480px;
  }

  .is-required {
    .bk-form-label .bk-form-label::after {
      position: absolute;
      top: 0;
      width: 14px;
      line-height: 32px;
      color: #ea3636;
      text-align: center;
      content: '*';
    }
  }
}

.bk-biz-id-select {
  .permission-disable-component {
    width: 100%;
  }
}
</style>
