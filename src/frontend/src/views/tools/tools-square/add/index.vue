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
    fullscreen
    :loading="loading"
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
                  :label="t('策略名称')"
                  label-width="160"
                  property="tool_name"
                  style="flex: 1;">
                  <bk-input
                    v-model.trim="formData.tool_name"
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
                        :label="item.name"
                        :value="item.id" />
                    </bk-select>
                  </bk-loading>
                </bk-form-item>
              </div>
              <bk-form-item
                :label="t('工具说明')"
                label-width="160"
                property="description">
                <bk-input
                  v-model.trim="formData.description"
                  autosize
                  :maxlength="100"
                  :placeholder="t('请输入说明')"
                  show-word-limit
                  style="width: 50%;"
                  type="textarea" />
              </bk-form-item>
              <bk-form-item
                :label="t('敏感定义')"
                label-width="160"
                property="scoped">
                <bk-button-group>
                  <bk-button
                    v-for="item in scopedList"
                    :key="item.value"
                    :selected="formData.scoped === item.value"
                    @click="handleSelected(item.value)">
                    {{ item.label }}
                  </bk-button>
                </bk-button-group>
                <bk-tag style="display: block; width: 120px;">
                  {{ t('可申请权限后使用') }}
                </bk-tag>
              </bk-form-item>
            </template>
          </card-part-vue>
          <card-part-vue :title="t('工具类型')">
            <template #content>
              <bk-form-item
                :label="t('工具类型')"
                label-width="160"
                property="toolType">
                <bk-radio-group
                  v-model="formData.toolType"
                  @change="handleToolTypeChange">
                  <bk-radio label="search_data">
                    <span>{{ t('数据查询') }}</span>
                  </bk-radio>
                  <bk-radio
                    disabled
                    label="API">
                    <span>{{ t('API接口') }}</span>
                  </bk-radio>
                  <bk-radio label="bkvision">
                    <span>{{ t('bkvision图表') }}</span>
                  </bk-radio>
                </bk-radio-group>
              </bk-form-item>
              <bk-form-item
                v-if="formData.toolType === 'search_data'"
                :label="t('配置方式')"
                label-width="160"
                property="searchType">
                <bk-button-group>
                  <bk-button
                    v-for="item in searchTypeList"
                    :key="item.value"
                    :disabled="item.disabled"
                    :selected="formData.searchType === item.value"
                    @click="handleSelectedSearchType(item.value)">
                    {{ item.label }}
                  </bk-button>
                </bk-button-group>
                <bk-tag style="display: block; width: 460px;">
                  {{ t('用于复杂的 SQL 查询，先编写 SQL，再根据 SQL 内的结果与变量配置前端样式') }}
                </bk-tag>
              </bk-form-item>
              <bk-form-item
                v-else
                :label="t('图表链接')"
                label-width="160"
                property="chart_link"
                required>
                <bk-input
                  v-model.trim="formData.chart_link"
                  :placeholder="t('请输入图表链接')"
                  style="width: 100%;" />
              </bk-form-item>
            </template>
          </card-part-vue>
          <template v-if="formData.toolType === 'search_data'">
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
                          type="copy" />
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
                        v-if="!showEditSql"
                        class="edit-icon"
                        outline
                        theme="primary"
                        @click="() => showEditSql = true">
                        {{ t('编辑sql') }}
                      </bk-button>
                    </div>
                  </div>
                </bk-form-item>
                <bk-form-item
                  :label="t('可识别数据源')"
                  label-width="160">
                  <div
                    v-for="(item, index) in identifiableDataSource"
                    :key="index"
                    class="data-source-item">
                    <div class="info">
                      <audit-icon
                        style="margin: 0 5px; color: #c4c6cc;"
                        type="un-full-screen-2" />
                      <a href="xxx">{{ item.label }}</a>
                    </div>
                    <bk-button
                      v-if="!item.hasPermission"
                      text
                      theme="primary">
                      {{ t('申请权限') }}
                    </bk-button>
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
                      <div class="field-value">
                        {{ t('前端类型') }}
                      </div>
                    </div>
                    <audit-form
                      ref="tableFormRef"
                      form-type="vertical"
                      :model="formData">
                      <template
                        v-for="(item, index) in formData.inputData"
                        :key="index">
                        <div class="field-row">
                          <div class="field-value">
                            <bk-form-item
                              error-display-type="tooltips"
                              label=""
                              label-width="0">
                              <bk-input
                                ref="fieldItemRef"
                                v-model="item.field_name" />
                            </bk-form-item>
                          </div>
                          <div class="field-value">
                            <bk-form-item
                              error-display-type="tooltips"
                              label=""
                              label-width="0">
                              <bk-input
                                ref="fieldItemRef"
                                v-model="item.display_name" />
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
                                v-model="item.description" />
                            </bk-form-item>
                          </div>
                          <div class="field-value">
                            <bk-form-item
                              error-display-type="tooltips"
                              label=""
                              label-width="0">
                              <bk-radio-group
                                v-model="item.required_choice"
                                style="padding: 0 8px;">
                                <bk-radio label="required ">
                                  <span>{{ t('是') }}</span>
                                </bk-radio>
                                <bk-radio label="optional ">
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
                              :property="`renderData[${index}].frontend_type`"
                              required>
                              <bk-select
                                v-model="item.frontend_type"
                                class="bk-select"
                                filterable
                                :input-search="false"
                                :placeholder="t('请选择')"
                                :search-placeholder="t('请输入关键字')">
                                <bk-option
                                  v-for="(selectItem, selectIndex) in frontendTypeList"
                                  :key="selectIndex"
                                  :label="selectItem.label"
                                  :value="selectItem.value" />
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
                      ref="tableFormRef"
                      form-type="vertical"
                      :model="formData">
                      <template
                        v-for="(item, index) in formData.outputData"
                        :key="index">
                        <div class="field-row">
                          <div class="field-value">
                            <bk-form-item
                              error-display-type="tooltips"
                              label=""
                              label-width="0">
                              <bk-input
                                ref="fieldItemRef"
                                v-model="item.field_name" />
                            </bk-form-item>
                          </div>
                          <div class="field-value">
                            <bk-form-item
                              error-display-type="tooltips"
                              label=""
                              label-width="0">
                              <bk-input
                                ref="fieldItemRef"
                                v-model="item.display_name" />
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
                                v-model="item.description" />
                            </bk-form-item>
                          </div>
                          <div class="field-value">
                            <bk-form-item
                              error-display-type="tooltips"
                              label=""
                              label-width="0">
                              <bk-select
                                v-model="item.field_down"
                                class="bk-select"
                                filterable
                                :input-search="false"
                                :placeholder="t('请选择')"
                                :search-placeholder="t('请输入关键字')">
                                <bk-option
                                  v-for="(selectItem, selectIndex) in frontendTypeList"
                                  :key="selectIndex"
                                  :label="selectItem.label"
                                  :value="selectItem.value" />
                              </bk-select>
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
          {{ t('创建') }}
        </bk-button>
        <bk-button
          class="ml8"
          @click="handleCancel">
          {{ t('取消') }}
        </bk-button>
        <bk-button
          class="ml8"
          style="margin-left: 48px;"
          @click="handlePreview">
          {{ t('预览测试') }}
        </bk-button>
      </template>
      <edit-sql
        ref="editSqlRef"
        v-model:showEditSql="showEditSql" />
    </smart-action>
  </skeleton-loading>
  <!-- <creating /> -->
  <!-- <failed /> -->
  <!-- <successful /> -->
