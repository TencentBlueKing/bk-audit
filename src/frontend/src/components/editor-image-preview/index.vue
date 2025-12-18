<template>
  <div
    v-if="images.length > 0"
    class="editor-image-preview">
    <div class="preview-header">
      <span class="preview-title">{{ title }} ({{ images.length }})</span>
    </div>
    <div class="preview-grid">
      <div
        v-for="(image, index) in images"
        :key="index"
        class="preview-item">
        <img
          :alt="t('图片') + `${index + 1}`"
          class="preview-thumbnail"
          :src="image.url"
          @click="openModal(index)"
          @error="handleImageError(index)">
      </div>
    </div>

    <!-- 自定义图片放大遮罩 -->
    <div
      v-if="showModal"
      class="image-modal-overlay"
      @click="closeModal">
      <div class="image-modal-container">
        <!-- 关闭按钮 - 右上角 -->
        <div
          class="modal-close"
          @click="closeModal">
          <audit-icon type="close-line" />
        </div>

        <!-- 图片容器 -->
        <div class="modal-image-wrapper">
          <img
            v-if="currentImage && currentImage.url"
            :alt="t('图片') + `${currentIndex + 1}`"
            class="modal-image"
            :src="currentImage.url"
            :style="{
              transform: `rotate(${imageRotation}deg) scale(${imageScale})`
            }"
            @click.stop
            @error="handleModalImageError">
        </div>

        <!-- 底部控制栏 -->
        <div class="bottom-controls">
          <!-- 图片信息 -->
          <div class="image-info">
            <span>{{ title }} {{ currentIndex + 1 }}</span>
            <span
              v-if="images.length > 1"
              class="image-counter">
              {{ currentIndex + 1 }} / {{ images.length }}
            </span>
          </div>

          <!-- 控制按钮组 -->
          <div class="control-buttons">
            <!-- 左右导航 -->
            <div
              v-if="images.length > 1 && currentIndex > 0"
              class="control-button"
              @click.stop="prevImage">
              <audit-icon type="back" />
            </div>
            <div
              v-else
              class="control-button disabled">
              <audit-icon type="back" />
            </div>

            <!-- 旋转按钮 -->
            <div
              class="control-button"
              @click.stop="rotateLeft">
              <audit-icon type="redo" />
            </div>

            <!-- 放大按钮 -->
            <div
              class="control-button"
              @click.stop="zoomIn">
              <audit-icon type="add-fill" />
            </div>

            <!-- 缩小按钮 -->
            <div
              class="control-button"
              @click.stop="zoomOut">
              <audit-icon type="reduce-fill" />
            </div>

            <!-- 右导航 -->
            <div
              v-if="images.length > 1 && currentIndex < images.length - 1"
              class="control-button"
              @click.stop="nextImage">
              <audit-icon type="right" />
            </div>
            <div
              v-else
              class="control-button disabled">
              <audit-icon type="right" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, onMounted, onUnmounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  interface ImageItem {
    url: string;
  }

  interface Props {
    images: ImageItem[];
    title: string;
  }

  const props = defineProps<Props>();
  const { t } = useI18n();
  const showModal = ref(false);
  const currentIndex = ref(0);
  const imageRotation = ref(0);
  const imageScale = ref(1);

  const currentImage = computed(() => props.images[currentIndex.value]);

  // 处理图片加载错误
  const handleImageError = (index: number) => {
    console.warn(`图片 ${index} 加载失败:`, props.images[index]?.url);
  };

  const handleModalImageError = () => {
    console.warn('模态框图片加载失败:', currentImage.value?.url);
  };

  // 打开模态框
  const openModal = (index: number) => {
    currentIndex.value = index;
    showModal.value = true;
  };

  // 关闭模态框
  const closeModal = () => {
    showModal.value = false;
    currentIndex.value = 0;
    // 重置图片变换
    imageRotation.value = 0;
    imageScale.value = 1;
  };

  // 上一张图片
  const prevImage = () => {
    if (currentIndex.value > 0) {
      currentIndex.value -= 1;
      // 切换图片时重置变换
      imageRotation.value = 0;
      imageScale.value = 1;
    }
  };

  // 下一张图片
  const nextImage = () => {
    if (currentIndex.value < props.images.length - 1) {
      currentIndex.value += 1;
      // 切换图片时重置变换
      imageRotation.value = 0;
      imageScale.value = 1;
    }
  };

  // 旋转图片
  const rotateLeft = () => {
    imageRotation.value -= 90;
  };

  // 放大图片
  const zoomIn = () => {
    imageScale.value = Math.min(imageScale.value + 0.2, 3);
  };

  // 缩小图片
  const zoomOut = () => {
    imageScale.value = Math.max(imageScale.value - 0.2, 0.5);
  };

  // 键盘事件处理
  const handleKeydown = (event: KeyboardEvent) => {
    if (!showModal.value) return;

    switch (event.key) {
    case 'Escape':
      closeModal();
      break;
    case 'ArrowLeft':
      if (currentIndex.value > 0) {
        prevImage();
      }
      break;
    case 'ArrowRight':
      if (currentIndex.value < props.images.length - 1) {
        nextImage();
      }
      break;
    }
  };

  // 添加键盘事件监听
  onMounted(() => {
    document.addEventListener('keydown', handleKeydown);
  });

  // 移除键盘事件监听
  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeydown);
  });
