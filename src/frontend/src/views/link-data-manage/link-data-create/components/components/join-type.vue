<template>
  <bk-popover
    ext-cls="link-data-join-type"
    placement="bottom"
    theme="light"
    trigger="click">
    <relation-ship :join-type="joinType" />
    <template #content>
      <div
        v-for="type in joinTypeList"
        :key="type"
        class="join-type-list"
        :class="[type === joinType ? 'active' : '']"
        @click="() => handleSelectJoinType(type)">
        <relation-ship
          :height="10"
          :join-type="type"
          style="margin-right: 5px;"
          :width="10" />
        <span>{{ type }}</span>
      </div>
    </template>
  </bk-popover>
</template>
<script setup lang="ts">
  const joinType = defineModel<string>('joinType', {
    default: 'left_join',
  });

  const joinTypeList = ['left_join', 'right_join', 'inner_join', 'full_outer_join'];

  const handleSelectJoinType = (type: string) => {
    joinType.value = type;
  };
</script>
<style scoped lang="postcss">
.join-type-list {
  display: flex;
  align-items: center;
  padding: 12px;
  cursor: pointer;

  &:hover {
    background-color: #f5f7fa;
  }
}

.active {
  color: #3a84ff;
  background-color: #e1ecff;
}
</style>
<style>
.link-data-join-type {
  padding: 4px 0 !important;
}
</style>
