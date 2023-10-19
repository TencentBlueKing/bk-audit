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
  <div
    :class="classes"
    @click="handleClick">
    <slot />
  </div>
</template>
<script setup lang="ts">
  import {
    computed,
    inject,
    watch,
  } from 'vue';
  import { useRoute } from 'vue-router';

  import {
    type IMenuContext,
    menuKey,
  } from './common';

  interface Props {
    index: string;
  }

  const props = defineProps<Props>();

  const route = useRoute();

  const menu = inject(menuKey, {} as IMenuContext);

  const classes = computed(() => ({
    'audit-menu-item': true,
    active: props.index === menu.activeIndex.value,
  }));

  watch(route, (route) => {
    route.matched.forEach((curMatch) => {
      if (curMatch.name === props.index) {
        menu.activeIndex.value = props.index;
      }
    });
  }, {
    immediate: true,
  });


  const handleClick = () => {
    menu.change(props.index);
  };

</script>
