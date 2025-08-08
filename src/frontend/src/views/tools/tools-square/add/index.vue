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

              <bk-form-item
                :label="t('敏感定义')"
                label-width="160"
                property="radioGroupValue"
                required>
                <template #label>
                  <span
                    v-bk-tooltips="t('影响工具是否可公开申请或公开使用')"
                    style="border-bottom: 1px dashed #979ba5;">{{ t('敏感定义')
                    }}</span>
                </template>
                <bk-radio-group v-model="formData.radioGroupValue">
                  <bk-radio-button
                    v-for="radio in radioGroup"
                    :key="radio.id"
                    :label="radio.label" />
                </bk-radio-group>
                <div v-if="formData.radioGroupValue !== ''">
                  <bk-tag>
                    {{ formData.radioGroupValue === t('公开可申请') ? t('可申请权限后使用') : t('指定部分人可使用，不可被申请，指定人可看到并可使用') }}
                  </bk-tag>
                </div>
              </bk-form-item>

              <bk-form-item
                v-if="formData.radioGroupValue === t('仅指定人可用')"
                :label="t('可用人')"
                label-width="160"
                property="users"
                required>
                <audit-user-selector
                  v-model="formData.users"
                  :placeholder="t('请输入可用人')"
                  style="width: 50%;" />
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
                      :disabled="item.id === 'api' || route.name === 'toolsEdit'"
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
              <!-- bkvision 图表 -->
              <div v-else>
                <bk-form-item
                  :label="t('图表链接')"
                  label-width="160"
                  property="config.uid"
                  required>
                  <bk-input
                    v-model.trim="formData.config.uid"
                    :placeholder="t('请输入图表链接')"
                    style="width: 100%;" />
                </bk-form-item>

                <bk-form-item
                  :label="t('选择报表所在空间')"
                  label-width="160"
                  property="config.uid"
                  required>
                  <bk-input
                    v-model.trim="formData.config.uid"
                    :placeholder="t('请输入图表链接')"
                    style="width: 100%;" />
                </bk-form-item>
                <div style=" display: flex;align-items: center; width: 100%; justify-content: space-between; ">
                  <bk-form-item
                    :label="t('选择报表')"
                    label-width="160"
                    property="area"
                    required
                    style="width: 49.5%;">
                    <bk-cascader
                      v-model="formData.area"
                      :list="cascaderList"
                      :show-complete-name="false"
                      trigger="click" />
                  </bk-form-item>

                  <bk-form-item
                    :label="t('选择版本')"
                    label-width="160"
                    property="version"
                    required
                    style="width: 49.5%;">
                    <div style="display: flex;">
                      <bk-select
                        v-model="formData.bkVersion"
                        auto-focus
                        class="bk-select"
                        filterable
                        style="width: calc(100% - 50px)">
                        <bk-option
                          v-for="(item, index) in versionList"
                          :id="item.value"
                          :key="index"
                          :disabled="item.disabled"
                          :name="item.label" />
                      </bk-select>
                      <span style="width: 50px; color: #3a84ff; text-align: center; cursor: pointer;"> {{ t('查看')
                      }}</span>
                    </div>
                  </bk-form-item>
                </div>
              </div>
            </template>
          </card-part-vue>
          <card-part-vue
            :title="t('参数配置')"
            :title-description="t('BKVision仪表盘内中可供用户操作的选择器，此处配置为展示的默认值')">
            <template #content>
              <div style="display: flex;width: 100%; justify-content: space-between;">
                <bk-vision-component
                  v-for="comItem in componentList"
                  :key="comItem.id"
                  :config="comItem"
                  style="width: 49.5%" />
              </div>
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
                          boundary="parent"
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
                                <form-item
                                  ref="formItemRefs"
                                  :data-config="item"
                                  origin-model
                                  @change="(val: any) => handleFormItemChange(val, item)" />
                              </template>
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
                                @click="() => handleClick(index, item.drill_config)">
                                <template v-if="item.drill_config.tool.uid">
                                  <audit-icon
                                    style=" margin-right: 5px;font-size: 16px;"
                                    svg
                                    :type="iconMap[
                                      getToolNameAndType(item.drill_config.tool.uid).type as keyof typeof iconMap
                                    ]" />
                                  {{ getToolNameAndType(item.drill_config.tool.uid).name }}
                                  <audit-icon
                                    class="remove-btn"
                                    type="delete-fill"
                                    @click.stop="handleRemove(index)" />
                                  <audit-icon
                                    v-if="!(item.drill_config.tool.version
                                      >= (toolMaxVersionMap[item.drill_config.tool.uid] || 1))"
                                    v-bk-tooltips="{
                                      content: t('该工具已更新，请确认'),
                                    }"
                                    class="renew-tips"
                                    type="info-fill" />
                                </template>
                                <span
                                  v-else
                                  style="color: #c4c6cc;">
                                  {{ t('请配置') }}
                                </span>
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
        :all-tools-data="allToolsData"
        :new-tool-name="formData.name"
        :output-fields="formData.config.output_fields"
        :tag-data="originalTagData"
        @open-tool="handleOpenTool"
        @submit="handleFieldSubmit" />
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
  <!-- 循环所有工具 -->
  <div
    v-for="item in allToolsData"
    :key="item.uid">
    <component
      :is="DialogVue"
      :ref="(el: any) => dialogRefs[item.uid] = el"
      :tags-enums="originalTagData"
      @open-field-down="openFieldDown" />
  </div>
