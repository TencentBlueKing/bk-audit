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
  <!-- 步进条 -->
  <teleport to="#teleport-nav-step">
    <bk-steps
      v-model:cur-step="currentStep"
      class="tool-create-step"
      :line-type="isEditMode ? 'solid' : 'dashed'"
      :steps="steps" />
  </teleport>

  <skeleton-loading
    v-if="!isCreating && !isFailed && !isSuccessful"
    fullscreen
    :loading="loading || isEditDataLoading"
    name="createTools">
    <!-- 步骤1：工具配置 -->
    <div
      v-if="currentStep === 1"
      class="step-content">
      <smart-action
        class="create-tools-page"
        :offset-target="getSmartActionOffsetTarget">
        <div class="create-tools-main">
          <audit-form
            ref="formRef"
            class="tools-form"
            form-type="vertical"
            :model="formData"
            :rules="rules">
            <!-- 基础信息 -->
            <base-info
              v-model:form-data="formData"
              :all-tag-data="allTagData"
              :tag-loading="tagLoading" />

            <!-- 工具类型 -->
            <tool-type-section
              ref="toolTypeSectionRef"
              v-model:form-data="formData"
              :com-ref="comRef"
              :is-edit-mode="isEditMode"
              @apply-permission="handleApplyPermission"
              @update:bk-vision-update-time="(val: string) => bkVisionUpdateTime = val"
              @update:is-first-edit="(val: boolean) => isFirstEdit = val"
              @update:is-show-component="(val: boolean) => isShowComponent = val"
              @update:is-update="(val: boolean) => isUpdate = val"
              @update:report-lists-panels="(val: any) => reportListsPanels = val" />

            <component
              :is="ToolTypeComMap[formData.tool_type]"
              v-if="isShowComponent"
              ref="comRef"
              :data-search-config-type="formData.data_search_config_type"
              :form-data-config="formData"
              :is-edit-mode="isEditMode"
              :is-first-edit="isFirstEdit"
              :is-update="isUpdate"
              :name="formData.name"
              :report-lists-panels="reportListsPanels"
              :uid="formData.uid"
              @change-is-update-submit="changeIsUpdateSubmit"
              @change-submit="changeSubmit"
              @get-is-done-de-bug="getIsDoneDeBug" />
          </audit-form>
        </div>
        <template #action>
          <bk-button
            class="w88"
            theme="primary"
            @click="handleNextStep">
            {{ t('下一步') }}
          </bk-button>
          <bk-button
            class="ml8"
            @click="handleCancel">
            {{ t('取消') }}
          </bk-button>
        </template>
      </smart-action>
    </div>

    <!-- 步骤2：可见范围 -->
    <div
      v-if="currentStep === 2"
      class="step-content step2-content">
      <smart-action
        class="create-tools-page"
        :offset-target="getSmartActionOffsetTarget">
        <audit-form :model="formData">
          <card-part-vue
            :is-open="false"
            :show-icon="false"
            :title="t('可见范围')">
            <template #content>
              <!-- 选择可见范围 -->
              <div class="visible-range-select-row">
                <label class="select-label">{{ t('选择可见范围') }}</label>
                <div class="select-control">
                  <visible-range-field
                    :form-data="formData"
                    @update:form-data="handleVisibleRangeChange" />
                </div>
              </div>

              <!-- 各场景/系统参数配置 -->
              <scene-param-config
                :form-data="formData"
                :input-variables="formData.config.input_variable"
                :selected-scenes="selectedSceneItems"
                :selected-systems="selectedSystemItems"
                @update:param-overrides="handleParamOverridesChange" />
            </template>
          </card-part-vue>
        </audit-form>
        <template #action>
          <bk-button
            class="w88"
            @click="handlePreviousStep">
            {{ t('上一步') }}
          </bk-button>
          <bk-button
            v-bk-tooltips="{
              disabled: !isApiDoneDeBug,
              content: t('请完成接口成功调试后再试')
            }"
            class="w88 ml8"
            :disabled="isApiDoneDeBug"
            theme="primary"
            @click="handleSubmit">
            {{ isEditMode ? t('提交') : t('提交') }}
          </bk-button>
          <bk-button
            class="w88 ml8"
            @click="handleCancel">
            {{ t('取消') }}
          </bk-button>
        </template>
      </smart-action>
    </div>
  </skeleton-loading>
  <creating
    v-if="isCreating"
    :is-edit-mode="isEditMode" />
  <failed
    v-if="isFailed"
    :is-edit-mode="isEditMode"
    :name="formData.name"
    @modify-again="handleModifyAgain" />
  <successful
    v-if="isSuccessful"
    :is-edit-mode="isEditMode"
    :name="formData.name" />