</template>

<script setup lang='ts'>
  import * as monaco from 'monaco-editor';
  import { onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import CardPartVue from './components/card-part.vue';
  import EditSql from './components/edit-sql.vue';
  // import Creating from './components/tool-status/creating.vue';
  // import Failed from './components/tool-status/failed.vue';
  // import Successful from './components/tool-status/Successful.vue';

  let editor: monaco.editor.IStandaloneCodeEditor;

  const { t } = useI18n();
  const viewRootRef = ref();

  const loading = ref(false);
  const formData = ref({
    tool_name: '',
    tags: [],
    description: '',
    scoped: '',
    toolType: 'search_data',
    searchType: '',
    chart_link: '',
    inputData: [{
      field_name: '',
      display_name: '',
      description: '',
      required_choice: '',
      frontend_type: '',
    }],
    outputData: [{
      field_name: '',
      display_name: '',
      description: '',
      field_down: '',
    }],
  });
  const tagLoading = ref(false);
  const tagData = ref([{
    name: '标签1',
    id: 1,
  }]);
  const scopedList = ref([{
    label: '公开可申请',
    value: 'not_sensitive',
  }, {
    label: '仅指定人可用',
    value: 'sensitive',
  }]);
  const searchTypeList = ref([{
    label: '简易模式',
    value: 'simple',
    disabled: true,
  }, {
    label: 'SQL模式',
    value: 'sql',
  }]);
  const identifiableDataSource = ref([{
    label: '12131231',
    value: '1',
    hasPermission: true,
  }, {
    label: 'rw4e5tsedfae',
    value: '2',
    hasPermission: false,
  }]);
  const frontendTypeList = ref([{
    label: '12131231',
    value: '1',
  }, {
    label: 'rw4e5tsedfae',
    value: '2',
  }]);
  const showExit = ref(false);
  const showEditSql = ref(false);

  const getSmartActionOffsetTarget = () => document.querySelector('create-tools-page');

  const handleSelected = (value: string) => {
    formData.value.scoped = value;
  };

  const handleToolTypeChange = (value: string) => {
    formData.value.toolType = value;
  };

  const handleSelectedSearchType = (value: string) => {
    formData.value.searchType = value;
  };

  // 实现全屏
  const handleToggleFullScreen = () => {
    console.log('toggle full screen');
  };

  const handleExitFullScreen = () => {
    console.log('exit full screen');
  };

  const handleReize = () => {
    editor.layout();
  };

  const handleSubmit = () => {
    console.log('submit');
  };

  const handleCancel = () => {
    console.log('cancel');
  };

  const handlePreview = () => {
    console.log('preview');
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
    window.addEventListener('resize', handleReize);
  };

  onMounted(() => {
    initEditor();
    defineTheme();
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

