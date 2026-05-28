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
  <skeleton-loading
    v-if="!isCreating && !isFailed && !isSuccessful"
    fullscreen
    :loading="loading || isEditDataLoading"
    name="createTools">
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
          v-bk-tooltips="{
            disabled: !isApiDoneDeBug,
            content: t('请完成接口成功调试后再试')
          }"
          class="w88"
          :disabled="isApiDoneDeBug"
          theme="primary"
          @click="handleSubmit">
          {{ isEditMode ? t('提交') : t('创建') }}
        </bk-button>
        <bk-button
          class="ml8"
          @click="handleCancel">
          {{ t('取消') }}
        </bk-button>
      </template>
    </smart-action>
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
  import { nextTick, onMounted, provide, ref, toRef, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import MetaManageService from '@service/meta-manage';
  import RootManageService from '@service/root-manage';
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

  const isEditMode = route.name === 'sceneToolEdit';
  const backRouteName = 'sceneToolManege';
  const isShowComponent = ref(false);

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
  } = useRequest(MetaManageService.fetchTags, {
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

  onMounted(() => {
    if (isEditMode) {
      fetchToolsDetail({
        uid: route.params.id,
      });
    }
  });

  useRouterBack(() => {
    router.push({
      name: backRouteName,
    });
  });
</script>

<style lang="postcss" scoped>
  .create-tools-page {
    .flex-center {
      display: flex;
      align-items: center;
    }
  }
</style>