</template>

<script setup lang='tsx'>
  import _ from 'lodash';
  import { computed, nextTick, onMounted, provide, ref, toRef, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import MetaManageService from '@service/meta-manage';
  import RootManageService from '@service/root-manage';
  import SceneManageService from '@service/scene-manage';
  import ToolManageService from '@service/tool-manage';

  import ConfigModel from '@model/root/config';
  import ToolDetailModel from '@model/tool/tool-detail';

  import useRouterBack from '@hooks/use-router-back';

  import Api from './components/api/index.vue';
  import BaseInfo from './components/base-info.vue';
  import BkVision from './components/bkvision/index.vue';
  import DataSearch from './components/data-search/index.vue';
  import Creating from './components/tool-status/creating.vue';
  import Failed from './components/tool-status/failed.vue';
  import Successful from './components/tool-status/Successful.vue';
  import ToolTypeSection from './components/tool-type-section.vue';
  import VisibleRangeField from './components/visible-range-field.vue';
  import SceneParamConfig from './components/scene-param-config.vue';
  import CardPartVue from './components/card-part.vue';
  import type { FormData } from './types';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';

  const ToolTypeComMap: Record<string, any> = {
    data_search: DataSearch,
    bk_vision: BkVision,
    api: Api,
  };

  const route = useRoute();
  const router = useRouter();
  const { t } = useI18n();

  const isEditMode = route.name === 'platformToolEdit';
  const backRouteName = 'platformToolConfig';
  const isShowComponent = ref(false);

  // 步骤条配置
  const steps = [
    { title: t('工具配置') },
    { title: t('可见范围') },
  ];
  const currentStep = ref<1 | 2>(1);

  const formRef = ref();
  const comRef = ref();
  const toolTypeSectionRef = ref();

  const { messageWarn } = useMessage();
  const loading = ref(false);
  const isCreating = ref(false);
  const isFailed = ref(false);
  const isSuccessful = ref(false);
  const allTagMap = ref<Record<string, string>>({});
  const isUpdate = ref(false);
  const isFirstEdit = ref(false);
  const reportListsPanels = ref([]);
  const bkVisionUpdateTime = ref('');
  const formData = ref<FormData>({
    source: '',
    users: [],
    name: '',
    tags: [],
    description: '',
    tool_type: 'data_search',
    is_bkvision: false,
    data_search_config_type: 'sql',
    updated_at: '',
    updated_by: '',
    updated_time: null,
    // 可见范围（平铺字段，提交时组装为 visibility 对象）
    visibility_type: 'scenes_and_systems' as FormData['visibility_type'],
    scene_ids: [] as number[],
    system_ids: [] as number[],
    config: {
      referenced_tables: [],
      input_variable: [{
        raw_name: '',
        display_name: '',
        description: '',
        required: false,
        field_category: '',
        default_value: '',
        raw_default_value: '',
        choices: [],
      }],
      output_fields: [{
        raw_name: '',
        display_name: '',
        description: '',
        drill_config: [],
        enum_mappings: {
          collection_id: '',
          mappings: [],
        },
      }],
      output_config: {
        enable_grouping: false,
        groups: [],
      },
      sql: '',
      uid: '',
    },
  });

  const allTagData = ref<Array<{
    tag_id: string;
    tag_name: string;
  }>>([]);

  // 场景/系统列表（用于参数配置区域显示名称）
  const allSceneList = ref<Array<{ id: number; name: string }>>([]);
  const allSystemList = ref<Array<{ id: number; name: string }>>([]);

  // 提供响应式的工具名称给子组件
  provide('newToolDataName', toRef(() => formData.value.name));

  const getSmartActionOffsetTarget = () => document.querySelector('.create-tools-page');

  const rules = {
    name: [
      {
        validator: (value: string) => {
          const reg = /^[\w\u4e00-\u9fa5-_]+$/;
          return reg.test(value);
        },
        message: t('工具名称只允许中文、字母、数字、中划线或下划线组成'),
        trigger: 'change',
      },
    ],
    tags: [
      {
        validator: (value: Array<string>) => {
          const reg = /^[\w\u4e00-\u9fa5-_]+$/;
          return value.every(item => reg.test(allTagMap.value[item] ? allTagMap.value[item] : item));
        },
        message: t('标签只允许中文、字母、数字、中划线或下划线组成'),
        trigger: 'change',
      },
      {
        validator: (value: Array<string>) => {
          const reg = /\D+/;
          if (Object.keys(allTagMap.value).length === 0) {
            return true;
          }
          return value.every(item => reg.test(allTagMap.value[item] ? allTagMap.value[item] : item));
        },
        message: t('标签不能为纯数字'),
        trigger: 'change',
      },
    ],
  };

  // 侧边栏确认之后更新状态
  const changeSubmit = (value: boolean) => {
    isUpdate.value = value;
  };

  // 是否执行更新数据
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const changeIsUpdateSubmit = (_value: boolean) => {
    // 预留回调
  };

  const {
    data: configData,
  } = useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
  });

  // 获取所有标签列表
  const {
    loading: tagLoading,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    run: _fetchAllTags,
  } = useRequest(ToolManageService.fetchToolTags, {
    defaultValue: [],
    manual: true,
    onSuccess: (data) => {
      allTagData.value = data.reduce((res, item) => {
        if (item.tag_id !== '-2') {
          res.push({
            tag_id: item.tag_id,
            tag_name: item.tag_name,
          });
        }
        return res;
      }, [] as Array<{
        tag_id: string;
        tag_name: string;
      }>);
      data.forEach((item) => {
        allTagMap.value[item.tag_id] = item.tag_name;
      });
    },
  });

  // 编辑状态获取数据
  const {
    run: fetchToolsDetail,
    loading: isEditDataLoading,
  } = useRequest(ToolManageService.fetchToolsDetail, {
    defaultValue: new ToolDetailModel(),
    onSuccess: (data) => {
      formData.value = data as any;
      nextTick(() => {
        comRef.value.setConfigs(formData.value.config);
      });
    },
  });

  const handleApplyPermission = () => {
    window.open(`${configData.value.tool.vision_share_permission_url}`);
  };

  // 下一步：校验步骤1表单后进入步骤2
  const handleNextStep = () => {
    const tastQueue = [formRef.value.validate()];
    if (comRef.value && formData.value.tool_type !== 'api') {
      tastQueue.push(comRef.value.getValue());
    }
    // 创建时 api 判断是否调试成功
    if (comRef.value && formData.value.tool_type === 'api' && !isEditMode) {
      const debugResult = comRef.value.getDebugResult();
      if (!debugResult.isDoneDeBug) {
        messageWarn(t('请先进行接口调试'));
        return;
      } if (debugResult.isDoneDeBug && !debugResult.isSuccess) {
        messageWarn(t('接口调试失败'));
        return;
      }
    }
    // api 类型校验分页配置等
    if (comRef.value && formData.value.tool_type === 'api' && comRef.value.validate) {
      if (!comRef.value.validate()) {
        return;
      }
    }
    Promise.all(tastQueue).then(() => {
      // 获取组件配置
      if (comRef.value?.getFields) {
        if (formData.value.tool_type === 'bk_vision') {
          formData.value.config.input_variable = comRef.value.getFields();
          if (!isUpdate.value) {
            formData.value.updated_time = bkVisionUpdateTime.value || null;
          }
        } else {
          formData.value.config = comRef.value.getFields();
        }
      }
      currentStep.value = 2;
    });
  };

  // 上一步
  const handlePreviousStep = () => {
    currentStep.value = 1;
  };

  // 可见范围数据变更
  const handleVisibleRangeChange = (val: FormData) => {
    formData.value.visibility_type = val.visibility_type;
    formData.value.scene_ids = val.scene_ids;
    formData.value.system_ids = val.system_ids;
  };

  // 参数覆盖配置变更
  const handleParamOverridesChange = (value: Record<string, any>) => {
    formData.value.scene_param_overrides = value;
  };

  const handleCancel = () => {
    router.push({
      name: backRouteName,
      query: {
        scene_id: route.query?.scene_id,
        scope_id: route.query?.scope_id,
        scope_type: route.query?.scope_type,
      },
    });
  };

  const handleModifyAgain = () => {
    isCreating.value = false;
    isFailed.value = false;
    isSuccessful.value = false;
    nextTick(() => {
      comRef.value.setConfigs(formData.value.config);
    });
  };

  // 提交
  const handleSubmit = () => {
    const tastQueue = [formRef.value.validate()];
    if (comRef.value && formData.value.tool_type !== 'api') {
      tastQueue.push(comRef.value.getValue());
    }
    // 创建时 api 判断是否调试成功
    if (comRef.value && formData.value.tool_type === 'api' && !isEditMode) {
      const debugResult = comRef.value.getDebugResult();
      if (!debugResult.isDoneDeBug) {
        messageWarn(t('请先进行接口调试'));
        return;
      } if (debugResult.isDoneDeBug && !debugResult.isSuccess) {
        messageWarn(t('接口调试失败'));
        return;
      }
    }

    // api 类型校验分页配置等
    if (comRef.value && formData.value.tool_type === 'api' && comRef.value.validate) {
      if (!comRef.value.validate()) {
        return;
      }
    }

    Promise.all(tastQueue).then(() => {
      // 获取组件配置
      if (comRef.value?.getFields) {
        if (formData.value.tool_type === 'bk_vision') {
          formData.value.config.input_variable = comRef.value.getFields();
          if (!isUpdate.value) {
            formData.value.updated_time = bkVisionUpdateTime.value || null;
          }
        } else {
          formData.value.config = comRef.value.getFields();
        }
      }
      const data = _.cloneDeep(formData.value);
      const groups = data.config.output_config?.groups || [];
      const enableGrouping = data.config.output_config?.enable_grouping || false;
      let hasEmptyOutputFields = false;
      if (groups.length > 0) {
        groups.forEach((item: any) => {
          if (item.output_fields.length === 0) {
            hasEmptyOutputFields = true;
            if (enableGrouping) {
              messageWarn(item.name + t(' 查询结果设置未设置'));
            } else {
              messageWarn(t('查询结果设置未设置'));
            }
          }
        });

        if (hasEmptyOutputFields) {
          return;
        }
      }
      isCreating.value = true;

      const service = isEditMode ? ToolManageService.updateSceneTool : ToolManageService.createSceneTool;

      if (data.tags) {
        data.tags = data.tags.map(item => (allTagMap.value[item] ? allTagMap.value[item] : item));
      }
      service(data)
        .then((res: any) => {
          isFailed.value = false;
          // 新建/编辑成功后不再由前端变更状态，状态以后端默认返回为准
          if (!isEditMode) {
            const toolUid = res?.uid || '';
            if (toolUid) {
              // 记录新建的工具 ID，用于列表页绿底高亮（刷新后消失）
              try {
                const raw = sessionStorage.getItem('tool_manage_new_uids');
                const uids: string[] = raw ? JSON.parse(raw) : [];
                uids.push(toolUid as string);
                sessionStorage.setItem('tool_manage_new_uids', JSON.stringify(uids));
              } catch { /* ignore */ }
            }
          }
          window.changeConfirm = false;
          router.push({
            name: backRouteName,
            query: {
              scene_id: route.query?.scene_id,
              scope_id: route.query?.scope_id,
              scope_type: route.query?.scope_type,
            },
          });
        })
        .catch(() => {
          isSuccessful.value = false;
          isFailed.value = true;
        })
        .finally(() => {
          isCreating.value = false;
        });
    });
  };

  const isApiDoneDeBug = ref(false);
  // api工具获取是否调试成功
  const getIsDoneDeBug = (val: boolean, isEditInfo: boolean, isSuccess: boolean, isSame: boolean) => {
    if (!isEditMode) {
      isApiDoneDeBug.value = !val || !isSuccess;
    } else {
      if (isSame) {
        isApiDoneDeBug.value = false;
      } else if (!isEditInfo && !isSuccess) {
        isApiDoneDeBug.value = true;
      } else if (!isEditInfo) {
        isApiDoneDeBug.value = false;
      } else {
        isApiDoneDeBug.value = !val || !isSuccess;
      }
    }
  };

  watch(() => formData.value.tool_type, (val) => {
    if (val === 'bk_vision') {
      isApiDoneDeBug.value = false;
    }
    if (val === 'data_search') {
      isShowComponent.value = true;
      isApiDoneDeBug.value = false;
    }
    if (val === 'api') {
      isShowComponent.value = true;
    }
  }, {
    deep: true,
    immediate: true,
  });

  // 监听步骤变化：从步骤2返回步骤1时，恢复子组件（数据查询、API接口）的内部状态
  watch(currentStep, (val) => {
    if (val === 1 && formData.value.tool_type !== 'bk_vision') {
      // 等待 DOM 更新完成、子组件挂载好后，调用 setConfigs 恢复状态
      nextTick(() => {
        nextTick(() => {
          if (comRef.value?.setConfigs && formData.value.config) {
            comRef.value.setConfigs(_.cloneDeep(formData.value.config));
          }
        });
      });
    }
  });

  // 加载场景列表（用于参数配置区域）
  const loadSceneListForParams = async () => {
    try {
      const data = await SceneManageService.fetchSceneAll({ status: 'enabled' });
      allSceneList.value = (data || []).map((item: any) => ({
        id: item.scene_id,
        name: item.name,
      }));
    } catch {
      allSceneList.value = [];
    }
  };

  // 加载系统列表（用于参数配置区域）
  const loadSystemListForParams = async () => {
    try {
      const data = await MetaManageService.fetchSystemWithAction({
        audit_status__in: 'accessed',
        namespace: 'default',
      });
      allSystemList.value = (data || []).map((item: any) => ({
        id: item.id,
        name: item.name,
      }));
    } catch {
      allSystemList.value = [];
    }
  };

  // 选中的场景项列表（含名称）
  const selectedSceneItems = computed(() => {
    if (!formData.value.scene_ids || formData.value.visibility_type === 'all_visible') return [];
    if (formData.value.visibility_type === 'all_scenes') return allSceneList.value;
    return allSceneList.value.filter(s => formData.value.scene_ids.includes(s.id));
  });

  // 选中的系统项列表（含名称）
  const selectedSystemItems = computed(() => {
    if (!formData.value.system_ids || formData.value.visibility_type === 'all_visible') return [];
    if (formData.value.visibility_type === 'all_systems') return allSystemList.value;
    return allSystemList.value.filter(s => formData.value.system_ids.includes(s.id));
  });

  onMounted(() => {
    if (isEditMode) {
      fetchToolsDetail({
        uid: route.params.id,
      });
    }
    // 步骤2需要的场景/系统列表
    loadSceneListForParams();
    loadSystemListForParams();
  });

  useRouterBack(() => {
    router.push({
      name: backRouteName,
    });
  });
</script>

<style lang="postcss" scoped>
  .tool-create-step {
    width: 450px;
    margin: 0 auto;
    transform: translateX(-86px);

    :deep(.bk-step) {
      display: flex;

      .bk-step-content {
        display: flex;
      }
    }
  }

  .step-content {
    padding-top: 16px;
  }

  .step2-content {
    padding-top: 16px;
  }

  .visible-range-select-row {
    display: flex;
    flex-direction: column;
    margin-bottom: 16px;

    .select-label {
      margin-bottom: 8px;
      font-size: 12px;
      line-height: 20px;
      color: #63656e;
      flex-shrink: 0;
    }

    .select-control {
      max-width: 660px;
      min-width: 360px;
    }
  }

  /* 步骤2 操作按钮间距 */
  :deep(.smart-action-action) {
    gap: 8px !important;
  }

  .create-tools-page {
    .flex-center {
      display: flex;
      align-items: center;
    }
  }
</style>