</template>

<script setup lang='ts'>
  import _ from 'lodash';
  import * as monaco from 'monaco-editor';
  import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import MetaManageService from '@service/meta-manage';
  import RootManageService from '@service/root-manage';
  import ToolManageService from '@service/tool-manage';

  import ConfigModel from '@model/root/config';
  import type ParseSqlModel from '@model/tool/parse-sql';
  import ToolDetailModel from '@model/tool/tool-detail';

  import useRouterBack from '@hooks/use-router-back';

  import { execCopy } from '@utils/assist';

  import DialogVue from '../components/dialog.vue';

  import AddEnum from './components/add-enum.vue';
  import BkVisionComponent from './components/bk-vision-components.vue';
  import CardPartVue from './components/card-part.vue';
  import EditSql from './components/edit-sql.vue';
  import fieldReference from './components/field-reference/index.vue';
  import Creating from './components/tool-status/creating.vue';
  import Failed from './components/tool-status/failed.vue';
  import Successful from './components/tool-status/Successful.vue';

  import ToolInfo from '@/domain/model/tool/tool-info';
  import useFullScreen from '@/hooks/use-full-screen';
  // import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';
  import FormItem from '@/views/tools/tools-square/components/form-item.vue';

  interface FormData {
    area?: string;
    bkVersion?: string;
    radioGroupValue?: string;
    users?: string[];
    name: string;
    tags: string[];
    description: string;
    tool_type: string;
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

  interface DrillDownItem {
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
  const radioGroup = ref([
    {
      id: '1',
      label: t('公开可申请'),
    },
    {
      id: '2',
      label: t('仅指定人可用'),
    }]);
  const viewRootRef = ref();
  const editSqlRef = ref();
  const formRef = ref();
  const tableInputFormRef = ref();
  const fieldReferenceRef = ref();
  const dialogVueRef = ref();
  const requiredListRef = ref();
  const addEnumRefs = ref();
  const formItemRefs = ref();
  const dialogRefs = ref<Record<string, any>>({});

  const loading = ref(false);
  const showEditSql = ref(false);
  const showFieldReference = ref(false);
  const showPreview = ref(false);

  const isCreating = ref(false);
  const isFailed = ref(false);
  const isSuccessful = ref(false);

  const strategyTagMap = ref<Record<string, string>>({});
  const toolMaxVersionMap = ref<Record<string, number>>({});
  const componentList = ref([
    {
      id: '1',
      type: 'userSelect',
      label: '用户选择',
    },
    {
      id: '2',
      type: 'input',
      label: '输入',
    },
  ]);
  const cascaderList = ref([
    {
      id: '1',
      name: '安全项目',
      disabled: true,
      children: [
        {
          id: '1-1-1',
          name: '旧业务',
        },
        {
          id: '1-1-2',
          name: '新业受运营报表',
          disabled: true,
        },
      ],
    },
    {
      id: '2',
      name: '数据调取工具',
    },
    {
      id: '3',
      name: '业受货币化相关',
      children: [
        {
          id: '3-1-1',
          name: '新业受运营报表',
          children: [
            {
              id: '3-1-1-1',
              name: '数据调取工具',
            },
            {
              id: '3-1-1-2',
              name: '光谱',
            },
            {
              id: '3-1-1-3',
              name: 'GBSS 单据汇总查询',
            },
          ],
        },
      ],
    },
  ]);
  const versionList = ref([
    {
      value: 'v11',
      label: 'v11',
    },
    {
      value: 'v12',
      label: 'v1.2',
    },
    {
      value: 'v1',
      label: 'v1',
    },
    {
      value: 'v19',
      label: 'v11',
      disabled: true,
    },
  ]);
  const formData = ref<FormData>({
    radioGroupValue: '',
    bkVersion: '1.0.0',
    area: '',
    users: [],
    name: '',
    tags: [],
    description: '',
    tool_type: 'bk_vision',
    data_search_config_type: 'sql',
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
  const originalTagData = ref<Array<{
    tag_id: string
    tag_name: string;
    tool_count: number;
  }>>([]);

  const frontendTypeList = ref<Array<{
    id: string;
    name: string;
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
    tips: t('暂未开放，敬请期待'),
  }, {
    id: 'bk_vision',
    name: t('bkvision图表'),
  }]);

  const iconMap = {
    data_search: 'sqlxiao',
    api: 'apixiao',
    bk_vision: 'bkvisonxiao',
  };

  const requiredList = ref([{
    id: true,
    label: t('是'),
  }, {
    id: false,
    label: t('否'),
  }]);
  const getSmartActionOffsetTarget = () => document.querySelector('.create-tools-page');


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
    data: tagData,
    loading: tagLoading,
  } = useRequest(ToolManageService.fetchToolTags, {
    defaultValue: [],
    manual: true,
    onSuccess: (data) => {
      // 字段下钻使用
      originalTagData.value = data;
      fetchAllTools();

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
      nextTick(() => {
        editor.setValue(formData.value.config.sql);
        formItemRefs.value.forEach((item: any, index: number) => {
          item?.setData(formData.value.config.input_variable[index].default_value);
        });
      });
    },
  });

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
        drill_config: {
          tool: { uid: '', version: 1 },
          config: [],
        },
      };
    });

    defineTheme();
    nextTick(() => {
      editor.setValue(sqlData.original_sql);
      formItemRefs.value.forEach((item: any, index: number) => {
        item?.setData(formData.value.config.input_variable[index].default_value);
      });
    });
  };

  const handleApply = () => {
    window.open(`${configData.value.third_party_system.bkbase_web_url}#/auth-center/permissions`);
  };

  const handleViewMore = (rtId: string) => {
    const prefix = rtId.split('_')[0];

    window.open(`${configData.value.third_party_system.bkbase_web_url}#/data-mart/data-dictionary/detail?dataType=result_table&result_table_id=${rtId}&bk_biz_id=${prefix}`);
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

  const handleFormItemChange = (val: any, item: FormData['config']['input_variable'][0]) => {
    const index = formData.value.config.input_variable.findIndex(i => i.raw_name === item.raw_name);
    if (index !== -1) {
      formData.value.config.input_variable[index].default_value = val;
    }
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

  const handleClick = (index: number, drillConfig?: FormData['config']['output_fields'][0]['drill_config']) => {
    showFieldReference.value = true;
    outputIndex.value = index;
    // 编辑
    if (drillConfig) {
      fieldReferenceRef.value.setFormData(drillConfig);
    }
  };

  // 下钻打开
  const openFieldDown = (drillDownItem: DrillDownItem, drillDownItemRowData: Record<any, string>) => {
    const { uid } = drillDownItem.drill_config.tool;
    const toolItem = allToolsData.value.find(item => item.uid === uid);
    if (!toolItem) {
      return;
    }

    const toolInfo = new ToolInfo(toolItem as any);
    if (dialogRefs.value[uid]) {
      dialogRefs.value[uid].openDialog(toolInfo, drillDownItem, drillDownItemRowData);
    }
  };

  // 打开工具
  const handleOpenTool = async (toolInfo: ToolDetailModel) => {
    if (dialogRefs.value[toolInfo.uid]) {
      dialogRefs.value[toolInfo.uid].openDialog(toolInfo.uid);
    }
  };

  // 删除值
  const handleRemove = (index: number) => {
    formData.value.config.output_fields[index] = {
      ...formData.value.config.output_fields[index],
      drill_config: {
        tool: { uid: '', version: 1 },
        config: [],
      },
    };
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
          right: 28px;
          z-index: 1;
          display: none;
          font-size: 12px;
          color: #c4c6cc;
          transition: all .15s;

          &:hover {
            color: #979ba5;
          }
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
