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
          :model="formData">
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
                    :placeholder="t('请输入，20字符内，可由汉字、小写字母、数字、“_”组成')"
                    show-word-limit
                    style="width: 100%;" />
                </bk-form-item>
                <bk-form-item
                  :label="t('标签')"
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
                        v-for="(item, index) in tagData"
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
                      :disabled="item.id === 'api'"
                      :label="item.id">
                      <span>{{ item.name }}</span>
                    </bk-radio>
                  </template>
                </bk-radio-group>
              </bk-form-item>
              <bk-form-item
                v-if="formData.tool_type === 'data_search'"
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
                  <bk-tag>
                    {{ t('用于复杂的 SQL 查询，先编写 SQL，再根据 SQL 内的结果与变量配置前端样式') }}
                  </bk-tag>
                </div>
              </bk-form-item>
              <bk-form-item
                v-else
                :label="t('图表链接')"
                label-width="160"
                property="config.uid"
                required>
                <bk-input
                  v-model.trim="formData.config.uid"
                  :placeholder="t('请输入图表链接')"
                  style="width: 100%;" />
              </bk-form-item>
            </template>
          </card-part-vue>
          <!-- 工具配置 -->
          <template v-if="formData.tool_type === 'data_search'">
            <card-part-vue :title="t('工具配置页面')">
              <template #content>
                <bk-form-item
                  :label="t('配置SQL')"
                  label-width="160">
                  <div class="sql-editor">
                    <div class="title">
                      <span style="margin-left: auto;">
                        <audit-icon
                          v-bk-tooltips="t('复制')"
                          class="icon"
                          type="copy"
                          @click.stop="handleCopy" />
                        <audit-icon
                          v-bk-tooltips="t('全屏')"
                          class="ml16 icon"
                          type="full-screen"
                          @click.stop="handleToggleFullScreen" />
                      </span>
                    </div>
                    <div
                      ref="viewRootRef"
                      class="sql-container"
                      :style="{height: '320px', width: '100%'}">
                      <audit-icon
                        v-if="showExit"
                        v-bk-tooltips="t('退出全屏')"
                        class="ml16 exit-icon"
                        type="un-full-screen-2"
                        @click="handleExitFullScreen" />
                      <bk-button
                        v-if="!showEditSql && !showFieldReference && !showPreview"
                        class="edit-icon"
                        outline
                        theme="primary"
                        @click="handleEditSql">
                        {{ t('编辑sql') }}
                      </bk-button>
                    </div>
                  </div>
                </bk-form-item>
                <bk-form-item
                  :label="t('可识别数据源')"
                  label-width="160">
                  <div
                    v-for="(item, index) in formData.config.referenced_tables"
                    :key="index"
                    class="data-source-item">
                    <div class="info">
                      <audit-icon
                        style="margin: 0 5px; color: #c4c6cc;"
                        type="lock" />
                      <a href="xxx">{{ item.table_name }}</a>
                    </div>
                    <auth-button
                      v-if="!item.hasPermission"
                      action-id="xxx"
                      :permission="false"
                      resource="xxx"
                      text
                      theme="primary">
                      {{ t('申请权限') }}
                    </auth-button>
                  </div>
                </bk-form-item>
                <bk-form-item
                  :label="t('查询输入设置')"
                  label-width="160">
                  <div class="render-field">
                    <div class="field-header-row">
                      <div class="field-value">
                        {{ t('字段名') }}
                      </div>
                      <div class="field-value">
                        {{ t('显示名') }}
                      </div>
                      <div
                        class="field-value"
                        style="flex: 0 0 380px;">
                        {{ t('字段说明') }}
                      </div>
                      <div class="field-value">
                        {{ t('是否必填') }}
                      </div>
                      <div class="field-value is-required">
                        {{ t('前端类型') }}
                      </div>
                    </div>
                    <audit-form
                      ref="tableInputFormRef"
                      form-type="vertical"
                      :model="formData">
                      <template
                        v-for="(item, index) in formData.config.input_variable"
                        :key="index">
                        <div class="field-row">
                          <div class="field-value">
                            <bk-form-item
                              error-display-type="tooltips"
                              label=""
                              label-width="0">
                              <bk-input
                                ref="fieldItemRef"
                                v-model="item.raw_name"
                                :disabled="!formData.config.sql"
                                :placeholder="!formData.config.sql ? t('请先配置sql'):t('请输入')" />
                            </bk-form-item>
                          </div>
                          <div class="field-value">
                            <bk-form-item
                              error-display-type="tooltips"
                              label=""
                              label-width="0">
                              <bk-input
                                ref="fieldItemRef"
                                v-model="item.display_name"
                                :disabled="!formData.config.sql"
                                :placeholder="!formData.config.sql ? t('请先配置sql'):t('请输入')" />
                            </bk-form-item>
                          </div>
                          <div
                            class="field-value"
                            style="flex: 0 0 380px;">
                            <bk-form-item
                              error-display-type="tooltips"
                              label=""
                              label-width="0">
                              <bk-input
                                ref="fieldItemRef"
                                v-model="item.description"
                                :disabled="!formData.config.sql"
                                :placeholder="!formData.config.sql ? t('请先配置sql'):t('请输入')" />
                            </bk-form-item>
                          </div>
                          <div class="field-value">
                            <bk-form-item
                              error-display-type="tooltips"
                              label=""
                              label-width="0">
                              <bk-radio-group
                                v-model="item.required"
                                :disabled="!formData.config.sql"
                                style="padding: 0 8px;">
                                <bk-radio label>
                                  <span>{{ t('是') }}</span>
                                </bk-radio>
                                <bk-radio :label="false ">
                                  <span>{{ t('否') }}</span>
                                </bk-radio>
                              </bk-radio-group>
                            </bk-form-item>
                          </div>
                          <div class="field-value">
                            <bk-form-item
                              error-display-type="tooltips"
                              label=""
                              label-width="0"
                              :property="`config.input_variable[${index}].field_category`"
                              required>
                              <bk-select
                                v-model="item.field_category"
                                class="bk-select"
                                :disabled="!formData.config.sql"
                                filterable
                                :input-search="false"
                                :placeholder="!formData.config.sql ? t('请先配置sql'):t('请选择')"
                                :search-placeholder="t('请输入关键字')">
                                <bk-option
                                  v-for="(selectItem, selectIndex) in frontendTypeList"
                                  :key="selectIndex"
                                  :label="selectItem.name"
                                  :value="selectItem.id" />
                              </bk-select>
                            </bk-form-item>
                          </div>
                        </div>
                      </template>
                    </audit-form>
                  </div>
                </bk-form-item>
                <bk-form-item
                  :label="t('查询结果设置')"
                  label-width="160">
                  <div class="render-field">
                    <div class="field-header-row">
                      <div class="field-value">
                        {{ t('字段名') }}
                      </div>
                      <div class="field-value">
                        {{ t('显示名') }}
                      </div>
                      <div
                        class="field-value"
                        style="flex: 0 0 380px;">
                        {{ t('字段说明') }}
                      </div>
                      <div class="field-value">
                        {{ t('字段下钻') }}
                      </div>
                    </div>
                    <audit-form
                      ref="tableOutputFormRef"
                      form-type="vertical"
                      :model="formData">
                      <template
                        v-for="(item, index) in formData.config.output_fields"
                        :key="index">
                        <div class="field-row">
                          <div class="field-value">
                            <bk-form-item
                              error-display-type="tooltips"
                              label=""
                              label-width="0">
                              <bk-input
                                ref="fieldItemRef"
                                v-model="item.raw_name"
                                :disabled="!formData.config.sql"
                                :placeholder="!formData.config.sql ? t('请先配置sql'):t('请输入')" />
                            </bk-form-item>
                          </div>
                          <div class="field-value">
                            <bk-form-item
                              error-display-type="tooltips"
                              label=""
                              label-width="0">
                              <bk-input
                                ref="fieldItemRef"
                                v-model="item.display_name"
                                :disabled="!formData.config.sql"
                                :placeholder="!formData.config.sql ? t('请先配置sql'):t('请输入')" />
                            </bk-form-item>
                          </div>
                          <div
                            class="field-value"
                            style="flex: 0 0 380px;">
                            <bk-form-item
                              error-display-type="tooltips"
                              label=""
                              label-width="0">
                              <bk-input
                                ref="fieldItemRef"
                                v-model="item.description"
                                :disabled="!formData.config.sql"
                                :placeholder="!formData.config.sql ? t('请先配置sql'):t('请输入')" />
                            </bk-form-item>
                          </div>
                          <div class="field-value">
                            <bk-form-item
                              error-display-type="tooltips"
                              label=""
                              label-width="0">
                              <div
                                v-if="!item.drill_config.tool.uid"
                                style="padding: 0 8px; color: #c4c6cc; cursor: pointer;"
                                @click="() => handleClick(index)">
                                {{ !formData.config.sql ? t('请先配置sql'):t('请配置') }}
                              </div>
                              <div
                                v-else
                                style="padding: 0 8px; cursor: pointer;"
                                @click="() => handleClick(index, item.drill_config)">
                                {{ getToolName(item.drill_config.tool.uid) }}
                              </div>
                            </bk-form-item>
                          </div>
                        </div>
                      </template>
                    </audit-form>
                  </div>
                </bk-form-item>
              </template>
            </card-part-vue>
          </template>
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
      <!-- 编辑sql -->
      <edit-sql
        ref="editSqlRef"
        v-model:showEditSql="showEditSql"
        @update-parse-sql="handleUpdateParseSql" />
      <!-- 字段下钻 -->
      <field-reference
        ref="fieldReferenceRef"
        v-model:showFieldReference="showFieldReference"
        :new-tool-name="formData.name"
        :output-fields="formData.config.output_fields"
        @submit="handleFieldSubmit"
        @update-all-tools-data="handleAllToolsData" />
    </smart-action>
  </skeleton-loading>
  <dialog-vue
    ref="dialogVueRef"
    :tags-enums="tagData"
    @close="handleClose" />
  <creating v-if="isCreating" />
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

