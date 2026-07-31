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
  <teleport to=".sec-chat-main">
    <div
      v-if="isShow"
      class="log-statistics-overlay"
      @click.self="handleClose">
      <div class="log-statistics-modal">
        <div class="modal-header">
          <h4 class="modal-title">
            数据统计
          </h4>
          <div
            class="modal-close"
            @click="handleClose">
            <audit-icon type="close" />
          </div>
        </div>

        <div class="modal-body">
          <p class="subtitle">
            请选择需要统计的字段
          </p>
          <bk-input
            v-model="keyword"
            class="search-input"
            clearable
            placeholder="搜索字段名称">
            <template #suffix>
              <audit-icon
                class="search-icon"
                type="search1" />
            </template>
          </bk-input>

          <div class="field-groups">
            <div
              v-for="group in filteredGroups"
              :key="group.key"
              class="field-group">
              <div class="group-title">
                {{ group.label }}（{{ group.fields.length }}）
              </div>
              <div class="field-grid-wrap">
                <div class="field-grid">
                  <button
                    v-for="field in group.fields"
                    :key="field"
                    class="field-pill"
                    :class="{ 'is-selected': selectedFields.includes(field) }"
                    type="button"
                    @click="toggleField(field)">
                    {{ field }}
                  </button>
                </div>
              </div>
            </div>
            <div
              v-if="!filteredGroups.length"
              class="field-empty">
              暂无匹配字段
            </div>
          </div>

          <div class="divider-wrapper">
            <div class="divider-line" />
            <div class="divider-text">
              以上报告不满足需求？
            </div>
            <div class="divider-line" />
          </div>

          <div class="custom-section">
            <div
              class="custom-header"
              @click="customExpanded = !customExpanded">
              <audit-icon
                class="collapse-icon"
                :type="customExpanded ? 'angle-fill-down' : 'angle-fill-rignt'" />
              <span class="custom-title">自定义统计</span>
              <span class="custom-desc">（输入任意内容，AI为您定制报告）</span>
            </div>
            <div
              v-show="customExpanded"
              class="custom-content">
              <div class="custom-input-wrapper">
                <bk-input
                  v-model="customPrompt"
                  class="custom-input"
                  placeholder="输入你想统计的内容，例如：分析张三在英雄联盟业务的资产转移报告"
                  :rows="3"
                  type="textarea" />
              </div>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <bk-button
            class="confirm-btn"
            :disabled="!canConfirm"
            theme="primary"
            @click="handleConfirm">
            确定
          </bk-button>
          <bk-button @click="handleClose">
            取消
          </bk-button>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script lang="ts" setup>
  import { computed, ref, watch } from 'vue';

  const props = withDefaults(defineProps<{
    modelValue?: boolean;
  }>(), {
    modelValue: false,
  });

  const emit = defineEmits<{
    'update:modelValue': [value: boolean];
    confirm: [payload: { fields: string[]; customPrompt?: string }];
  }>();

  const COMMON_FIELDS = [
    '操作起始时间', '操作人', '操作人账号类型', '来源系统', '操作结果',
    '操作途径', '来源IP', '事件ID', '请求ID',
  ];

  const EXTEND_FIELDS = [
    '请求路径', '空间ID', '资源实例', '动作标识', '客户端类型',
    '浏览器', '操作系统', '业务ID', '项目ID', '环境类型',
    '接口版本', '请求方法', '状态码', '耗时', '扩展字段1',
    '扩展字段2', '扩展字段3', '扩展字段4', '扩展字段5', '扩展字段6',
  ];

  const isShow = ref(false);
  const keyword = ref('');
  const selectedFields = ref<string[]>([]);
  const customExpanded = ref(false);
  const customPrompt = ref('');

  watch(() => props.modelValue, (val) => {
    isShow.value = val;
    if (val) {
      keyword.value = '';
      selectedFields.value = [];
      customExpanded.value = false;
      customPrompt.value = '';
    }
  });

  watch(isShow, (val) => {
    if (val !== props.modelValue) emit('update:modelValue', val);
  });

  const filterFields = (fields: string[]) => {
    const key = keyword.value.trim().toLowerCase();
    if (!key) return fields;
    return fields.filter(item => item.toLowerCase().includes(key));
  };

  const filteredGroups = computed(() => {
    const groups = [
      { key: 'common', label: '通用字段', fields: filterFields(COMMON_FIELDS) },
      { key: 'extend', label: '拓展字段', fields: filterFields(EXTEND_FIELDS) },
    ];
    return groups.filter(item => item.fields.length);
  });

  const canConfirm = computed(() => (
    selectedFields.value.length > 0 || !!customPrompt.value.trim()
  ));

  const toggleField = (field: string) => {
    const idx = selectedFields.value.indexOf(field);
    if (idx === -1) selectedFields.value.push(field);
    else selectedFields.value.splice(idx, 1);
  };

  const handleClose = () => {
    isShow.value = false;
  };

  const handleConfirm = () => {
    if (!canConfirm.value) return;
    emit('confirm', {
      fields: [...selectedFields.value],
      customPrompt: customPrompt.value.trim() || undefined,
    });
    handleClose();
  };
