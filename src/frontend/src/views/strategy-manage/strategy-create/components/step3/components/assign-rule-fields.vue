<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
-->
<template>
  <div class="assign-rule-fields">
    <div class="form-section">
      <div class="form-label is-required">
        {{ t('分派至场景空间') }}
      </div>
      <bk-select
        v-model="localValue.scene_ids"
        collapse-tags
        filterable
        multiple
        multiple-mode="tag"
        :placeholder="t('请选择')">
        <bk-option
          v-for="item in sceneOptions"
          :key="item.id"
          :label="item.name"
          :value="item.id" />
      </bk-select>
    </div>

    <div class="form-section form-section-row">
      <div class="form-section-col">
        <div class="form-label is-required">
          {{ t('风险单处理人') }}
        </div>
        <notice-group-select
          v-model="localValue.processors"
          :check-result-map="checkResultMap"
          :group-list="groupList"
          :loading="groupLoading"
          @refresh="emits('refreshGroupList')" />
      </div>
      <div class="form-section-col">
        <div class="form-label">
          {{ t('关注人') }}
        </div>
        <notice-group-select
          v-model="localValue.notice_users"
          :check-result-map="checkResultMap"
          :group-list="groupList"
          :loading="groupLoading"
          @refresh="emits('refreshGroupList')" />
      </div>
    </div>

    <div class="form-section">
      <div class="form-label">
        {{ t('风险单分派方式') }}
      </div>
      <bk-radio-group v-model="localValue.assign_mode">
        <bk-radio label="confirm">
          {{ t('确认后分派') }}
        </bk-radio>
        <bk-radio label="direct">
          {{ t('直接分派') }}
        </bk-radio>
      </bk-radio-group>
    </div>

    <div
      v-if="localValue.assign_mode === 'confirm'"
      class="form-section">
      <div class="form-label is-required">
        {{ t('确认人') }}
      </div>
      <notice-group-select
        v-model="localValue.confirmers"
        :check-result-map="checkResultMap"
        :group-list="groupList"
        :loading="groupLoading"
        @refresh="emits('refreshGroupList')" />
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';

  import NoticeGroupSelect from './notice-group-select.vue';

  interface RuleFields {
    scene_ids: Array<string | number>;
    processors: Array<string | number>;
    notice_users: Array<string | number>;
    assign_mode: 'confirm' | 'direct';
    confirmers: Array<string | number>;
  }

  interface Props {
    modelValue: RuleFields;
    sceneOptions: Array<{ id: string | number; name: string }>;
    groupList: Array<{ id: string | number; name: string }>;
    checkResultMap: Record<string, boolean>;
    groupLoading?: boolean;
  }

  interface Emits {
    (e: 'update:modelValue', value: RuleFields): void;
    (e: 'refreshGroupList'): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    groupLoading: false,
  });
  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  const localValue = computed({
    get: () => props.modelValue,
    set: value => emits('update:modelValue', value),
  });
</script>
<style lang="postcss" scoped>
.assign-rule-fields {
  .form-section {
    margin-bottom: 20px;

    &:last-child {
      margin-bottom: 0;
    }
  }

  .form-section-row {
    display: flex;
    gap: 16px;
  }

  .form-section-col {
    flex: 1;
    min-width: 0;
  }

  .form-label {
    margin-bottom: 8px;
    font-size: 12px;
    color: #63656e;

    &.is-required::before {
      display: inline-block;
      width: 8px;
      color: #ea3636;
      text-align: center;
      content: '*';
    }
  }
}
</style>
