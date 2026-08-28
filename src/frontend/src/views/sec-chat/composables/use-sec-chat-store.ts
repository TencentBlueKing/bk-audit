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
import { computed, ref } from 'vue';

import AiAssistantManageService from '@service/ai-assistant-manage';

import type {
  AiMessage,
  AiSearchCondition,
  AiSidebarConversationNode,
  AiSidebarGroupNode,
  AiSidebarNode,
} from '@model/ai-assistant/types';

import type {
  Conversation,
  Group,
  SelectedSystem,
} from '../types';
import {
  buildFieldCatalog,
  extractFieldCatalogFromSystemMessage,
  findLatestSuccessSystemSelection,
  getNlRecognitionError,
  mapAiMessageToChatMessage,
} from '../utils/map-ai-message';

const MESSAGE_POLL_INTERVAL_MS = 2000;
const CHILD_LOG_RETRY_TIMES = 3;
const CHILD_LOG_RETRY_DELAY_MS = 500;

const sleep = (ms: number) => new Promise<void>((resolve) => {
  setTimeout(resolve, ms);
});

const createEmptyConversation = (partial: Omit<Conversation, 'systemIds' | 'systems' | 'messages'> & Partial<Conversation>): Conversation => ({
  systemIds: [],
  systems: [],
  messages: [],
  ...partial,
});

const sidebarCollapsed = ref(false);
const activeConversationId = ref<string | null>(null);
const sidebarLoading = ref(false);
const messageLoading = ref(false);

const groups = ref<Group[]>([]);
const conversations = ref<Conversation[]>([]);

/** 草稿会话（确认系统前的本地态） */
const draftConversation = ref<Conversation | null>(null);

const pollTimers = new Map<string, ReturnType<typeof setInterval>>();
/** 同一会话消息拉取进行中的 Promise，避免并发叠打 */
const messageLoadInflight = new Map<string, Promise<void>>();
/** 同一分组子节点拉取进行中的 Promise，避免并发叠打 */
const groupLoadInflight = new Map<string, Promise<void>>();

const activeConversation = computed(() => {
  if (draftConversation.value && activeConversationId.value === draftConversation.value.id) {
    return draftConversation.value;
  }
  return conversations.value.find(c => c.id === activeConversationId.value) || null;
});

const isConversationNode = (node: AiSidebarNode): node is AiSidebarConversationNode => (
  node.node_type === 'CONVERSATION'
);

const isGroupNode = (node: AiSidebarNode): node is AiSidebarGroupNode => (
  node.node_type === 'GROUP'
);

const mapConversationNode = (node: AiSidebarConversationNode, pinned = false): Conversation => (
  createEmptyConversation({
    id: node.node_uid,
    title: node.title || '新对话',
    pinned: pinned || Boolean(node.pinned),
    groupName: node.group_name || undefined,
    sceneType: 'log',
    createdAt: node.updated_at || node.created_at
      ? Date.parse(node.updated_at || node.created_at || '') || Date.now()
      : Date.now(),
  })
);

const stopMessagePoll = (messageUid: string) => {
  const timer = pollTimers.get(messageUid);
  if (timer) {
    clearInterval(timer);
    pollTimers.delete(messageUid);
  }
};

const stopAllMessagePolls = () => {
  pollTimers.forEach((_timer, uid) => stopMessagePoll(uid));
};

const applySystemSelectionContext = (conv: Conversation, chatMessage: ReturnType<typeof mapAiMessageToChatMessage>) => {
  const systems = chatMessage.systems || [];
  /* eslint-disable no-param-reassign */
  conv.systems = systems;
  conv.systemIds = systems.map(item => item.id);
  conv.selectedSystemMessageUid = chatMessage.id;
  conv.standardFields = chatMessage.standardFields || [];
  conv.extensionFields = chatMessage.extensionFields || [];
  conv.commonOperations = chatMessage.commonOperations || [];
  conv.historicalOperations = chatMessage.historicalOperations || [];
  /* eslint-enable no-param-reassign */
};

