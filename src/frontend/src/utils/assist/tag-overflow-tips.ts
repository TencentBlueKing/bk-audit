/*
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
*/
import tippy, {
  type Instance,
  type SingleTarget,
} from 'tippy.js';

const TAG_SELECTOR = [
  '.bk-tag',
  '.user-tag',
  '.custom-tag',
  '.pa-param-user-tag',
  '.audit-ellipsis-tag',
].join(',');

const TEXT_INNER_SELECTOR = [
  '.bk-tag-text',
  '.user-name',
  '.tag-content',
  '.custom-tag-text',
].join(',');

const SKIP_SELECTOR = [
  '.audit-edit-tag__more',
  '.audit-edit-tag-measure',
  '.audit-tag-no-ellipsis',
  '.override-selected-overflow-tag',
].join(',');

const MORE_TAG_TEXT = /^\+\s*\d+$/;

type TippyHost = HTMLElement & {
  _tippy?: Instance;
};

let installed = false;
let activeIns: Instance | null = null;
let activeEl: HTMLElement | null = null;

const closestTag = (target: EventTarget | null) => {
  if (!(target instanceof Element)) {
    return null;
  }
  return target.closest(TAG_SELECTOR) as HTMLElement | null;
};

const getOverflowEl = (tagEl: HTMLElement) => {
  const inner = tagEl.querySelector(TEXT_INNER_SELECTOR) as HTMLElement | null;
  return inner || tagEl;
};

const getContent = (tagEl: HTMLElement) => {
  const inner = tagEl.querySelector(TEXT_INNER_SELECTOR) as HTMLElement | null;
  return (inner?.textContent || tagEl.textContent || '').replace(/\s+/g, ' ').trim();
};

const isOverflow = (el: HTMLElement) => (
  el.scrollWidth > el.clientWidth + 1
  || el.scrollHeight > el.clientHeight + 1
);

const shouldSkip = (tagEl: HTMLElement) => {
  if (tagEl.closest(SKIP_SELECTOR) || tagEl.matches(SKIP_SELECTOR)) {
    return true;
  }
  const content = getContent(tagEl);
  if (!content || MORE_TAG_TEXT.test(content)) {
    return true;
  }
  // 已有其它 tippy 时不重复挂载
  // eslint-disable-next-line no-underscore-dangle
  const existingTippy = (tagEl as TippyHost)._tippy;
  if (existingTippy && existingTippy !== activeIns) {
    return true;
  }
  return !isOverflow(getOverflowEl(tagEl));
};

const destroyActive = () => {
  if (activeIns) {
    activeIns.hide();
    activeIns.unmount();
    activeIns.destroy();
    activeIns = null;
  }
  activeEl = null;
};

const showTips = (tagEl: HTMLElement) => {
  if (activeEl === tagEl && activeIns) {
    return;
  }
  destroyActive();
  const content = getContent(tagEl);
  if (!content) {
    return;
  }
  activeEl = tagEl;
  activeIns = tippy(tagEl as SingleTarget, {
    content,
    placement: 'top',
    appendTo: () => document.body,
    theme: 'dark',
    maxWidth: 320,
    interactive: false,
    arrow: true,
    offset: [0, 8],
    zIndex: 999999,
    hideOnClick: true,
    trigger: 'manual',
  });
  activeIns.show();
};

const handleMouseOver = (event: MouseEvent) => {
  const tagEl = closestTag(event.target);
  const fromTag = closestTag(event.relatedTarget);
  if (!tagEl || tagEl === fromTag) {
    return;
  }
  if (shouldSkip(tagEl)) {
    return;
  }
  showTips(tagEl);
};

const handleMouseOut = (event: MouseEvent) => {
  const tagEl = closestTag(event.target);
  const toTag = closestTag(event.relatedTarget);
  if (!tagEl || tagEl === toTag) {
    return;
  }
  if (activeEl === tagEl) {
    destroyActive();
  }
};

export const installTagOverflowTips = () => {
  if (installed || typeof document === 'undefined') {
    return;
  }
  installed = true;
  document.addEventListener('mouseover', handleMouseOver, true);
  document.addEventListener('mouseout', handleMouseOut, true);
};
