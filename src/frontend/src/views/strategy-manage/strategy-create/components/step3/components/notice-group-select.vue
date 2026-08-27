<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
-->
<template>
  <bk-loading
    :loading="loading"
    style="width: 100%;">
    <bk-select
      v-model="localValue"
      class="bk-select"
      collapse-tags
      filterable
      :input-search="false"
      multiple
      multiple-mode="tag"
      :placeholder="t('请选择通知组')"
      :popover-options="{
        zIndex: 1000,
      }"
      :search-placeholder="t('请输入关键字')">
      <auth-option
        v-for="(item, index) in groupList"
        :key="index"
        action-id="list_notice_group_v2"
        :label="item.name"
        :permission="checkResultMap.list_notice_group_v2"
        resource-is-scene
        :value="item.id" />
      <template #extension>
        <div class="create-notice-group">
          <auth-router-link
            action-id="create_notice_group_v2"
            class="create_notice_group_v2"
            :permission="checkResultMap.create_notice_group_v2"
            resource-is-scene
            target="_blank"
            :to="{
              name: 'noticeGroupList',
              query: {
                create: true,
              },
            }">
            <audit-icon
              style="font-size: 14px;color: #3a84ff;"
              type="plus-circle" />
            {{ t('新增通知组') }}
          </auth-router-link>
        </div>
        <div
          class="refresh"
          @click="emits('refresh')">
          <audit-icon
            v-if="loading"
            class="rotate-loading"
            svg
            type="loading" />
          <template v-else>
            <audit-icon type="refresh" />
            {{ t('刷新') }}
          </template>
        </div>
      </template>
    </bk-select>
  </bk-loading>
</template>
<script setup lang="ts">
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface Props {
    modelValue: Array<string | number>;
    groupList: Array<{ id: string | number; name: string }>;
    checkResultMap: Record<string, boolean>;
    loading?: boolean;
  }

  interface Emits {
    (e: 'update:modelValue', value: Array<string | number>): void;
    (e: 'refresh'): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    loading: false,
  });
  const emits = defineEmits<Emits>();
  const { t } = useI18n();

  const localValue = computed({
    get: () => props.modelValue,
    set: value => emits('update:modelValue', value),
  });
</script>
<style lang="postcss" scoped>
.create-notice-group {
  padding: 0 12px;
  text-align: center;
  flex: 1;
}

.refresh {
  padding: 0 12px;
  color: #3a84ff;
  text-align: center;
  cursor: pointer;
  border-left: 1px solid #dcdee5;
  flex: 1;
}
</style>
