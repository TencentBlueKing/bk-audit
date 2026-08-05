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

/**
 * 修复 bk-search-select 字段编辑态下的粘贴/删除交互：
 * 1) 选中值后粘贴应覆盖，而不是用 | 追加
 * 2) Delete/Backspace 清空选中值后应同步内部 values，否则后续无法粘贴
 *
 * 说明：依赖组件 DOM（.bk-search-select .div-input）与内部 setupState（usingItem/inputKey）。
 */

type SelectedItemLike = {
  values: Array<{ id: string; name: string }>;
  addValues: (str: string, merge?: boolean) => void;
};

type SearchInputSetupState = Record<string, any>;

const VUE_PARENT_KEY = '__vueParentComponent';

let installed = false;

const unwrapMaybeRef = <T, >(maybeRef: any): T => {
  if (maybeRef && typeof maybeRef === 'object' && 'value' in maybeRef && !('addValues' in maybeRef)) {
    return maybeRef.value as T;
  }
  return maybeRef as T;
};

const setMaybeRef = (setup: SearchInputSetupState, key: string, val: unknown) => {
  const current = setup[key];
  if (current && typeof current === 'object' && 'value' in current && !('addValues' in current)) {
    current.value = val;
    return;
  }
  // setupState 可能是自动解包 proxy，直接赋值以同步内部 ref
  // eslint-disable-next-line no-param-reassign
  setup[key] = val;
};

const getSearchInputSetupState = (inputEl: HTMLElement): SearchInputSetupState | null => {
  let el: HTMLElement | null = inputEl;
  while (el) {
    let inst = (el as any)[VUE_PARENT_KEY];
    while (inst) {
      const setupState = inst.setupState as SearchInputSetupState | undefined;
      if (setupState && 'usingItem' in setupState && 'inputKey' in setupState) {
        return setupState;
      }
      inst = inst.parent;
    }
    el = el.parentElement;
  }
  return null;
};

const remountSearchInput = (setup: SearchInputSetupState) => {
  setMaybeRef(setup, 'inputKey', `${Date.now()}`);
};

const resolveFieldEditInput = (target: EventTarget | null): HTMLElement | null => {
  const el = target as HTMLElement | null;
  if (!el?.closest) return null;

  const root = el.closest('.bk-search-select') as HTMLElement | null;
  if (!root) return null;

  const inputEl = el.closest('.div-input') as HTMLElement | null;
  if (!inputEl || !root.contains(inputEl)) return null;

  // 仅处理「已选字段」编辑态；自由输入交给组件默认逻辑
  const hasFieldKey = !!inputEl.querySelector('span[contenteditable="false"][data-key]');
  if (!hasFieldKey) return null;

  return inputEl;
};

const hasTextSelection = () => {
  const selection = window.getSelection();
  return !!selection && !selection.isCollapsed && !!selection.toString();
};

const focusRemountedInput = (inputEl: HTMLElement) => {
  const root = inputEl.closest('.bk-search-select');
  // inputKey 变更后节点会重建，下一帧再聚焦
  requestAnimationFrame(() => {
    const nextInput = (root?.querySelector('.div-input') || inputEl) as HTMLElement | null;
    nextInput?.focus();
  });
};

const handlePasteCapture = (event: ClipboardEvent) => {
  const inputEl = resolveFieldEditInput(event.target);
  if (!inputEl) return;

  const setup = getSearchInputSetupState(inputEl);
  const usingItem = unwrapMaybeRef<SelectedItemLike | null>(setup?.usingItem);
  if (!usingItem || typeof usingItem.addValues !== 'function') return;

  const selected = hasTextSelection();
  const valuesEmpty = !usingItem.values?.length;
  // 有选区 → 覆盖；删空后 values 已空 → 也要接管，否则组件默认粘贴仍可能异常
  if (!selected && !valuesEmpty) return;

  const pasted = (event.clipboardData?.getData('text') || '').trim();
  event.preventDefault();
  event.stopImmediatePropagation();
  if (!pasted || !setup) return;

  usingItem.addValues(pasted, false);
  setMaybeRef(setup, 'keyword', pasted);
  remountSearchInput(setup);
  focusRemountedInput(inputEl);
};

const handleKeydownCapture = (event: KeyboardEvent) => {
  if (event.key !== 'Delete' && event.key !== 'Backspace') return;
  if (!hasTextSelection()) return;

  const inputEl = resolveFieldEditInput(event.target);
  if (!inputEl) return;

  const setup = getSearchInputSetupState(inputEl);
  const usingItem = unwrapMaybeRef<SelectedItemLike | null>(setup?.usingItem);
  if (!usingItem || !setup) return;

  // 选中值被删除时同步清空内部 values，避免后续粘贴失效
  event.preventDefault();
  event.stopImmediatePropagation();
  usingItem.values = [];
  setMaybeRef(setup, 'keyword', '');
  remountSearchInput(setup);
  focusRemountedInput(inputEl);
};

export const installBkSearchSelectEnhance = () => {
  if (installed || typeof document === 'undefined') return;
  document.addEventListener('paste', handlePasteCapture, true);
  document.addEventListener('keydown', handleKeydownCapture, true);
  installed = true;
};

export const uninstallBkSearchSelectEnhance = () => {
  if (!installed || typeof document === 'undefined') return;
  document.removeEventListener('paste', handlePasteCapture, true);
  document.removeEventListener('keydown', handleKeydownCapture, true);
  installed = false;
};