</script>

<style lang="postcss" scoped>
  .log-statistics-overlay {
    position: absolute;
    inset: 0;
    z-index: 100;
    display: flex;
    padding: 24px;
    overflow: auto;
    background: rgb(0 0 0 / 40%);
    box-sizing: border-box;
    align-items: center;
    justify-content: center;
  }

  .log-statistics-modal {
    display: flex;
    width: 680px;
    max-width: 100%;
    max-height: calc(100% - 48px);
    margin: auto;
    overflow: hidden;
    background: #fff;
    border-radius: 2px;
    box-shadow: 0 4px 12px rgb(0 0 0 / 15%);
    flex-direction: column;
  }

  .modal-header {
    display: flex;
    height: 52px;
    padding: 0 24px;
    flex-shrink: 0;
    align-items: center;
    justify-content: space-between;
    box-sizing: border-box;

    .modal-title {
      margin: 0;
      font-size: 20px;
      font-weight: 700;
      line-height: 28px;
      color: #313238;
    }

    .modal-close {
      display: flex;
      width: 32px;
      height: 32px;
      margin-right: -8px;
      font-size: 18px;
      color: #979ba5;
      cursor: pointer;
      border-radius: 2px;
      align-items: center;
      justify-content: center;

      &:hover {
        color: #63656e;
        background: #eaebf0;
      }
    }
  }

  .modal-body {
    padding: 0 24px 8px;
    overflow: auto;
    flex: 1;
  }

  .subtitle {
    margin: 0 0 12px;
    font-size: 12px;
    line-height: 20px;
    color: #63656e;
  }

  .search-input {
    margin-bottom: 16px;

    .search-icon {
      margin-right: 8px;
      font-size: 16px;
      color: #c4c6cc;
    }
  }

  .field-group {
    margin-bottom: 16px;

    .group-title {
      margin-bottom: 8px;
      font-size: 12px;
      font-weight: 700;
      line-height: 20px;
      color: #313238;
    }
  }

  .field-grid-wrap {
    /* 每组最多展示 5 行（2 列），超出滚动：5*32 + 4*8 = 192 */
    max-height: 192px;
    overflow: auto;
    scrollbar-width: thin;
    scrollbar-color: #dcdee5 transparent;

    &::-webkit-scrollbar {
      width: 4px;
    }

    &::-webkit-scrollbar-thumb {
      background: #dcdee5;
      border-radius: 2px;
    }
  }

  .field-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .field-pill {
    height: 32px;
    padding: 0 12px;
    overflow: hidden;
    font-size: 12px;
    line-height: 30px;
    color: #63656e;
    text-align: left;
    text-overflow: ellipsis;
    white-space: nowrap;
    cursor: pointer;
    background: #f5f7fa;
    border: 1px solid transparent;
    border-radius: 2px;
    box-sizing: border-box;

    &:hover {
      color: #3a84ff;
    }

    &.is-selected {
      color: #3a84ff;
      background: #f0f5ff;
      border-color: #3a84ff;
    }
  }

  .field-empty {
    padding: 24px 0;
    font-size: 12px;
    color: #c4c6cc;
    text-align: center;
  }

  .divider-wrapper {
    display: flex;
    margin: 16px 0;
    align-items: center;

    .divider-line {
      height: 1px;
      background: #dcdee5;
      flex: 1;
    }

    .divider-text {
      padding: 0 16px;
      font-size: 12px;
      color: #979ba5;
    }
  }

  .custom-section {
    .custom-header {
      display: flex;
      cursor: pointer;
      user-select: none;
      align-items: center;

      .collapse-icon {
        margin-right: 6px;
        font-size: 16px;
        color: #979ba5;
      }

      .custom-title {
        font-size: 14px;
        font-weight: 700;
        color: #313238;
      }

      .custom-desc {
        font-size: 12px;
        color: #979ba5;
      }
    }

    .custom-content {
      margin-top: 12px;
    }

    .custom-input-wrapper {
      border: 1px solid #dcdee5;
      border-radius: 2px;
      transition: all .2s;

      &:focus-within {
        background: linear-gradient(white, white) padding-box,
          linear-gradient(90deg, #a469ff 0%, #1cc2fe 100%) border-box;
        border-color: transparent;
      }

      .custom-input {
        background: transparent;
        border: none;
        box-shadow: none;

        :deep(.bk-textarea) {
          min-height: 80px;
          background: transparent;
          border: none;
          resize: none;
        }
      }
    }
  }

  .modal-footer {
    display: flex;
    height: 56px;
    padding: 0 24px;
    background: #fafbfd;
    border-top: 1px solid #dcdee5;
    flex-shrink: 0;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
    box-sizing: border-box;

    .confirm-btn {
      min-width: 64px;
    }
  }
</style>