</script>

<style scoped lang="postcss">
.editor-image-preview {
  padding: 12px;
  margin-top: 12px;
  background-color: #f5f7fa;
  border: 1px solid #dcdee5;
  border-radius: 4px;
}

.preview-header {
  margin-bottom: 8px;
}

.preview-title {
  font-size: 12px;
  font-weight: 500;
  color: #63656e;
}

.preview-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.preview-item {
  display: inline-block;
}

.preview-thumbnail {
  width: 60px;
  height: 60px;
  cursor: pointer;
  border: 1px solid #dcdee5;
  border-radius: 4px;
  transition: all .2s;
  object-fit: cover;
}

.preview-thumbnail:hover {
  border-color: #3a84ff;
  box-shadow: 0 2px 4px rgb(58 132 255 / 20%);
}

/* 自定义图片放大遮罩样式 */
.image-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  cursor: pointer;
  background-color: rgb(0 0 0 / 80%);
  animation: fade-in .3s ease;
  justify-content: center;
  align-items: center;
}

.image-modal-container {
  position: relative;
  display: flex;
  width: 100vw;
  height: 100vh;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}

.modal-image-wrapper {
  display: flex;
  width: 80%;
  padding: 60px 20px 120px;
  overflow: hidden;
  flex: 1;
  justify-content: center;
  align-items: center;
}

.modal-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  cursor: default;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgb(0 0 0 / 30%);
  animation: zoom-in .3s ease;
  transition: transform .3s ease;
}

.modal-close {
  position: absolute;
  top: 20px;
  right: 20px;
  z-index: 10001;
  display: flex;
  width: 40px;
  height: 40px;
  color: #fff;
  cursor: pointer;
  background-color: rgb(0 0 0 / 60%);
  border-radius: 50%;
  transition: all .2s;
  justify-content: center;
  align-items: center;
}

.modal-close .wesec-icon {
  font-size: 20px;
}

.modal-close:hover {
  background-color: rgb(0 0 0 / 80%);
  transform: scale(1.1);
}

/* 底部控制栏 */
.bottom-controls {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  display: flex;
  padding: 40px 20px 20px;
  background: linear-gradient(to top, rgb(0 0 0 / 80%), rgb(0 0 0 / 40%), transparent);
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.image-info {
  display: flex;
  font-size: 14px;
  color: white;
  text-align: center;
  flex-direction: column;
  gap: 4px;
}

.image-counter {
  font-size: 12px;
  color: #ccc;
}

.control-buttons {
  display: flex;
  gap: 12px;
  align-items: center;
}

.control-button {
  display: flex;
  width: 44px;
  height: 44px;
  font-size: 24px;
  color: #333;
  cursor: pointer;
  background-color: rgb(255 255 255 / 90%);
  border-radius: 50%;
  transition: all .2s;
  user-select: none;
  justify-content: center;
  align-items: center;
}

.control-button:hover:not(.disabled) {
  background-color: #fff;
  transform: scale(1.1);
}

.control-button.disabled {
  cursor: not-allowed;
  opacity: 40%;
}

.control-button .wesec-icon {
  font-size: 18px;
}

/* 动画效果 */
@keyframes fade-in {
  from {
    opacity: 0%;
  }

  to {
    opacity: 100%;
  }
}

@keyframes zoom-in {
  from {
    opacity: 0%;
    transform: scale(.8);
  }

  to {
    opacity: 100%;
    transform: scale(1);
  }
}

/* 响应式设计 */
@media (width <= 768px) {
  .modal-close {
    top: 10px;
    right: 10px;
  }

  .image-info {
    font-size: 12px;
  }

  .control-buttons {
    gap: 8px;
  }

  .control-button {
    width: 40px;
    height: 40px;
  }

  .control-button .wesec-icon {
    font-size: 16px;
  }
}
</style>