const upsertConversationMessage = (conversationId: string, message: AiMessage) => {
  const conv = conversations.value.find(c => c.id === conversationId)
    || (draftConversation.value?.id === conversationId ? draftConversation.value : null);
  if (!conv) return;

  const fieldCatalog = buildFieldCatalog(conv.standardFields, conv.extensionFields);
  const chatMessage = mapAiMessageToChatMessage(message, { fieldCatalog });
  const idx = conv.messages.findIndex(item => item.id === message.uid);
  if (idx >= 0) {
    conv.messages.splice(idx, 1, chatMessage);
  } else {
    conv.messages.push(chatMessage);
  }

  if (message.message_type === 'SYSTEM_SELECTION' && message.status === 'SUCCESS') {
    applySystemSelectionContext(conv, chatMessage);
  }
};

/** NL SUCCESS 后拉取后端续链创建的 LOG_SEARCH 子消息 */
const fetchChildLogSearch = async (conversationId: string, nlUid: string) => {
  for (let attempt = 0; attempt < CHILD_LOG_RETRY_TIMES; attempt += 1) {
    try {
      const windowData = await AiAssistantManageService.fetchMessageHistory({
        conversation_uid: conversationId,
        anchor_uid: nlUid,
        direction: 'AFTER',
        include_content: true,
      });
      const child = (windowData.results || []).find(item => (
        item.message_type === 'LOG_SEARCH'
        && item.parent_message_uid === nlUid
      ));
      if (child) {
        upsertConversationMessage(conversationId, child);
        return child;
      }
    } catch {
      // 短暂重试
    }
    if (attempt < CHILD_LOG_RETRY_TIMES - 1) {
      await sleep(CHILD_LOG_RETRY_DELAY_MS);
    }
  }
  return null;
};

const handleNlTerminalStatus = async (conversationId: string, detail: AiMessage) => {
  if (detail.message_type !== 'NATURAL_LANGUAGE_SEARCH') return;
  if (detail.status === 'SUCCESS' && !getNlRecognitionError(detail)) {
    await fetchChildLogSearch(conversationId, detail.uid);
  }
};

const startMessagePoll = (conversationId: string, messageUid: string) => {
  if (pollTimers.has(messageUid)) return;

  const tick = async () => {
    try {
      const detail = await AiAssistantManageService.fetchMessage({ message_uid: messageUid });
      upsertConversationMessage(conversationId, detail);
      if (detail.status !== 'PROCESSING') {
        stopMessagePoll(messageUid);
        await handleNlTerminalStatus(conversationId, detail);
      }
    } catch {
      // 轮询失败不打断，下一次继续
    }
  };

  void tick();
  const timer = setInterval(tick, MESSAGE_POLL_INTERVAL_MS);
  pollTimers.set(messageUid, timer);
};

const resumeProcessingPolls = (conversationId: string, messages: AiMessage[]) => {
  messages.forEach((message) => {
    // 文档：仅自然语言消息会出现 PROCESSING
    if (message.status === 'PROCESSING'
      && (message.message_type === 'NATURAL_LANGUAGE_SEARCH' || !message.message_type)) {
      startMessagePoll(conversationId, message.uid);
    }
  });
};

