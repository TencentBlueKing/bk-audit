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
        :style="{ height: '320px', width: '100%' }">
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
          :type="item.permission.result ? 'unlock' : 'lock'" />
        <span
          v-if="!item.permission.result"
          :style="!item.permission.result ? {
            color: '#c4c6cc',
          } : {}">{{ item.table_name }}</span>
        <bk-button
          v-else
          text
          theme="primary"
          @click="handleViewMore(item.table_name || '')">
          {{ item.table_name }}
        </bk-button>
      </div>
      <bk-button
        v-if="!item.permission.result"
        text
        theme="primary"
        @click="handleApply">
        {{ t('申请权限') }}
      </bk-button>
    </div>
  </bk-form-item>
  <!-- 输入 -->
  <bk-form-item
    :label="t('查询输入设置')"
    label-width="160">
    <div class="render-field">
      <div class="field-header-row">
        <div class="field-value">
          {{ t('变量名') }}
        </div>
        <div class="field-value">
          {{ t('显示名') }}
        </div>
        <div
          class="field-value"
          style="flex: 0 0 350px;">
          {{ t('变量名说明') }}
        </div>
        <div
          class="field-value"
          style="flex: 0 0 200px;">
          {{ t('是否必填') }}
          <bk-popover
            ref="requiredListRef"
            allow-html
            content="#hidden_pop_content"
            ext-cls="field-required-pop"
            placement="top"
            theme="light"
            trigger="click"
            width="100">
            <audit-icon
              style="margin-left: 4px; font-size: 16px;color: #3a84ff; cursor: pointer;"
              type="piliangbianji" />
          </bk-popover>
          <div style="display: none">
            <div id="hidden_pop_content">
              <div
                v-for="(item, index) in requiredList"
                :key="index"
                class="field-required-item"
                @click="handleRequiredClick(item.id)">
                {{ item.label }}
              </div>
            </div>
          </div>
        </div>
        <div
          class="field-value is-required"
          style="flex: 0 0 200px;">
          {{ t('前端类型') }}
        </div>
        <div class="field-value">
          {{ t('默认值') }}
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
                  disabled
                  :placeholder="!formData.config.sql ? t('请先配置sql') : t('请输入')" />
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
                  :placeholder="!formData.config.sql ? t('请先配置sql') : t('请输入')" />
              </bk-form-item>
            </div>
            <div
              class="field-value"
              style="flex: 0 0 350px;">
              <bk-form-item
                error-display-type="tooltips"
                label=""
                label-width="0">
                <bk-input
                  ref="fieldItemRef"
                  v-model="item.description"
                  :disabled="!formData.config.sql"
                  :placeholder="!formData.config.sql ? t('请先配置sql') : t('请输入')" />
              </bk-form-item>
            </div>
            <div
              class="field-value"
              style="flex: 0 0 200px;">
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
                  <bk-radio :label="false">
                    <span>{{ t('否') }}</span>
                  </bk-radio>
                </bk-radio-group>
              </bk-form-item>
            </div>
            <div
              class="field-value"
              style="flex: 0 0 200px;">
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
                  :placeholder="!formData.config.sql ? t('请先配置sql') : t('请选择')"
                  :search-placeholder="t('请输入关键字')"
                  @change="(value: string) => handleFieldCategoryChange(value, index)">
                  <bk-option
                    v-for="(selectItem, selectIndex) in frontendTypeList"
                    :key="selectIndex"
                    :label="selectItem.name"
                    :value="selectItem.id" />
                </bk-select>
                <template v-if="item.field_category === 'multiselect'">
                  <bk-button
                    class="add-enum"
                    text
                    theme="primary"
                    @click="handleAddEnum(index)">
                    {{ t('配置选项') }}
                  </bk-button>
                </template>
                <add-enum
                  ref="addEnumRefs"
                  @update-choices="(value: Array<{
                                key: string,
                                name: string
                  }>) => handleUpdateChoices(value, index)" />
              </bk-form-item>
            </div>
            <div class="field-value">
              <bk-form-item
                error-display-type="tooltips"
                label=""
                label-width="0"
                :property="`config.input_variable[${index}].target_value`">
                <template v-if="!item.field_category">
                  <bk-input
                    disabled
                    :placeholder="t('请先配置前端类型')" />
                </template>
                <template v-else>
                  <!-- 不同前端类型 -->
                  <tool-form-item
                    :data-config="item"
                    origin-model
                    :target-value="item.default_value"
                    @change="(val: any) => handleFormItemChange(val, item)" />
                </template>
              </bk-form-item>
            </div>
          </div>
        </template>
      </audit-form>
    </div>
  </bk-form-item>
  <!-- 输出 -->
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
        <div class="field-value">
          <span
            v-bk-tooltips="t('为储存值配置可读的展示文本')"
            class="tips"
            style="line-height: 16px;">
            {{ t('字段值映射') }}
          </span>
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
                  disabled
                  :placeholder="!formData.config.sql ? t('请先配置sql') : t('请输入')" />
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
                  :placeholder="!formData.config.sql ? t('请先配置sql') : t('请输入')" />
              </bk-form-item>
            </div>
            <div class="field-value">
              <bk-form-item
                error-display-type="tooltips"
                label=""
                label-width="0">
                <bk-input
                  v-if="!formData.config.sql"
                  disabled
                  :placeholder="t('请先配置sql')" />
                <div
                  v-else
                  class="field-value-div"
                  @click="() => handleFiledDict(index, item.enum_mappings)"
                  @mouseleave="() => handleMappingsMouseLeave(index)">
                  <span
                    :style="{
                      color: item.enum_mappings.mappings.length ? '#63656e' : '#c4c6cc',
                      cursor: 'pointer',
                      marginLeft: '8px',
                    }">{{ item.enum_mappings.mappings.length ? t('已配置') : t('请点击配置') }}</span>
                  <audit-popconfirm
                    v-if="item.enum_mappings.mappings.length"
                    :ref="(el: any) => mappingsPopconfirmRefs[index] = el"
                    :confirm-handler="() => handleRemoveMappings(index)"
                    :content="t('删除操作无法撤回，请谨慎操作！')"
                    :title="t('确认删除该配置？')"
                    @hide="() => handleMappingsPopconfirmHide(index)">
                    <audit-icon
                      class="remove-mappings-btn remove-btn"
                      :class="{ 'is-popconfirm-visible': mappingsPopconfirmVisible[index] }"
                      type="delete-fill"
                      @click="() => handleMappingsPopconfirmShow(index)" />
                  </audit-popconfirm>
                </div>
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
                  :placeholder="!formData.config.sql ? t('请先配置sql') : t('请输入')" />
              </bk-form-item>
            </div>
            <div class="field-value">
              <bk-form-item
                error-display-type="tooltips"
                label=""
                label-width="0">
                <bk-input
                  v-if="!formData.config.sql"
                  disabled
                  :placeholder="t('请先配置sql')" />
                <div
                  v-else
                  class="field-value-div"
                  @mouseleave="() => handleDrillMouseLeave(index)">
                  <template v-if="item.drill_config.length && item.drill_config.every(item => item.tool.uid)">
                    <bk-popover
                      placement="top"
                      theme="black">
                      <span
                        @click="() => handleClick(index, item.raw_name, item.drill_config)">
                        {{ t('已配置') }}
                        <span style="color: #3a84ff;">{{ item.drill_config.length }}</span>
                        {{ t('个工具') }}
                      </span>
                      <template #content>
                        <div>
                          <div
                            v-for="config in item.drill_config"
                            :key="config.tool.uid">
                            {{ getToolNameAndType(config.tool.uid).name }}
                          </div>
                        </div>
                      </template>
                    </bk-popover>
                    <!-- 删除 -->
                    <audit-popconfirm
                      :ref="(el: any) => drillPopconfirmRefs[index] = el"
                      class="ml8"
                      :confirm-handler="() => handleRemove(index)"
                      :content="t('移除操作无法撤回，请谨慎操作！')"
                      :title="t('确认移除以下工具？')"
                      @hide="() => handleDrillPopconfirmHide(index)">
                      <audit-icon
                        class="remove-btn"
                        :class="{ 'is-popconfirm-visible': drillPopconfirmVisible[index] }"
                        type="delete-fill"
                        @click="() => handleDrillPopconfirmShow(index)" />
                      <template #content>
                        <bk-table
                          ref="refTable"
                          :columns="columns"
                          :data="item.drill_config"
                          height="auto"
                          max-height="100%"
                          show-overflow-tooltip
                          stripe />
                      </template>
                    </audit-popconfirm>
                    <bk-popover
                      v-if="item.drill_config
                        .some(drill => !(drill.tool.version >= (toolMaxVersionMap[drill.tool.uid] || 1)))"
                      placement="top"
                      theme="black">
                      <audit-icon
                        class="renew-tips"
                        type="info-fill" />
                      <template #content>
                        <div>
                          <div>{{ t('以下工具已更新，请确认：') }}</div>
                          <div
                            v-for="drill in item.drill_config
                              .filter(drill => !(drill.tool.version >= (toolMaxVersionMap[drill.tool.uid] || 1)))"
                            :key="drill.tool.uid">
                            {{ getToolNameAndType(drill.tool.uid).name }}
                          </div>
                        </div>
                      </template>
                    </bk-popover>
                  </template>
                  <span
                    v-else
                    style="color: #c4c6cc;"
                    @click="() => handleClick(index, item.raw_name)">
                    {{ t('请点击配置') }}
                  </span>
                </div>
              </bk-form-item>
            </div>
          </div>
        </template>
      </audit-form>
    </div>
  </bk-form-item>

  <!-- 编辑sql -->
  <edit-sql
    ref="editSqlRef"
    v-model:showEditSql="showEditSql"
    @update-parse-sql="handleUpdateParseSql" />
  <!-- 字段下钻 -->
  <field-reference
    ref="fieldReferenceRef"
    v-model:showFieldReference="showFieldReference"
    :all-tools-data="allToolsData"
    :new-tool-name="name"
    :output-fields="formData.config.output_fields"
    :tag-data="toolTagData"
    @open-tool="handleOpenTool"
    @refresh-tool-list="handleRefreshToolList"
    @submit="handleFieldSubmit" />
  <!-- 字段映射 -->
  <field-dict
    ref="fieldDictRef"
    v-model:showFieldDict="showFieldDict"
    :edit-data="enumMappingsData"
    @submit="handleDictSubmit" />
  <!-- 循环所有工具 -->
  <div
    v-for="item in allOpenToolsData"
    :key="item">
    <component
      :is="DialogVue"
      :ref="(el:any) => dialogRefs[item] = el"
      :all-tools-data="allToolsData"
      :tags-enums="toolTagData"
      @open-field-down="openFieldDown" />
  </div>
