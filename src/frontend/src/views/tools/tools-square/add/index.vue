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
          <card-part-vue :title="t('基础信息')">
            <template #content>
              <div class="flex-center">
                <bk-form-item
                  class="is-required mr16"
                  :label="t('工具名称')"
                  label-width="160"
                  property="name"
                  required
                  style="flex: 1;">
                  <bk-input
                    v-model.trim="formData.name"
                    :maxlength="32"
                    :placeholder="t('请输入，32字符内，可由汉字、小写字母、数字、“_”组成')"
                    show-word-limit
                    style="width: 100%;" />
                </bk-form-item>
                <bk-form-item
                  :label="t('工具标签')"
                  label-width="160"
                  property="tags"
                  style="flex: 1;">
                  <bk-loading
                    :loading="tagLoading"
                    style="width: 100%;">
                    <bk-select
                      v-model="formData.tags"
                      allow-create
                      class="bk-select"
                      filterable
                      :input-search="false"
                      multiple
                      multiple-mode="tag"
                      :placeholder="t('请选择')"
                      :search-placeholder="t('请输入关键字')">
                      <bk-option
                        v-for="(item, index) in allTagData"
                        :key="index"
                        :label="item.tag_name"
                        :value="item.tag_id" />
                    </bk-select>
                  </bk-loading>
                </bk-form-item>
              </div>
              <bk-form-item
                :label="t('工具说明')"
                label-width="160"
                property="description"
                required>
                <bk-input
                  v-model.trim="formData.description"
                  autosize
                  :maxlength="100"
                  :placeholder="t('请输入说明')"
                  show-word-limit
                  style="width: 50%;"
                  type="textarea" />
              </bk-form-item>
            </template>
          </card-part-vue>

          <!-- 工具类型 -->
          <card-part-vue :title="t('工具类型')">
            <template #content>
              <bk-form-item
                :label="t('工具类型')"
                label-width="160"
                property="tool_type"
                required>
                <bk-radio-group v-model="formData.tool_type">
                  <template
                    v-for="(item, index) in toolTypeList"
                    :key="index">
                    <bk-radio
                      :disabled="route.name === 'toolsEdit'"
                      :label="item.id">
                      <div style="display: flex; align-items: center; line-height: 16px;">
                        <audit-icon
                          style=" margin-right: 5px;font-size: 16px;"
                          svg
                          :type="iconMap[item.id as keyof typeof iconMap]" />
                        <span
                          v-bk-tooltips="{
                            disabled: !item.tips,
                            content: item.tips || '',
                          }"
                          :style="item.tips ? { 'border-bottom': '1px dashed #979ba5' } : {}">{{ item.name }}</span>
                      </div>
                    </bk-radio>
                  </template>
                </bk-radio-group>
              </bk-form-item>

              <!-- 数据查询 -->
              <template v-if="formData.tool_type === 'data_search'">
                <bk-form-item
                  :label="t('配置方式')"
                  label-width="160"
                  property="data_search_config_type"
                  required>
                  <bk-button-group>
                    <bk-button
                      v-for="item in searchTypeList"
                      :key="item.value"
                      :disabled="item.disabled"
                      :selected="formData.data_search_config_type === item.value"
                      @click="() => formData.data_search_config_type = item.value">
                      {{ item.label }}
                    </bk-button>
                  </bk-button-group>
                  <div>
                    <bk-tag v-if="formData.data_search_config_type === 'simple'">
                      {{ t('用于复杂的 SQL 查询，先编写 SQL，再根据 SQL 内的结果与变量配置前端样式') }}
                    </bk-tag>
                    <bk-tag v-else>
                      {{ t('用于单一数据表，先配置的输入与输出字段，默认生成查询语句') }}
                    </bk-tag>
                  </div>
                </bk-form-item>
                <bk-form-item
                  v-if="formData.data_search_config_type === 'simple'"
                  :label="t('选择数据源')"
                  label-width="160"
                  property="source"
                  required>
                  <bk-input
                    v-model="formData.source"
                    :placeholder="t('请输入数据源名称、表名、ID 等，或可直接按分类筛选')" />
                </bk-form-item>
              </template>

              <!-- BKVision 图表 -->
              <div v-else-if="formData.tool_type === 'bk_vision'">
                <bk-form-item
                  :label="t('选择报表')"
                  label-width="160"
                  property="config.uid"
                  required>
                  <div v-if="hasPermission">
                    <div class="chart-cascade">
                      <bk-cascader
                        v-model="configUid"
                        children-key="share"
                        id-key="uid"
                        :list="Array.isArray(chartLists) ? chartLists : []"
                        :multiple="false"
                        :show-complete-name="false"
                        :style="spacePermission ? `width: 50%;border: 1px solid #e71818;` : `width: 50%;`"
                        trigger="click"
                        @change="handleSpaceChange" />
                      <bk-button
                        v-show="goBkVisionBtn && configUid.length > 0"
                        class="ml8"
                        @click="handleGoBkvision">
                        {{ t('跳转至 BKVision') }}
                      </bk-button>
                      <audit-icon
                        v-bk-tooltips="t('刷新报表')"
                        class="vision-refresh"
                        :class="{ rotating: isRefreshing }"
                        type="refresh"
                        @click="handleRefreshClick" />
                    </div>
                    <div
                      v-if="spacePermission"
                      class="permission">
                      {{ t('该报表无权限，请') }} <span
                        class="permission-link"
                        @click="handleApplyPermission">{{ t('申请权限') }}</span>
                    </div>
                  </div>
                  <div v-else>
                    <bk-input
                      disabled
                      :model-value="t('当前图表你没有权限，请申请权限后再操作')" />
                  </div>
                </bk-form-item>
              </div>
            </template>
          </card-part-vue>
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
            @change-submit="changeSubmit" />
        </audit-form>
      </div>
      <template #action>
        <bk-button
          class="w88"
          theme="primary"
          @click="handleSubmit">
          {{ isEditMode ? t('提交') : t('创建') }}
        </bk-button>
        <bk-button
          class="ml8"
          @click="handleCancel">
          {{ t('取消') }}
        </bk-button>
        <!-- <bk-button
          class="ml8"
          :disabled="!formData.config.sql"
          style="margin-left: 48px;"
          @click="handlePreview">
          {{ t('预览测试') }}
        </bk-button> -->
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
  import { nextTick, onMounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import MetaManageService from '@service/meta-manage';
  import RootManageService from '@service/root-manage';
  import ToolManageService from '@service/tool-manage';

  import ConfigModel from '@model/root/config';
  import ToolDetailModel from '@model/tool/tool-detail';

  import useRouterBack from '@hooks/use-router-back';

  import Api from './components/api/index.vue';
  import BkVision from './components/bkvision/index.vue';
  import CardPartVue from './components/card-part.vue';
  import DataSearch from './components/data-search/index.vue';
  import Creating from './components/tool-status/creating.vue';
  import Failed from './components/tool-status/failed.vue';
  import Successful from './components/tool-status/Successful.vue';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';

  interface FormData {
    uid?: string; // 工具uid
    source?:string;
    users?: string[];
    name: string;
    tags: string[];
    description: string;
    tool_type: string;
    updated_at: string;
    updated_by: string;
    is_bkvision: boolean;
    updated_time: string | null;
    data_search_config_type: string;
    config: {
      referenced_tables: Array<{
        table_name: string | null;
        alias: string | null;
        permission: {
          result: boolean;
        };
      }>;
      input_variable: Array<{
        raw_name: string;
        display_name: string;
        description: string;
        required: boolean;
        field_category: string;
        default_value: any;
        raw_default_value?: any,
        is_default_value?: boolean;
        choices: Array<{
          key: string,
          name: string
        }>
      }>
      output_fields: Array<{
        raw_name: string;
        display_name: string;
        description: string;
        drill_config: Array<{
          tool: {
            uid: string;
            version: number;
          };
          drill_name: string;
          config: Array<{
            source_field: string;
            target_value_type: string;
            target_value: string;
          }>
        }>;
        enum_mappings: {
          collection_id: string;
          mappings: Array<{
            key: string;
            name: string;
          }>;
        };
      }>
      sql: string;
      uid: string;
    };
  }

  interface ChartListModel {
    uid: string;
    name: string;
    share: Array<{
      uid: string;
      name: string;
    }>;
  }

  const ToolTypeComMap: Record<string, any> = {
    data_search: DataSearch,
    bk_vision: BkVision,
    api: Api,
  };

  const route = useRoute();
  const router = useRouter();
  const { t } = useI18n();

  const searchTypeList = [{
    label: t('简易模式'),
    value: 'simple',
    disabled: true,
  }, {
    label: t('SQL模式'),
    value: 'sql',
  }];
  const isEditMode = route.name === 'toolsEdit';
  const isShowComponent = ref(false);
  const configUid = ref<string[]>([]);
  const hasPermission = ref(true);
  const spacePermission = ref(false);

  const formRef = ref();
  const comRef = ref();

  const { messageSuccess } = useMessage();
  const loading = ref(false);
  const isCreating = ref(false);
  const isFailed = ref(false);
  const isSuccessful = ref(false);
  const goBkVisionBtn = ref(false);
  const allTagMap = ref<Record<string, string>>({});
  const isUpdate = ref(false);
  const isUpdateSubmit = ref(false);
  const isFirstEdit = ref(false);
  const dashboardUid = ref('');
  const reportListsPanels = ref([]);
  const formData = ref<FormData>({
    source: '',
    users: [],
    name: '',
    tags: [],
    description: '',
    tool_type: 'api',
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
      sql: '',
      uid: '',  // BKVision图表uid
    },
  });

  const allTagData = ref<Array<{
    tag_id: string
    tag_name: string;
  }>>([]);

  const toolTypeList = ref<Array<{
    id: string;
    name: string;
    tips?: string;
  }>>([{
    id: 'data_search',
    name: t('数据查询'),
    tips: t('根据输入条件，使用 SQL 查询数据库以获得结果；可定义输入与输出'),
  }, {
    id: 'api',
    name: t('API接口'),
    tips: t('根据输入条件，使用 API 接口调用以获得结果。可定义输入与输出'),
  }, {
    id: 'bk_vision',
    name: t('BKVision图表'),
  }]);

  const iconMap = {
    data_search: 'sqlxiao',
    api: 'apixiao',
    bk_vision: 'bkvisonxiao',
  };


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
      // 因为校验的是name，但value是id的数组；将item转为name，自定义输入id = name，直接使用item即可
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
          // 接口过慢时 allTagMap.value为空
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
  const changeIsUpdateSubmit = (value: boolean) => {
    isUpdateSubmit.value = value;
  };
  const {
    data: configData,
  } = useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
  });

  // 跳转到BKVision
  const handleGoBkvision = () => {
    window.open(`${configData.value.third_party_system.bkvision_web_url}#/${configUid.value[0]}/dashboards/detail/root/${dashboardUid.value}`);
  };
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
        tag_name: string
      }>);
      data.forEach((item) => {
        allTagMap.value[item.tag_id] = item.tag_name;
      });
    },
  });
  const isRefreshing = ref(false);
  // 获取图表列表
  const {
    data: chartLists,
    run: fetchChartLists,
  } = useRequest(ToolManageService.fetchChartLists, {
    defaultValue: new Array<ChartListModel>(),
    // manual: true,
    onSuccess: (data) => {
      if (isRefreshing.value) {
        return;
      }
      if (data === 'error') {
        hasPermission.value = false;
        chartLists.value = [];
        return;
      }
      if (isEditMode) {
        if (Array.isArray(data)) {
          hasPermission.value = true;
          configUid.value = data.map((item: any) => {
            let ids = '';
            item.share.forEach((sh: any) => {
              if (sh.uid === formData.value.config.uid) {
                ids = `${item.uid},${sh.uid}`;
              }
            });
            return ids;
          }).filter(item => item !== '')[0].split(',');
        }
      }
    },
  });
  const bkVisionUpdateTime = ref('');
  const {
    run: fetchReportLists,
  } = useRequest(ToolManageService.fetchReportLists, {
    defaultValue: {},
    onSuccess: (res) => {
      if (isRefreshing.value) {
        return;
      }
      if (res) {
        dashboardUid.value = res.data.dashboard_uid;
        const configInputVariable = _.cloneDeep(formData.value.config.input_variable);
        const { panels, variables } = res.data;
        reportListsPanels.value = panels;
        const filters = [...new Set(Object.keys(res.filters))];
        // eslint-disable-next-line max-len
        const getInputVariableConfig = (isVariables: boolean, com: any, isEditMode: boolean, originalDefaultValue?: string | Array<string>) => ({
          raw_name: (isVariables ? com?.flag  : com?.chartConfig?.flag) || '',
          display_name: (isVariables ? com?.description  : com.title) || '',
          description: com.uid || '',
          field_category: com.type || '',
          required: true,
          is_default_value: false,
          raw_default_value: '',
          default_value: isEditMode ? originalDefaultValue : (originalDefaultValue || ''),
          choices: [],
        });

        // 编辑模式下第一次进入检查更新
        if (isEditMode && clickSpaceChange.value === 1) {
          isFirstEdit.value = true;
          isUpdate.value =  formData.value.is_bkvision;
          formData.value.config.input_variable = formData.value.config.input_variable.map((item) => {
            // 变量描述取最新的变量描述
            if (item.field_category === 'variable') {
              let variablesDescription = '';
              variables.forEach((variable: any) => {
                if (variable.uid === item.description) {
                  variablesDescription = variable.description;
                }
              });
              return {
                ...item,
                raw_default_value: res.constants[item.raw_name],
                display_name: variablesDescription,
                default_value: item.default_value,
                choices: [],
              };
            }
            return {
              ...item,
              default_value: item.default_value,
              choices: [],
            };
          });
        } else {
          isFirstEdit.value = false;
          isUpdate.value = false;
          formData.value.config.input_variable = filters
            .map((item) => {
              const com = panels.find((p: any) => p.uid === item);
              if (!com) return null;

              let originalDefaultValue: string | Array<string> = '';
              if (isEditMode && configInputVariable.length > 0) {
                const originalItem = configInputVariable.find((original: any) => original.description === com.uid);
                if (originalItem) originalDefaultValue = originalItem.default_value;
              } else {
                originalDefaultValue = res.filters[com.uid];
              }
              return getInputVariableConfig(false, com, isEditMode, originalDefaultValue);
            })
            .filter((item): item is NonNullable<typeof item> => item !== null);

          if (variables.length > 0) {
            variables.forEach((com: any) => {
              if (com.build_in) return;
              let originalDefaultValue: string | Array<string> = '';
              if (isEditMode && configInputVariable.length > 0) {
                const originalItem = configInputVariable.find((original: any) => original.description === com.uid);
                if (originalItem) originalDefaultValue = originalItem.default_value;
              } else {
                originalDefaultValue = res.constants[com.flag];
              }
              formData.value.config.input_variable.push({
                ...getInputVariableConfig(true, com, isEditMode, originalDefaultValue),
                is_default_value: false,
                raw_default_value: originalDefaultValue || '',
              });
            });
          }
        }

        bkVisionUpdateTime.value = res.data.updated_time || null;

        // 设置组件配置
        nextTick(() => {
          const bkVisionCom = filters
            .map((item) => {
              const com = panels.find((p: any) => p.uid === item);
              if (!com) return null;
              return getInputVariableConfig(false, com, true, res.filters[item]);
            })
            .filter((item): item is NonNullable<typeof item> => item !== null);
          const updatedBkVisionCom = bkVisionCom.map((comItem) => {
            // eslint-disable-next-line max-len
            const formItemMatch = formData.value.config.input_variable.find(formItem => formItem.description === comItem.description);
            if (formItemMatch) {
              return {
                ...comItem,
                is_default_value: formItemMatch.is_default_value,
              };
            }
            return comItem;
          });
          comRef.value.setConfigs(formData.value.config.input_variable);
          comRef.value.setVariablesConfig(res.data.variables, updatedBkVisionCom, res);
        });
        goBkVisionBtn.value = true;
      } else {
        spacePermission.value = true;
        goBkVisionBtn.value = false;
      }
    },
  });
  const clickSpaceChange = ref(0);

  // 刷新图标点击事件
  const handleRefreshClick = async () => {
    if (isRefreshing.value) return;
    isRefreshing.value = true;
    try {
      // 如果有选中的报表，重新获取报表数据
      fetchChartLists().then(() => {
        messageSuccess(t('刷新成功'));
      });
      if (configUid.value.length > 0) {
        await fetchReportLists({
          share_uid: configUid.value[configUid.value.length - 1],
        });
      }
    } finally {
      isRefreshing.value = false;
    }
  };
  // 选择报表
  const handleSpaceChange = (val: string) => {
    isRefreshing.value = false;
    clickSpaceChange.value += 1;
    spacePermission.value = false;
    if (val.length === 0) {
      return;
    }
    fetchReportLists({
      share_uid: val[val.length - 1],
    }).then((r) => {
      if (!r) {
        isShowComponent.value = false;
      } else {
        isShowComponent.value = true;
      }
    });
  };

  // 编辑状态获取数据
  const {
    run: fetchToolsDetail,
    loading: isEditDataLoading,
  } = useRequest(ToolManageService.fetchToolsDetail, {
    defaultValue: new ToolDetailModel(),
    onSuccess: (data) => {
      formData.value = data as any;
      comRef.value.setConfigs(formData.value.config);
    },
  });

  const handleApplyPermission = () => {
    window.open(`${configData.value.tool.vision_share_permission_url}`);
  };

  const handleCancel = () => {
    router.push({
      name: 'toolsSquare',
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

    Promise.all(tastQueue).then(() => {
      isCreating.value = true;

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
      const service = isEditMode ? ToolManageService.updateTool : ToolManageService.createTool;

      if (data.tags) {
        data.tags = data.tags.map(item => (allTagMap.value[item] ? allTagMap.value[item] : item));
      }
      service(data)
        .then(() => {
          isFailed.value = false;
          isSuccessful.value = true;
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

  watch(() => formData.value.tool_type, (val) => {
    if (val === 'bk_vision') {
      fetchChartLists();
    }
    if (val === 'data_search' || val === 'api') {
      isShowComponent.value = true;
    }
  }, {
    deep: true,
    immediate: true,
  });

  watch(() => configUid.value, (val) => {
    if (val.length  === 0) {
      formData.value.config.uid = '';
      isShowComponent.value = false;
    } else {
      formData.value.config.uid = val[val.length - 1];
      isShowComponent.value = true;
    }
    formRef.value?.validate('config.uid');
  }, {
    deep: true,
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
      name: 'toolsSquare',
    });
  });
</script>
<style lang="postcss" scoped>
.create-tools-page {
  .flex-center {
    display: flex;
    align-items: center;
  }

  .chart-cascade {
    display: flex;
  }

  .vision-refresh {
    display: flex;
    margin-left: 10px;
    font-size: 18px;
    color: #87888f;
    cursor: pointer;
    transition: transform .3s ease;
    align-items: center;
    justify-content: center;

    &.rotating {
      animation: refresh 1s linear infinite;
    }
  }

  @keyframes refresh {
    from {
      transform: rotate(0deg);
    }

    to {
      transform: rotate(360deg);
    }
  }

  .permission {
    font-size: 12px;
    color: #e71818;

    .permission-link {
      color: #3a84ff;
      cursor: pointer;
    }
  }
}

</style>