<script setup lang='ts'>
  import _ from 'lodash';
  import * as monaco from 'monaco-editor';
  import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import MetaManageService from '@service/meta-manage';
  import ToolManageService from '@service/tool-manage';

  import type ParseSqlModel from '@model/tool/parse-sql';
  import ToolDetailModel from '@model/tool/tool-detail';

  import useRouterBack from '@hooks/use-router-back';

  import { execCopy } from '@utils/assist';

  import DialogVue from '../components/dialog.vue';

  import CardPartVue from './components/card-part.vue';
  import EditSql from './components/edit-sql.vue';
  import fieldReference from './components/field-reference.vue';
  import Creating from './components/tool-status/creating.vue';
  import Failed from './components/tool-status/failed.vue';
  import Successful from './components/tool-status/Successful.vue';

  import useFullScreen from '@/hooks/use-full-screen';
  // import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';

  interface FormData {
    name: string;
    tags: string[];
    description: string;
    tool_type: string;
    data_search_config_type: string;
    config: {
      referenced_tables: Array<{
        table_name: string | null;
        alias: string | null;
        hasPermission: boolean;
      }>;
      input_variable: Array<{
        raw_name: string;
        display_name: string;
        description: string;
        required: boolean;
        field_category: string;
      }>
      output_fields: Array<{
        raw_name: string;
        display_name: string;
        description: string;
        drill_config: {
          tool: {
            uid: string;
            version: number;
          };
          config: Array<{
            source_field: string;
            target_value_type: string;
            target_value: string;
          }>
        };
      }>
      sql: string;
      uid: string;
    };
  }

  let editor: monaco.editor.IStandaloneCodeEditor;
  const searchTypeList = [{
    label: '简易模式',
    value: 'simple',
    disabled: true,
  }, {
    label: 'SQL模式',
    value: 'sql',
  }];

  const route = useRoute();
  const router = useRouter();
  // const { messageSuccess } = useMessage();
  const { t } = useI18n();
  const { showExit, handleScreenfull } = useFullScreen(
    () => editor,
    () => viewRootRef.value,
  );
  const isEditMode = route.name === 'toolsEdit';

  const viewRootRef = ref();
  const editSqlRef = ref();
  const formRef = ref();
  const tableInputFormRef = ref();
  const fieldReferenceRef = ref();
  const dialogVueRef = ref();

  const loading = ref(false);
  const showEditSql = ref(false);
  const showFieldReference = ref(false);
  const showPreview = ref(false);

  const isCreating = ref(false);
  const isFailed = ref(false);
  const isSuccessful = ref(false);

  const strategyTagMap = ref<Record<string, string>>({});
  const formData = ref<FormData>({
    name: '',
    tags: [],
    description: '',
    tool_type: 'data_search',
    data_search_config_type: 'sql',
    config: {
      referenced_tables: [],
      input_variable: [{
        raw_name: '',
        display_name: '',
        description: '',
        required: false,
        field_category: '',
      }],
      output_fields: [{
        raw_name: '',
        display_name: '',
        description: '',
        drill_config: {
          tool: {
            uid: '',
            version: 1,
          },
          config: [],
        },
      }],
      sql: '',
      uid: '',
    },
  });

  const outputIndex = ref(-1);
  const allToolsData = ref<Array<ToolDetailModel>>([]);

  const frontendTypeList = ref<Array<{
    id: string;
    name: string;
  }>>([]);

  const toolTypeList = ref<Array<{
    id: string;
    name: string;
  }>>([]);

  const getSmartActionOffsetTarget = () => document.querySelector('.create-tools-page');

  // 获取前端类型
  useRequest(MetaManageService.fetchGlobalChoices, {
    defaultValue: {},
    manual: true,
    onSuccess(result) {
      frontendTypeList.value = result.FieldCategory;
      toolTypeList.value = result.ToolType;
    },
  });

  // 获取标签列表
  const {
    data: tagData,
    loading: tagLoading,
  } = useRequest(ToolManageService.fetchToolTags, {
    defaultValue: [],
    manual: true,
    onSuccess: (data) => {
      tagData.value = data.reduce((res, item) => {
        if (item.tag_id !== '-2') {
          res.push({
            tag_id: item.tag_id,
            tag_name: item.tag_name,
            tool_count: item.tool_count,
          });
        }
        return res;
      }, [] as Array<{
        tag_id: string;
        tag_name: string
        tool_count: number
      }>);
      data.forEach((item) => {
        strategyTagMap.value[item.tag_id] = item.tag_name;
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
      formData.value = data;
      editor.setValue(formData.value.config.sql);
    },
  });

  const handleUpdateParseSql = (sqlData?: ParseSqlModel) => {
    if (!sqlData) return;
    formData.value.config.sql = sqlData.original_sql;
    formData.value.config.referenced_tables = sqlData.referenced_tables;
    formData.value.config.input_variable = sqlData.sql_variables.map(item => ({
      ...item,
      field_category: '',
    }));
    formData.value.config.output_fields = sqlData.result_fields.map(item => ({
      ...item,
      description: '',
      drill_config: {
        tool: {
          uid: '',
          version: 1,
        },
        config: [],
      },
    }));

    defineTheme();
    editor.setValue(sqlData.original_sql);
  };

  // 实现全屏
  const handleToggleFullScreen = () => {
    handleScreenfull();
  };

  // 退出全屏
  const handleExitFullScreen = () => {
    handleScreenfull();
  };

  const handleEditSql = () => {
    showEditSql.value = true;
    if (formData.value.config.sql) {
      editSqlRef.value.setEditorValue(formData.value.config.sql);
    }
  };

  const handleCopy = () => {
    execCopy(formData.value.config.sql, t('复制成功'));
  };

  const handleClick = (index: number, drillConfig?: FormData['config']['output_fields'][0]['drill_config']) => {
    showFieldReference.value = true;
    outputIndex.value = index;
    // 编辑
    if (drillConfig) {
      fieldReferenceRef.value.setFormData(drillConfig);
    }
  };

  // const handlePreview = () => {
  //   const tastQueue = [formRef.value.validate()];
  //   if (tableInputFormRef.value) {
  //     tastQueue.push(tableInputFormRef.value.validate());
  //   }
  //   // 校验后再预览
  //   Promise.all(tastQueue).then(() => {
  //     showPreview.value = true;
  //     dialogVueRef.value.openDialog({
  //       ...formData.value,
  //       permission: {
  //         use_tool: true,
  //       },
  //     }, false, {}, true);
  //   });
  // };

  const handleClose = () => {
    showPreview.value = false;
  };

  const handleCancel = () => {
    router.push({
      name: 'toolsSquare',
    });
  };

  const handleModifyAgain = () => {
    isFailed.value = false;
  };

  const handleFieldSubmit = (drillConfig: FormData['config']['output_fields'][0]['drill_config']) => {
    formData.value.config.output_fields[outputIndex.value].drill_config = drillConfig;
  };

  const handleAllToolsData = (data: Array<ToolDetailModel>) => {
    allToolsData.value = data;
  };

  const getToolName = (uid: string) => {
    const tool = allToolsData.value.find(item => item.uid === uid);
    return tool ? tool.name : '';
  };

  // 提交
  const handleSubmit = () => {
    const tastQueue = [formRef.value.validate()];
    if (tableInputFormRef.value) {
      tastQueue.push(tableInputFormRef.value.validate());
    }

    Promise.all(tastQueue).then(() => {
      isCreating.value = true;

      const data = _.cloneDeep(formData.value);
      const service = isEditMode ? ToolManageService.updateTool : ToolManageService.createTool;

      if (data.tags) {
        data.tags = data.tags.map(item => (strategyTagMap.value[item] ? strategyTagMap.value[item] : item));
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

  const defineTheme = () => {
    monaco.editor.defineTheme('sqlView', {
      base: 'vs', // 以哪个默认主题为基础："vs" | "vs-dark" | "hc-black" | "hc-light"
      inherit: true,
      rules: [
        { token: 'identifier', foreground: '#d06733' },
        { token: 'number', foreground: '#6bbeeb', fontStyle: 'italic' },
        { token: 'keyword', foreground: '#05a4d5' },
      ],
      colors: {
        'scrollbarSlider.background': '#eeeff2', // 滚动条背景
        'editor.foreground': '#0d0b09', // 基础字体颜色
        'editor.background': '#fbfbfc', // 背景颜色
        'editorCursor.foreground': '#d4b886', // 焦点颜色
        'editor.lineHighlightBackground': '#6492a520', // 焦点所在的一行的背景颜色
        'editorLineNumber.foreground': '#008800', // 行号字体颜色
      },
    });

    monaco.editor.setTheme('sqlView');
  };

  const initEditor = () => {
    editor = monaco.editor.create(viewRootRef.value, {
      value: formData.value.config.sql,
      language: 'sql',
      theme: 'vs',
      minimap: {
        enabled: true,
      },
      automaticLayout: true,
      wordWrap: 'bounded',
      readOnly: true,
    });
    editor.layout();
  };

  watch(showEditSql, (val) => {
    if (!val) {
      defineTheme();
    }
  });

  onMounted(() => {
    initEditor();
    defineTheme();
    if (isEditMode) {
      fetchToolsDetail({
        uid: route.params.id,
      });
    }
  });

  onBeforeUnmount(() => {
    editor.dispose();
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

  .sql-editor {
    min-width: 800px;
    line-height: 40px;

    .title {
      display: flex;
      height: 40px;
      padding: 0 25px;
      font-size: 14px;
      color: #c4c6cc;
      background: #fbfbfc;

      .icon {
        font-size: 16px;
        cursor: pointer;
      }
    }

    .sql-container {
      position: relative;

      .edit-icon {
        position: absolute;
        top: 50%;
        left: 50%;
        z-index: 10000;
        transform: translate(-50%, -50%);
      }

      .exit-icon {
        position: absolute;
        top: 10px;
        right: 20px;
        z-index: 11111;
        font-size: 20px;
        color: #c4c6cc;
        cursor: pointer;
      }
    }
  }

  .data-source-item {
    display: grid;
    grid-template-columns: 1fr 50px;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;

    .info {
      flex: 1;
      background-color: #f5f7fa;
    }
  }

  .render-field {
    display: flex;
    min-width: 640px;
    overflow: hidden;
    border: 1px solid #dcdee5;
    border-radius: 2px;
    user-select: none;
    flex-direction: column;
    flex: 1;

    .field-select {
      width: 40px;
      text-align: center;
      background: #fafbfd;
    }

    .field-operation {
      width: 170px;
      padding-left: 16px;
      background: #fafbfd;
      border-left: 1px solid #dcdee5;
    }

    :deep(.field-value) {
      display: flex;
      flex: 1;

      /* width: 180px; */
      overflow: hidden;
      border-left: 1px solid #dcdee5;
      align-items: center;

      .bk-form-item.is-error {
        .bk-input--text {
          background-color: #ffebeb;
        }
      }

      .bk-form-item {
        width: 100%;
        margin-bottom: 0;

        .bk-input {
          height: 42px;
          border: none;
        }

        .bk-input.is-focused:not(.is-readonly) {
          border: 1px solid #3a84ff;
          outline: 0;
          box-shadow: 0 0 3px #a3c5fd;
        }

        .bk-form-error-tips {
          top: 12px
        }
      }
    }


    .field-header-row {
      display: flex;
      height: 42px;
      font-size: 12px;
      line-height: 40px;
      color: #313238;
      background: #f0f1f5;

      .field-value {
        padding-left: 8px;
      }

      .field-value.is-required {
        &::after {
          margin-left: 4px;
          color: red;
          content: '*';
        }
      }

      .field-select,
      .field-operation {
        background: #f0f1f5;
      }
    }

    .field-row {
      display: flex;
      overflow: hidden;
      font-size: 12px;
      line-height: 42px;
      color: #63656e;
      border-top: 1px solid #dcdee5;
    }
  }
}
</style>