</template>
<script setup lang='tsx'>
  import type { Column } from 'bkui-vue/lib/table/props';
  import _ from 'lodash';
  import * as monaco from 'monaco-editor';
  import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import MetaManageService from '@service/meta-manage';
  import RootManageService from '@service/root-manage';
  import ToolManageService from '@service/tool-manage';

  import ConfigModel from '@model/root/config';
  import type ParseSqlModel from '@model/tool/parse-sql';

  // import ToolDetailModel from '@model/tool/tool-detail';
  import { execCopy } from '@utils/assist';

  import DialogVue from '../../../../components/dialog.vue';
  import AddEnum from '../components/add-enum.vue';
  import editSql from '../components/edit-sql.vue';
  import FieldReference from '../components/field-reference/index.vue';

  // import ToolInfo from '@/domain/model/tool/tool-info';
  import useFullScreen from '@/hooks/use-full-screen';
  import useRequest from '@/hooks/use-request';
  import { useToolDialog } from '@/hooks/use-tool-dialog';
  import fieldDict from '@/views/strategy-manage/strategy-create/components/step2/components/event-table/field-dict.vue';
  import ToolFormItem from '@/views/tools/tools-square/components/tool-form-item.vue';

  interface Props {
    name: string
    uid: string
  }

  interface FormData {
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
        default_value: string | Array<string>;
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


  interface Exposes {
    getValue: () => Promise<any>;
    setConfigs: (data: FormData['config']) => void;
    getFields: () => FormData['config'];
  }

  const props = defineProps<Props>();

  let editor: monaco.editor.IStandaloneCodeEditor;
  const viewRootRef = ref();
  const editSqlRef = ref();
  const requiredListRef = ref();
  const addEnumRefs = ref();
  const fieldReferenceRef = ref();
  const tableInputFormRef = ref();

  // 使用工具对话框hooks
  const {
    allOpenToolsData,
    dialogRefs,
    openFieldDown,
    handleOpenTool,
  } = useToolDialog();

  // const loading = ref(false);
  const showEditSql = ref(false);
  const showFieldReference = ref(false);
  const showFieldDict = ref(false);
  const showPreview = ref(false);

  const { t } = useI18n();
  const { showExit, handleScreenfull } = useFullScreen(
    () => editor,
    () => viewRootRef.value,
  );


  const formData = ref<FormData>({
    config: {
      referenced_tables: [],
      input_variable: [{
        raw_name: '',
        display_name: '',
        description: '',
        required: false,
        field_category: '',
        default_value: '',
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
      uid: '',
    },
  });

  const requiredList = ref([{
    id: true,
    label: t('是'),
  }, {
    id: false,
    label: t('否'),
  }]);

  const frontendTypeList = ref<Array<{
    id: string;
    name: string;
  }>>([]);

  // const iconMap = {
  //   data_search: 'sqlxiao',
  //   api: 'apixiao',
  //   bk_vision: 'bkvisonxiao',
  // };

  const columns = [{
    label: () => t('工具列表'),
    render: ({ data }: {data: FormData['config']['output_fields'][0]['drill_config'][0]}) => <div>{getToolNameAndType(data.tool.uid).name}</div>,
  }] as Column[];

  // 字段下钻使用index
  const outputIndex = ref(-1);
  // 字段映射使用index
  const enumIndex = ref(-1);
  const enumMappingsData = ref<Array<{
    key: string;
    name: string;
  }>>([]);

  const toolMaxVersionMap = ref<Record<string, number>>({});

  // 气泡框状态管理
  const mappingsPopconfirmRefs = ref<Record<number, any>>({});
  const drillPopconfirmRefs = ref<Record<number, any>>({});
  const mappingsPopconfirmVisible = ref<Record<number, boolean>>({});
  const drillPopconfirmVisible = ref<Record<number, boolean>>({});

  const {
    data: configData,
  } = useRequest(RootManageService.config, {
    defaultValue: new ConfigModel(),
    manual: true,
  });

  // 获取前端类型
  useRequest(MetaManageService.fetchGlobalChoices, {
    defaultValue: {},
    manual: true,
    onSuccess(result) {
      frontendTypeList.value = result.FieldCategory;
    },
  });

  // 获取所有工具
  const {
    data: allToolsData,
    run: fetchAllTools,
  } = useRequest(ToolManageService.fetchAllTools, {
    defaultValue: [],
    onSuccess: (data) => {
      toolMaxVersionMap.value = data.reduce((res, item) => {
        res[item.uid] = item.version;
        return res;
      }, {} as Record<string, number>);
    },
  });

  // 获取标签列表
  const {
    data: toolTagData,
  } = useRequest(ToolManageService.fetchToolTags, {
    defaultValue: [],
    manual: true,
    onSuccess: () => {
      fetchAllTools();
    },
  });

  const handleCopy = () => {
    execCopy(formData.value.config.sql, t('复制成功'));
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
      editSqlRef.value.setEditorValue(formData.value.config.sql, props.uid);
    }
  };

  const handleViewMore = (rtId: string) => {
    const prefix = rtId.split('_')[0];

    window.open(`${configData.value.third_party_system.bkbase_web_url}#/data-mart/data-dictionary/detail?dataType=result_table&result_table_id=${rtId}&bk_biz_id=${prefix}`);
  };

  const handleApply = () => {
    window.open(`${configData.value.third_party_system.bkbase_web_url}#/auth-center/permissions`);
  };

  const handleRequiredClick = (value: boolean) => {
    if (formData.value.config.input_variable.length === 0) {
      return;
    }
    formData.value.config.input_variable = formData.value.config.input_variable.map(item => ({
      ...item,
      required: value,
    }));
    requiredListRef.value?.hide();
  };

  const handleFieldCategoryChange = (value: string, index: number) => {
    formData.value.config.input_variable[index].default_value = '';
    if (value !== 'enum') {
      formData.value.config.input_variable[index].choices = [];
    }
  };

  const handleAddEnum = (index: number) => {
    // 编辑带上值
    const currentChoices = formData.value.config.input_variable[index].choices;
    addEnumRefs.value[index].show(currentChoices);
  };

  const handleUpdateChoices = (value: Array<{
    key: string
    name: string
  }>, index: number) => {
    formData.value.config.input_variable[index].choices = value;
  };

  const handleFormItemChange = (val: any, item: FormData['config']['input_variable'][0]) => {
    const index = formData.value.config.input_variable.findIndex(i => i.raw_name === item.raw_name);
    if (index !== -1) {
      // 检查值是否真的变化了，避免循环触发
      const currentValue = formData.value.config.input_variable[index].default_value;
      if (_.isEqual(currentValue, val)) {
        return;
      }
      formData.value.config.input_variable[index].default_value = val;
    }
  };

  const handleFiledDict = (index: number, enumMappings?: FormData['config']['output_fields'][0]['enum_mappings']) => {
    enumIndex.value = index;
    showFieldDict.value = true;
    if (enumMappings) {
      enumMappingsData.value = enumMappings.mappings;
    }
  };

  // 字段值映射气泡框显示/隐藏处理
  const handleMappingsPopconfirmShow = (index: number) => {
    mappingsPopconfirmVisible.value[index] = true;
  };

  const handleMappingsPopconfirmHide = (index: number) => {
    mappingsPopconfirmVisible.value[index] = false;
  };

  const handleMappingsMouseLeave = (index: number) => {
    // 如果气泡框未显示，则关闭气泡框
    if (mappingsPopconfirmRefs.value[index] && !mappingsPopconfirmVisible.value[index]) {
      mappingsPopconfirmRefs.value[index].hide();
    }
  };

  const handleRemoveMappings = async (index: number) => {
    formData.value.config.output_fields[index].enum_mappings = {
      collection_id: '',
      mappings: [],
    };
  };

  const handleClick = (index: number, activeFieldName: string, drillConfig?: FormData['config']['output_fields'][0]['drill_config']) => {
    showFieldReference.value = true;
    outputIndex.value = index;
    fieldReferenceRef.value.setActiveFieldName(activeFieldName);
    // 编辑
    if (drillConfig) {
      fieldReferenceRef.value.setFormData(drillConfig);
    }
  };

  const getToolNameAndType = (uid: string) => {
    const tool = allToolsData.value.find(item => item.uid === uid);
    return tool ? {
      name: tool.name,
      type: tool.tool_type,
    } : {
      name: '',
      type: '',
    };
  };

  // 字段下钻气泡框显示/隐藏处理
  const handleDrillPopconfirmShow = (index: number) => {
    drillPopconfirmVisible.value[index] = true;
  };

  const handleDrillPopconfirmHide = (index: number) => {
    drillPopconfirmVisible.value[index] = false;
  };

  const handleDrillMouseLeave = (index: number) => {
    // 如果气泡框未显示，则关闭气泡框
    if (drillPopconfirmRefs.value[index] && !drillPopconfirmVisible.value[index]) {
      drillPopconfirmRefs.value[index].hide();
    }
  };

  // 删除值
  const  handleRemove = async (index: number) => {
    formData.value.config.output_fields[index].drill_config = [];
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

  const handleUpdateParseSql = (sqlData?: ParseSqlModel) => {
    if (!sqlData) return;
    formData.value.config.sql = sqlData.original_sql;
    formData.value.config.referenced_tables = sqlData.referenced_tables;

    // 更新 input_variable
    const oldInputMap = new Map(formData.value.config.input_variable.map(item => [item.raw_name, item]));
    formData.value.config.input_variable = sqlData.sql_variables.map((newItem) => {
      const existing = oldInputMap.get(newItem.raw_name);
      if (existing) {
        return existing;
      }
      return {
        ...newItem,
        field_category: '',
        default_value: '',
        choices: [],
      };
    });

    // 更新 output_fields
    const oldOutputMap = new Map(formData.value.config.output_fields.map(item => [item.raw_name, item]));
    formData.value.config.output_fields = sqlData.result_fields.map((newItem) => {
      const existing = oldOutputMap.get(newItem.raw_name);
      // 如果已有记录，保留用户填写的额外字段
      if (existing) {
        return existing;
      }
      // 新记录则初始化额外字段
      return {
        ...newItem,
        description: '',
        drill_config: [],
        enum_mappings: {
          collection_id: '',
          mappings: [],
        },
      };
    });

    defineTheme();
    nextTick(() => {
      editor.setValue(sqlData.original_sql);
    });
  };

  const handleRefreshToolList = () => {
    fetchAllTools();
  };

  const handleFieldSubmit = (drillConfig: FormData['config']['output_fields'][0]['drill_config']) => {
    formData.value.config.output_fields[outputIndex.value].drill_config = drillConfig;
  };

  const handleDictSubmit = (data: FormData['config']['output_fields'][0]['enum_mappings']['mappings']) => {
    formData.value.config.output_fields[enumIndex.value].enum_mappings.mappings = data;
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

  watch(() => showEditSql.value, (val) => {
    if (!val) {
      defineTheme();
    }
  });

  onMounted(() => {
    initEditor();
    defineTheme();
  });

  onBeforeUnmount(() => {
    editor.dispose();
  });

  defineExpose<Exposes>({
    getValue() {
      return tableInputFormRef.value.validate();
    },
    setConfigs(configs: FormData['config']) {
      formData.value.config = configs;
      // 设置sql编辑器
      editor.setValue(configs.sql);
    },
    getFields() {
      return formData.value.config;
    },
  });
</script>
<style lang="postcss" scoped>
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
      z-index: 2;
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
  display: flex;

  /* grid-template-columns: 1fr 50px; */
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

    .field-value-div {
      display: flex;
      padding: 0 8px;
      cursor: pointer;
      align-items: center;

      &:hover {
        .remove-btn {
          display: block;
        }
      }

      .remove-btn {
        position: absolute;
        top: 36%;
        right: 28px;
        z-index: 1;
        display: none;
        font-size: 12px;
        color: #c4c6cc;
        transition: all .15s;

        &:hover {
          color: #979ba5;
        }

        &.is-popconfirm-visible {
          display: block;
        }
      }

      .remove-mappings-btn {
        top: 40%;
        right: 8px;
      }

      .renew-tips {
        position: absolute;
        right: 8px;
        font-size: 14px;
        color: #3a84ff;
      }
    }

    .bk-form-item.is-error {
      .bk-input--text {
        background-color: #ffebeb;
      }
    }

    .bk-form-item {
      width: 100%;
      margin-bottom: 0;

      .bk-input,
      .bk-date-picker-editor,
      .bk-select-trigger,
      .bk-select-tag,
      .date-picker {
        height: 42px !important;
        border: none;
      }

      .icon-wrapper {
        top: 6px;
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

    .add-enum {
      position: absolute;
      top: 14px;
      right: 28px;
      cursor: pointer;
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
</style>
<style lang="postcss">
.field-required-pop {
  padding: 5px 0 !important;

  .field-required-item {
    position: relative;
    display: flex;
    min-height: 32px;
    padding: 0 12px;
    overflow: hidden;
    color: #63656e;
    text-align: left;
    text-overflow: ellipsis;
    white-space: nowrap;
    cursor: pointer;
    user-select: none;
    align-items: center;

    &:hover {
      background-color: #f5f7fa;
    }
  }
}
</style>