const applyMessageWindow = (conv: Conversation, windowData: {
  first_uid: string | null;
  last_uid: string | null;
  has_before: boolean;
  has_after: boolean;
  results: AiMessage[];
}, mode: 'replace' | 'prepend' | 'append' = 'replace') => {
  const latestSystemInWindow = findLatestSuccessSystemSelection(windowData.results);
  const fieldCatalog = latestSystemInWindow
    ? extractFieldCatalogFromSystemMessage(latestSystemInWindow)
    : buildFieldCatalog(conv.standardFields, conv.extensionFields);

  const mapped: ReturnType<typeof mapAiMessageToChatMessage>[] = [];
  windowData.results.forEach((message) => {
    if (message.message_type === 'NATURAL_LANGUAGE_SEARCH' && message.input_data?.query_text) {
      mapped.push({
        id: `${message.uid}-user`,
        role: 'user',
        type: 'text',
        content: String(message.input_data.query_text),
      });
    }
    mapped.push(mapAiMessageToChatMessage(message, { fieldCatalog }));
  });
  /* eslint-disable no-param-reassign -- 原地更新会话消息窗口与系统上下文 */
  if (mode === 'replace') {
    conv.messages = mapped;
  } else if (mode === 'prepend') {
    const existIds = new Set(conv.messages.map(item => item.id));
    conv.messages = [...mapped.filter(item => !existIds.has(item.id)), ...conv.messages];
  } else {
    const existIds = new Set(conv.messages.map(item => item.id));
    conv.messages = [...conv.messages, ...mapped.filter(item => !existIds.has(item.id))];
  }

  conv.messageFirstUid = windowData.first_uid;
  conv.messageLastUid = windowData.last_uid;
  conv.hasBeforeMessages = windowData.has_before;
  conv.hasAfterMessages = windowData.has_after;

  // 仅在替换/追加更新「当前系统」；向前翻历史不应回退到更早的 SYSTEM_SELECTION
  if (mode !== 'prepend' && latestSystemInWindow) {
    applySystemSelectionContext(conv, mapAiMessageToChatMessage(latestSystemInWindow));
  }
  /* eslint-enable no-param-reassign */

  resumeProcessingPolls(conv.id, windowData.results);

  // 历史里若已有 SUCCESS 的 NL 但尚未带上子 LOG，补拉一次（识别失败除外）
  windowData.results.forEach((message) => {
    if (message.message_type === 'NATURAL_LANGUAGE_SEARCH'
      && message.status === 'SUCCESS'
      && !getNlRecognitionError(message)) {
      const hasChild = windowData.results.some(item => (
        item.message_type === 'LOG_SEARCH' && item.parent_message_uid === message.uid
      )) || conv.messages.some(item => (
        item.messageType === 'LOG_SEARCH' && item.parentMessageUid === message.uid
      ));
      if (!hasChild) {
        void fetchChildLogSearch(conv.id, message.uid);
      }
    }
  });
};

