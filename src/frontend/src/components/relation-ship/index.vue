<template>
  <div class="table-relation-circle">
    <div
      class="circle-left-join"
      :style="circleLeft" />
    <div
      class="circle-right-join"
      :style="circleRight" />
    <div
      class="circle-inner-join"
      :style="InnerJoin" />
  </div>
</template>
<script setup lang="ts">
  import { computed, reactive, watch } from 'vue';

  interface Props {
    joinType: string
    active?: boolean,
    type?: 'gray' | 'normal',
    width?: number,
    height?: number,
  }

  const props = withDefaults(defineProps<Props>(), {
    width: 20,
    height: 20,
    type: 'normal',
    active: false,
  });

  const grayColor = computed(() => (props.active ? 'rgb(163, 197, 254)' : 'rgb(220, 222, 229)'));
  const grayBorderColor = computed(() => (props.active ? 'rgb(23, 104, 239)' : 'rgb(151, 155, 165)'));

  const circleLeft = reactive({
    width: `${props.width}px`,
    height: `${props.height}px`,
    borderColor: '',
    background: '',
    zIndex: 0,
  });

  const circleRight = reactive({
    width: `${props.width}px`,
    height: `${props.height}px`,
    marginLeft: `-${props.height / 2}px`,
    borderColor: '',
    background: '',
    zIndex: 0,
  });

  const InnerJoin = reactive({
    width: `${props.width / 2}px`,
    height: `${props.height / 2}px`,
    background: '',
  });

  watch(() => props.joinType, (joinType: string) => {
    switch (joinType) {
    case 'inner_join':
      circleLeft.borderColor = props.type === 'gray' ? grayBorderColor.value : 'rgb(58, 132, 255)';
      circleLeft.background = '';

      circleRight.borderColor = props.type === 'gray' ? grayBorderColor.value : 'rgb(150, 201, 137)';
      circleRight.background = '';

      InnerJoin.background = props.type === 'gray' ? grayColor.value : 'rgb(58, 132, 255,.8)';
      break;
    case 'left_join':
      circleLeft.borderColor = props.type === 'gray' ? grayBorderColor.value : 'rgb(58, 132, 255)';
      circleLeft.background = props.type === 'gray' ? grayColor.value : 'rgb(58, 132, 255,.8)';
      circleLeft.zIndex = 999;

      circleRight.borderColor = props.type === 'gray' ? grayBorderColor.value : 'rgb(150, 201, 137)';
      circleRight.background = '';
      circleRight.zIndex = 0;

      InnerJoin.background = '';
      break;
    case 'right_join':
      circleLeft.borderColor = props.type === 'gray' ? grayBorderColor.value : 'rgb(58, 132, 255)';
      circleLeft.background = '';
      circleLeft.zIndex = 0;

      circleRight.borderColor = props.type === 'gray' ? grayBorderColor.value : 'rgb(150, 201, 137)';
      circleRight.background = props.type === 'gray' ? grayColor.value : 'rgb(150, 201, 137,.8)';
      circleRight.zIndex = 999;

      InnerJoin.background = '';
      break;
    case 'full_outer_join':
      circleLeft.borderColor = props.type === 'gray' ? grayBorderColor.value : 'rgb(58, 132, 255)';
      circleLeft.background = props.type === 'gray' ? grayColor.value : 'rgb(58, 132, 255,.8)';
      circleLeft.zIndex = 999;

      circleRight.borderColor = props.type === 'gray' ? grayBorderColor.value : 'rgb(150, 201, 137)';
      circleRight.background = props.type === 'gray' ? grayColor.value : 'rgb(150, 201, 137,.8)';
      circleRight.zIndex = 0;

      InnerJoin.background = '';
      break;
    }
  }, {
    immediate: true,
  });

</script>
<style scoped lang="postcss">
.table-relation-circle {
  position: relative;
  display: flex;

  .circle-left-join {
    border: 1px solid;
    border-radius: 50%;
    opacity: 80%;
  }

  .circle-right-join {
    position: relative;
    border: 1px solid;
    border-radius: 50%;
    opacity: 80%;
  }

  .circle-inner-join {
    position: absolute;
    margin: auto;
    border-radius: 100% 0;
    opacity: 80%;
    transform: rotate(-45deg);
    inset: 0;
  }
}
</style>
