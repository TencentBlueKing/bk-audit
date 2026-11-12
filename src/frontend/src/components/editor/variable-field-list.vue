<template>
  <div class="variable-field-list">
    <bk-input
      v-model="searchKey"
      class="variable-field-list__search"
      clearable
      :placeholder="t('搜索变量名称')">
      <template #suffix>
        <audit-icon
          class="variable-field-list__search-icon"
          type="search1" />
      </template>
    </bk-input>
    <div
      v-if="filteredFields.length"
      class="variable-field-list__table">
      <div class="variable-field-list__row is-header">
        <span>{{ t('变量名称') }}</span>
        <span>{{ t('应用方式') }}</span>
        <span>{{ t('操作') }}</span>
      </div>
      <div
        v-for="item in filteredFields"
        :key="item.id"
        class="variable-field-list__row">
        <span class="variable-field-list__name">{{ item.name }}</span>
        <span class="variable-field-list__token">
          {{ tokenOf(item.id) }}
          <audit-icon
            class="variable-field-list__copy"
            type="copy"
            @click="handleCopy(item.id)" />
        </span>
        <button
          class="variable-field-list__insert"
          type="button"
          @click="handleInsert(item.id)">
          {{ t('插入') }}
        </button>
      </div>
    </div>
    <div
      v-else
      class="variable-field-list__empty">
      {{ t('暂无数据') }}
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import { encodeRegexp, execCopy } from '@utils/assist';

  interface VariableField {
    id: string;
    name: string;
  }

  interface Props {
    fields: VariableField[];
  }

  interface Emits {
    (e: 'insert', value: string): void;
  }

  const props = defineProps<Props>();
  const emit = defineEmits<Emits>();
  const { t } = useI18n();
  const searchKey = ref('');

  const tokenOf = (id: string) => `{{${id}}}`;

  const filteredFields = computed(() => {
    const keyword = searchKey.value.trim();
    if (!keyword) {
      return props.fields;
    }
    const rule = new RegExp(encodeRegexp(keyword), 'i');
    return props.fields.filter(item => rule.test(item.name) || rule.test(item.id));
  });

  const handleCopy = (id: string) => {
    execCopy(tokenOf(id), t('复制成功'));
  };

  const handleInsert = (id: string) => {
    emit('insert', tokenOf(id));
  };
</script>

<style lang="postcss" scoped>
.variable-field-list {padding: var(--bk-theme-space-16) var(--bk-theme-space-32) var(--bk-theme-space-24);
}

.variable-field-list__search {
  width: 100%;
  margin-bottom: var(--bk-theme-space-12);
}

.variable-field-list__search-icon {
  display: flex;
  font-size: 16px;
  color: var(--bk-theme-text-weak);
  align-items: center;
}

.variable-field-list__table {
  background: var(--bk-theme-surface-default);
  border: 1px solid var(--bk-theme-border-default);
  border-radius: var(--bk-theme-tag-radius);
}

.variable-field-list__row {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr) 80px;
  align-items: center;
  min-height: 42px;
  padding: 0 var(--bk-theme-space-16);
  font-size: 12px;
  line-height: 20px;
  color: var(--bk-theme-text-strong);
  border-top: 1px solid var(--bk-theme-border-default);
}

.variable-field-list__row.is-header {
  font-weight: 600;
  color: var(--bk-theme-text-strong);
  background: var(--bk-theme-surface-muted);
  border-top: none;
}

.variable-field-list__name,
.variable-field-list__token {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.variable-field-list__copy {
  margin-left: var(--bk-theme-space-6);
  color: var(--bk-theme-text-default);
  cursor: pointer;
}

.variable-field-list__copy:hover {
  color: var(--bk-theme-color-brand-2);
}

.variable-field-list__insert {
  padding: 0;
  font-size: 12px;
  line-height: 20px;
  color: var(--bk-theme-color-brand-2);
  cursor: pointer;
  background: transparent;
  border: none;
}

.variable-field-list__insert:hover {
  opacity: 80%;
}

.variable-field-list__empty {
  padding: var(--bk-theme-space-32) 0;
  font-size: 12px;
  color: var(--bk-theme-text-weak);
  text-align: center;
}
</style>