export function useSecChatStore() {
  const toggleSidebar = () => {
    sidebarCollapsed.value = !sidebarCollapsed.value;
  };

  const mergeConversationCache = (
    list: Conversation[],
    messageCache: Map<string, Conversation>,
  ): Conversation[] => list.map((item) => {
    const cached = messageCache.get(item.id);
    if (!cached) return item;
    return {
      ...item,
      messages: cached.messages,
      systems: cached.systems,
      systemIds: cached.systemIds,
      standardFields: cached.standardFields,
      extensionFields: cached.extensionFields,
      commonOperations: cached.commonOperations,
      historicalOperations: cached.historicalOperations,
      selectedSystemMessageUid: cached.selectedSystemMessageUid,
      messageFirstUid: cached.messageFirstUid,
      messageLastUid: cached.messageLastUid,
      hasBeforeMessages: cached.hasBeforeMessages,
      hasAfterMessages: cached.hasAfterMessages,
      messagesHydrated: cached.messagesHydrated,
    };
  });

  const snapshotMessageCache = () => new Map(conversations.value
    .filter(item => item.messagesHydrated || item.messages.length > 0)
    .map(item => [item.id, item] as const));

  /** 同 id 只保留首次出现（调用方保证更优先的列表在前） */
  const dedupeConversations = (list: Conversation[]): Conversation[] => {
    const seen = new Set<string>();
    return list.filter((item) => {
      if (seen.has(item.id)) return false;
      seen.add(item.id);
      return true;
    });
  };

  /**
   * 按需拉取分组下会话。展开分组 / 搜索时调用；已加载且非 force 则跳过。
   */
  const loadGroupConversations = async (groupId: string, options?: { force?: boolean }) => {
    const group = groups.value.find(g => g.id === groupId);
    if (!group) return;
    if (group.childrenLoaded && !options?.force) return;

    const existing = groupLoadInflight.get(groupId);
    if (existing) {
      await existing;
      return;
    }

    const task = (async () => {
      const target = groups.value.find(g => g.id === groupId);
      if (!target) return;
      if (target.childrenLoaded && !options?.force) return;

      target.childrenLoading = true;
      try {
        const childPage = await AiAssistantManageService.fetchSidebarNodes({
          parent_node_type: 'GROUP',
          parent_node_uid: groupId,
          page: 1,
          page_size: 100,
        });
        // await 后分组列表可能已刷新，重新定位
        const latest = groups.value.find(g => g.id === groupId);
        if (!latest) return;

        const mapped = (childPage.results || [])
          .filter(isConversationNode)
          .map(node => mapConversationNode({
            ...node,
            group_name: latest.name,
            group_uid: latest.id,
          }));

        const messageCache = snapshotMessageCache();
        // 分组子节点在前：同 id 去重时优先采用本接口结果，避免与根列表旧副本叠出两条
        conversations.value = dedupeConversations([
          ...mergeConversationCache(mapped, messageCache),
          ...conversations.value.filter(c => c.groupName !== latest.name),
        ]);
        latest.childrenLoaded = true;
        latest.conversationCount = mapped.length;
      } catch {
        // 单组失败保留未加载态，便于下次展开重试
        const latest = groups.value.find(g => g.id === groupId);
        if (latest) latest.childrenLoaded = false;
      } finally {
        const latest = groups.value.find(g => g.id === groupId);
        if (latest) latest.childrenLoading = false;
      }
    })();

    groupLoadInflight.set(groupId, task);
    try {
      await task;
    } finally {
      groupLoadInflight.delete(groupId);
    }
  };

  /**
   * 初始化 / 刷新侧栏根节点（未分组会话 + 分组元信息）。
   * 分组内会话仅在展开 / 搜索时按需加载。
   * 已加载过的分组子节点在刷新时保留，避免展开组「先空再补拉」闪屏。
   * 置顶能力本期不开放，不请求 pinned/。
   */
  const initSidebar = async () => {
    sidebarLoading.value = true;
    try {
      const rootPage = await AiAssistantManageService.fetchSidebarNodes({ page: 1, page_size: 100 });
      const rootNodes = rootPage.results || [];
      const groupNodes = rootNodes.filter(isGroupNode);
      const rootConversations = rootNodes
        .filter(isConversationNode)
        .map(node => mapConversationNode(node));

      const prevGroups = groups.value;
      const loadedIdSet = new Set(prevGroups.filter(g => g.childrenLoaded).map(g => g.id));

      const nextGroups: Group[] = groupNodes.map(groupNode => ({
        id: groupNode.node_uid,
        name: groupNode.name,
        conversationCount: groupNode.conversation_count,
        childrenLoaded: loadedIdSet.has(groupNode.node_uid),
        childrenLoading: false,
      }));

      const messageCache = snapshotMessageCache();
      const activeId = activeConversationId.value;
      const activeKeep = activeId
        ? conversations.value.find(c => c.id === activeId && c.groupName)
        : undefined;

      // 保留仍存在且此前已加载的分组子会话；分组重命名时同步 groupName
      const rootIds = new Set(rootConversations.map(c => c.id));
      const preservedGroupConvs = conversations.value
        .filter((c) => {
          if (!c.groupName || rootIds.has(c.id)) return false;
          const prev = prevGroups.find(g => g.name === c.groupName && g.childrenLoaded);
          return Boolean(prev && loadedIdSet.has(prev.id));
        })
        .map((c) => {
          const prev = prevGroups.find(g => g.name === c.groupName);
          if (!prev) return c;
          const nextName = nextGroups.find(g => g.id === prev.id)?.name;
          if (nextName && nextName !== c.groupName) {
            return { ...c, groupName: nextName };
          }
          return c;
        });

      conversations.value = dedupeConversations([
        ...mergeConversationCache(rootConversations, messageCache),
        ...mergeConversationCache(preservedGroupConvs, messageCache),
      ]);
      if (activeKeep && !conversations.value.some(c => c.id === activeKeep.id)) {
        const prev = prevGroups.find(g => g.name === activeKeep.groupName);
        const nextName = prev
          ? nextGroups.find(g => g.id === prev.id)?.name
          : undefined;
        const keep = nextName && nextName !== activeKeep.groupName
          ? { ...activeKeep, groupName: nextName }
          : activeKeep;
        conversations.value.push(mergeConversationCache([keep], messageCache)[0]);
      }
      groups.value = nextGroups;
    } finally {
      sidebarLoading.value = false;
    }
  };

  const resolveConversation = (conversationId: string): Conversation => {
    let conv = conversations.value.find(c => c.id === conversationId);
    if (!conv) {
      conv = createEmptyConversation({
        id: conversationId,
        title: '新对话',
        pinned: false,
        sceneType: 'log',
        createdAt: Date.now(),
      });
      conversations.value.unshift(conv);
    }
    return conv;
  };

  const loadConversationMessages = async (conversationId: string) => {
    const existing = messageLoadInflight.get(conversationId);
    if (existing) return existing;

    const task = (async () => {
      const seed = conversations.value.find(c => c.id === conversationId);
      if (seed?.isDraft) return;
      if (seed?.messagesHydrated) return;

      resolveConversation(conversationId);
      messageLoading.value = true;
      try {
        const [detail, windowData] = await Promise.all([
          AiAssistantManageService.fetchConversation({ conversation_uid: conversationId }),
          AiAssistantManageService.fetchMessageHistory({
            conversation_uid: conversationId,
            include_content: true,
          }),
        ]);
        // await 后侧栏可能已整表替换，必须重新取引用再写回
        const conv = resolveConversation(conversationId);
        conv.title = detail.title || conv.title;
        applyMessageWindow(conv, windowData, 'replace');
        conv.messagesHydrated = true;
      } catch (error) {
        const idx = conversations.value.findIndex(c => c.id === conversationId);
        if (idx >= 0 && conversations.value[idx].messages.length === 0) {
          conversations.value.splice(idx, 1);
        }
        if (activeConversationId.value === conversationId) {
          activeConversationId.value = null;
        }
        throw error;
      } finally {
        messageLoading.value = false;
      }
    })();

    messageLoadInflight.set(conversationId, task);
    try {
      await task;
    } finally {
      messageLoadInflight.delete(conversationId);
    }
  };

  const loadOlderMessages = async () => {
    const conv = activeConversation.value;
    if (!conv || conv.isDraft || !conv.hasBeforeMessages || !conv.messageFirstUid) return;
    const windowData = await AiAssistantManageService.fetchMessageHistory({
      conversation_uid: conv.id,
      anchor_uid: conv.messageFirstUid,
      direction: 'BEFORE',
      include_content: true,
    });
    applyMessageWindow(conv, {
      ...windowData,
      // 翻页后窗口锚点需与合并后的列表对齐
      first_uid: windowData.first_uid || conv.messageFirstUid,
      last_uid: conv.messageLastUid || windowData.last_uid,
      has_after: conv.hasAfterMessages ?? windowData.has_after,
    }, 'prepend');
  };

  const setActiveConversation = async (id: string | null) => {
    activeConversationId.value = id;
    if (!id) {
      stopAllMessagePolls();
      return;
    }
    if (draftConversation.value?.id === id) return;

    const conv = resolveConversation(id);

    if (!conv.messagesHydrated) {
      await loadConversationMessages(id);
      return;
    }

    conv.messages.forEach((message) => {
      if (message.apiStatus === 'PROCESSING'
        && message.messageType === 'NATURAL_LANGUAGE_SEARCH') {
        startMessagePoll(id, message.id);
      }
    });
  };

  const deleteConversation = async (id: string) => {
    if (draftConversation.value?.id === id) {
      draftConversation.value = null;
      if (activeConversationId.value === id) activeConversationId.value = null;
      return;
    }
    await AiAssistantManageService.deleteConversation({ conversation_uid: id });
    const idx = conversations.value.findIndex(c => c.id === id);
    if (idx >= 0) conversations.value.splice(idx, 1);
    if (activeConversationId.value === id) {
      activeConversationId.value = null;
      stopAllMessagePolls();
    }
    await initSidebar();
  };

  const updateConversationGroup = async (id: string, groupName?: string) => {
    const conv = conversations.value.find(c => c.id === id);
    if (!conv || conv.isDraft) return;
    const prevGroupName = conv.groupName;
    const normalizedGroupName = groupName?.trim() || undefined;
    const targetGroup = normalizedGroupName
      ? groups.value.find(g => g.name === normalizedGroupName)
      : undefined;

    await AiAssistantManageService.moveSidebarNode({
      source_node_type: 'CONVERSATION',
      source_node_uid: id,
      ...(targetGroup ? {
        target_node_type: 'GROUP' as const,
        target_node_uid: targetGroup.id,
      } : {}),
    });

    // 本地改归属，并去掉同 id 重复项，避免根列表与分组子节点叠出两条
    if (normalizedGroupName) {
      conv.groupName = normalizedGroupName;
    } else {
      delete conv.groupName;
    }
    conversations.value = dedupeConversations(conversations.value);

    await initSidebar();

    // 强制刷新相关分组，清掉 initSidebar 保留的过期子节点
    const reloadIds = new Set<string>();
    if (prevGroupName) {
      const prev = groups.value.find(g => g.name === prevGroupName);
      if (prev) reloadIds.add(prev.id);
    }
    if (targetGroup) {
      reloadIds.add(targetGroup.id);
    }
    await Promise.all([...reloadIds].map(groupId => loadGroupConversations(groupId, { force: true })));

    // 以本次操作为准校正归属后再去重，避免重拉分组时过期子节点与根列表各留一条
    conversations.value = dedupeConversations(conversations.value.map((item) => {
      if (item.id !== id) return item;
      if (normalizedGroupName) {
        return { ...item, groupName: normalizedGroupName };
      }
      const next = { ...item };
      delete next.groupName;
      return next;
    }));
  };

  /**
   * 同容器内会话排序（未分组根列表 / 某一分组内）。
   * beforeId：插到该会话前；toEnd：移到容器末尾（协议只有 before/最前，末尾用两次 move 对齐）。
   */
  const reorderConversation = async (
    id: string,
    options: { groupName?: string; beforeId?: string; toEnd?: boolean },
  ) => {
    const conv = conversations.value.find(c => c.id === id);
    if (!conv || conv.isDraft) return;

    const targetGroup = options.groupName
      ? groups.value.find(g => g.name === options.groupName)
      : undefined;
    // 根容器省略 target；组内排序必须带上 GROUP，避免被挪到根
    const targetParams = targetGroup
      ? {
        target_node_type: 'GROUP' as const,
        target_node_uid: targetGroup.id,
      }
      : {};

    const moveBefore = async (sourceUid: string, beforeUid?: string) => {
      await AiAssistantManageService.moveSidebarNode({
        source_node_type: 'CONVERSATION',
        source_node_uid: sourceUid,
        ...targetParams,
        ...(beforeUid ? {
          before_node_type: 'CONVERSATION' as const,
          before_node_uid: beforeUid,
        } : {}),
      });
    };

    if (options.toEnd) {
      const siblings = conversations.value.filter(c => (
        c.id !== id
        && !c.isDraft
        && (options.groupName ? c.groupName === options.groupName : !c.groupName)
      ));
      const last = siblings[siblings.length - 1];
      if (!last) {
        await moveBefore(id);
      } else {
        await moveBefore(id, last.id);
        await moveBefore(last.id, id);
      }
    } else if (options.beforeId) {
      await moveBefore(id, options.beforeId);
    } else {
      await moveBefore(id);
    }
    await initSidebar();
    // 组内排序：保留子节点避免闪屏，再静默重拉该组以同步顺序（加载期间仍展示旧列表）
    if (targetGroup) {
      const latest = groups.value.find(g => g.id === targetGroup.id);
      if (latest) {
        await loadGroupConversations(latest.id, { force: true });
      }
    }
  };

  const updateConversationTitle = async (id: string, title: string) => {
    const nextTitle = title.trim();
    if (!nextTitle) return;
    if (draftConversation.value?.id === id) {
      draftConversation.value.title = nextTitle;
      return;
    }
    const conv = conversations.value.find(c => c.id === id);
    if (!conv) return;
    await AiAssistantManageService.updateConversation({
      conversation_uid: id,
      title: nextTitle,
    });
    conv.title = nextTitle;
  };

  const createGroup = async (name: string) => {
    const group = await AiAssistantManageService.createConversationGroup({ name });
    await initSidebar();
    return group;
  };

  /**
   * 根列表分组排序。beforeId：插到该分组前；toEnd：移到末尾（协议只有 before/最前，末尾用两次 move 对齐）。
   */
  const reorderGroup = async (
    id: string,
    options: { beforeId?: string; toEnd?: boolean },
  ) => {
    const group = groups.value.find(g => g.id === id);
    if (!group) return;

    const moveBefore = async (sourceUid: string, beforeUid?: string) => {
      await AiAssistantManageService.moveSidebarNode({
        source_node_type: 'GROUP',
        source_node_uid: sourceUid,
        ...(beforeUid ? {
          before_node_type: 'GROUP' as const,
          before_node_uid: beforeUid,
        } : {}),
      });
    };

    if (options.toEnd) {
      const siblings = groups.value.filter(g => g.id !== id);
      const last = siblings[siblings.length - 1];
      if (!last) {
        await moveBefore(id);
      } else {
        await moveBefore(id, last.id);
        await moveBefore(last.id, id);
      }
    } else if (options.beforeId) {
      await moveBefore(id, options.beforeId);
    } else {
      await moveBefore(id);
    }
    await initSidebar();
  };

  const renameGroup = async (groupId: string, name: string) => {
    await AiAssistantManageService.updateConversationGroup({
      group_uid: groupId,
      name,
    });
    await initSidebar();
  };

  // keepConversations 仅供调用方区分二次确认文案，协议侧删分组会清理组内会话
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const deleteGroup = async (groupName: string, _keepConversations: boolean) => {
    const group = groups.value.find(g => g.name === groupName);
    if (!group) return;
    // 协议：删分组会清理组内会话，keepConversations 仅保留前端二次确认文案差异
    await AiAssistantManageService.deleteConversationGroup({ group_uid: group.id });
    if (activeConversationId.value
      && !conversations.value.find(c => c.id === activeConversationId.value && c.groupName !== groupName)) {
      // 刷新后再判断
    }
    await initSidebar();
    if (activeConversationId.value && !conversations.value.find(c => c.id === activeConversationId.value)) {
      activeConversationId.value = null;
    }
  };

  const clearAllConversations = async () => {
    await AiAssistantManageService.clearConversations();
    draftConversation.value = null;
    activeConversationId.value = null;
    stopAllMessagePolls();
    await initSidebar();
  };

  /**
   * 懒创建：只进入本地选系统草稿，确认系统后再 POST /conversations/
   */
  const createLogConversation = (prompt: string) => {
    const id = `draft-${Date.now()}`;
    const displayText = prompt === '请帮我检索审计日志' ? '审计日志检索' : prompt;
    const conversation = createEmptyConversation({
      id,
      title: '新对话',
      pinned: false,
      sceneType: 'log',
      isDraft: true,
      messagesHydrated: true,
      createdAt: Date.now(),
      messages: [
        {
          id: `${id}-user`,
          role: 'user',
          type: 'text',
          content: displayText,
        },
        {
          id: `${id}-select-system`,
          role: 'assistant',
          type: 'select-system',
          status: 'pending',
          systemIds: [],
          systems: [],
        },
      ],
    });
    draftConversation.value = conversation;
    activeConversationId.value = id;
    return conversation;
  };

  const findSelectSystemMessage = (conv: Conversation, messageId?: string) => {
    if (messageId) {
      return conv.messages.find(m => m.id === messageId && m.type === 'select-system');
    }
    return [...conv.messages].reverse().find(m => m.type === 'select-system');
  };

  const confirmSystem = async (
    messageId: string,
    systemIds: string[],
    systems: SelectedSystem[],
  ) => {
    const conv = activeConversation.value;
    if (!conv) return null;

    const msg = findSelectSystemMessage(conv, messageId);
    if (!msg) return null;

    const postSystemSelection = async (conversationUid: string) => (
      AiAssistantManageService.createMessage({
        conversation_uid: conversationUid,
        message_type: 'SYSTEM_SELECTION',
        input_data: {
          system_ids: systemIds,
        },
      })
    );

    if (conv.isDraft) {
      const created = await AiAssistantManageService.createConversation({
        title: conv.title || '新对话',
      });
      const realId = created.uid;
      const systemMessage = await postSystemSelection(realId);

      const nextMessages = conv.messages.filter(item => item.id !== msg.id);
      const realConversation = createEmptyConversation({
        id: realId,
        title: created.title || conv.title || '新对话',
        pinned: false,
        sceneType: 'log',
        systemIds: [...systemIds],
        systems: [...systems],
        messagesHydrated: true,
        messages: nextMessages,
        createdAt: created.created_at ? Date.parse(created.created_at) || Date.now() : Date.now(),
      });

      draftConversation.value = null;
      conversations.value.unshift(realConversation);
      activeConversationId.value = realId;
      upsertConversationMessage(realId, systemMessage);

      await initSidebar();
      return realConversation;
    }

    // 已有会话切系统：落库新的 SYSTEM_SELECTION
    conv.messages = conv.messages.filter(item => item.id !== msg.id);
    const systemMessage = await postSystemSelection(conv.id);
    upsertConversationMessage(conv.id, systemMessage);
    return conv;
  };

  const closeSelectSystem = (messageId: string) => {
    const conv = activeConversation.value;
    if (!conv) return;
    conv.messages = conv.messages.filter(item => item.id !== messageId);
    if (conv.isDraft) {
      draftConversation.value = null;
      activeConversationId.value = null;
    }
  };

  const reselectSystem = () => {
    const conv = activeConversation.value;
    if (!conv) return;
    conv.messages = conv.messages.filter(item => item.type !== 'retrieval-guide' && item.type !== 'select-system');
    conv.messages.push({
      id: `${conv.id}-select-system-${Date.now()}`,
      role: 'assistant',
      type: 'select-system',
      status: 'pending',
      systemIds: [...conv.systemIds],
      systems: [...conv.systems],
    });
  };

  /**
   * 自然语言检索：POST NL → PROCESSING 轮询 → SUCCESS 后 AFTER 拉子 LOG_SEARCH。
   */
  const sendLogQuery = async (content: string) => {
    const conv = activeConversation.value;
    if (!conv || conv.isDraft) return;
    const text = content.trim();
    if (!text) return;

    const stamp = Date.now();
    conv.messages.push({
      id: `${conv.id}-query-${stamp}`,
      role: 'user',
      type: 'text',
      content: text,
    });

    try {
      const message = await AiAssistantManageService.createMessage({
        conversation_uid: conv.id,
        message_type: 'NATURAL_LANGUAGE_SEARCH',
        input_data: {
          query_text: text,
          auto_execute: true,
        },
      });
      upsertConversationMessage(conv.id, message);
      if (message.status === 'PROCESSING') {
        startMessagePoll(conv.id, message.uid);
      } else {
        await handleNlTerminalStatus(conv.id, message);
      }
    } catch {
      // 033 未选系统等由全局中间件提示；补一条失败占位便于感知
      conv.messages.push({
        id: `${conv.id}-nl-error-${stamp}`,
        role: 'assistant',
        type: 'retrieval-result',
        content: text,
        apiStatus: 'FAILED',
        messageType: 'NATURAL_LANGUAGE_SEARCH',
        errorMessage: '发送失败，请确认已选择系统后重试',
      });
    }
  };

  /**
   * 条件筛选同步检索：POST LOG_SEARCH，响应当最终态。
   * 结果在条件卡内嵌展示，不写入消息列表，避免底部再追加一张结果卡。
   */
  const sendConditionSearch = async (condition: AiSearchCondition) => {
    const conv = activeConversation.value;
    if (!conv || conv.isDraft) {
      throw new Error('请先选择系统并创建会话');
    }
    const message = await AiAssistantManageService.createMessage({
      conversation_uid: conv.id,
      message_type: 'LOG_SEARCH',
      input_data: { condition },
    });
    const fieldCatalog = buildFieldCatalog(conv.standardFields, conv.extensionFields);
    return mapAiMessageToChatMessage(message, { fieldCatalog });
  };

  const retryMessage = async (messageUid: string) => {
    const conv = activeConversation.value;
    if (!conv || conv.isDraft) return;
    const message = await AiAssistantManageService.retryMessage({ message_uid: messageUid });
    upsertConversationMessage(conv.id, message);
    if (message.status === 'PROCESSING') {
      startMessagePoll(conv.id, message.uid);
    } else {
      await handleNlTerminalStatus(conv.id, message);
    }
  };

  return {
    sidebarCollapsed,
    sidebarLoading,
    messageLoading,
    activeConversationId,
    groups,
    conversations,
    draftConversation,
    activeConversation,
    toggleSidebar,
    initSidebar,
    loadGroupConversations,
    setActiveConversation,
    loadConversationMessages,
    loadOlderMessages,
    deleteConversation,
    updateConversationGroup,
    reorderConversation,
    updateConversationTitle,
    createGroup,
    reorderGroup,
    renameGroup,
    deleteGroup,
    clearAllConversations,
    createLogConversation,
    confirmSystem,
    closeSelectSystem,
    reselectSystem,
    sendLogQuery,
    sendConditionSearch,
    retryMessage,
    stopAllMessagePolls,
  };
}
