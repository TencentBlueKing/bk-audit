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
  AiSidebarConversationNode,
  AiSidebarGroupNode,
  AiSidebarNode,
} from '@model/ai-assistant/types';

import { buildMockRetrievalResult } from '../audit-log-retrieval/utils/build-mock-result';
import type {
  Conversation,
  Group,
  SelectedSystem,
} from '../types';
import {
  findLatestSuccessSystemSelection,
  mapAiMessageToChatMessage,
} from '../utils/map-ai-message';

const MESSAGE_POLL_INTERVAL_MS = 2000;

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

const upsertConversationMessage = (conversationId: string, message: AiMessage) => {
  const conv = conversations.value.find(c => c.id === conversationId)
    || (draftConversation.value?.id === conversationId ? draftConversation.value : null);
  if (!conv) return;

  const chatMessage = mapAiMessageToChatMessage(message);
  const idx = conv.messages.findIndex(item => item.id === message.uid);
  if (idx >= 0) {
    conv.messages.splice(idx, 1, chatMessage);
  } else {
    conv.messages.push(chatMessage);
  }

  if (message.message_type === 'SYSTEM_SELECTION' && message.status === 'SUCCESS') {
    const systems = chatMessage.systems || [];
    conv.systems = systems;
    conv.systemIds = systems.map(item => item.id);
    conv.selectedSystemMessageUid = message.uid;
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
    if (message.status === 'PROCESSING') {
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
  const mapped = windowData.results.map(mapAiMessageToChatMessage);
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
  if (mode !== 'prepend') {
    const latestSystem = findLatestSuccessSystemSelection(windowData.results);
    if (latestSystem) {
      const systems = mapAiMessageToChatMessage(latestSystem).systems || [];
      conv.systems = systems;
      conv.systemIds = systems.map(item => item.id);
      conv.selectedSystemMessageUid = latestSystem.uid;
    }
  }
  /* eslint-enable no-param-reassign */

  resumeProcessingPolls(conv.id, windowData.results);
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
        conversations.value = [
          ...conversations.value.filter(c => c.groupName !== latest.name),
          ...mergeConversationCache(mapped, messageCache),
        ];
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

      const nextGroups: Group[] = groupNodes.map(groupNode => ({
        id: groupNode.node_uid,
        name: groupNode.name,
        conversationCount: groupNode.conversation_count,
        childrenLoaded: false,
        childrenLoading: false,
      }));

      const messageCache = snapshotMessageCache();
      // 当前打开的分组会话先保留，避免根刷新到分组重拉之间主区消息被冲掉
      const activeId = activeConversationId.value;
      const activeKeep = activeId
        ? conversations.value.find(c => c.id === activeId && c.groupName)
        : undefined;

      conversations.value = mergeConversationCache(rootConversations, messageCache);
      if (activeKeep && !conversations.value.some(c => c.id === activeKeep.id)) {
        conversations.value.push(mergeConversationCache([activeKeep], messageCache)[0]);
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
      if (message.apiStatus === 'PROCESSING') {
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
    const targetGroup = groupName
      ? groups.value.find(g => g.name === groupName)
      : undefined;

    await AiAssistantManageService.moveSidebarNode({
      source_node_type: 'CONVERSATION',
      source_node_uid: id,
      ...(targetGroup ? {
        target_node_type: 'GROUP' as const,
        target_node_uid: targetGroup.id,
      } : {}),
    });
    await initSidebar();
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

  const updateGroups = async (newGroups: Group[]) => {
    // 侧栏拖拽排序：逐个与相邻 before 锚点对齐（根列表）
    groups.value = newGroups;
    for (let i = 0; i < newGroups.length; i += 1) {
      const current = newGroups[i];
      const before = newGroups[i + 1];
      try {
        await AiAssistantManageService.moveSidebarNode({
          source_node_type: 'GROUP',
          source_node_uid: current.id,
          ...(before ? {
            before_node_type: 'GROUP' as const,
            before_node_uid: before.id,
          } : {}),
        });
      } catch {
        // 单次失败继续
      }
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

    // TODO(下周)：input_data Schema 就绪后，创建时改回带 initial_message.SYSTEM_SELECTION；
    // 切系统时改回 POST /messages/。本期先空会话联调侧栏/会话 CRUD。
    if (conv.isDraft) {
      const created = await AiAssistantManageService.createConversation({
        title: conv.title || '新对话',
      });

      const realId = created.uid;
      const nextMessages = conv.messages.filter(item => item.id !== msg.id);
      nextMessages.push({
        id: `${realId}-retrieval-guide`,
        role: 'assistant',
        type: 'retrieval-guide',
        systems: [...systems],
        systemIds: [...systemIds],
      });

      const realConversation = createEmptyConversation({
        id: realId,
        title: created.title || conv.title || '新对话',
        pinned: false,
        sceneType: 'log',
        systemIds: [...systemIds],
        systems: [...systems],
        selectedSystemMessageUid: null,
        // 联调期消息仅本地；标 hydrated 避免随即按空历史回拉冲掉引导卡
        messagesHydrated: true,
        messages: nextMessages,
        createdAt: created.created_at ? Date.parse(created.created_at) || Date.now() : Date.now(),
      });

      draftConversation.value = null;
      conversations.value.unshift(realConversation);
      activeConversationId.value = realId;

      await initSidebar();
      return realConversation;
    }

    // 已有会话切系统：暂只更新本地，待 SYSTEM_SELECTION Schema 就绪后再落库
    conv.systemIds = [...systemIds];
    conv.systems = [...systems];
    conv.selectedSystemMessageUid = null;
    conv.messages = conv.messages.filter(item => item.id !== msg.id);
    conv.messages.push({
      id: `${conv.id}-retrieval-guide-${Date.now()}`,
      role: 'assistant',
      type: 'retrieval-guide',
      systems: [...systems],
      systemIds: [...systemIds],
    });
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
   * 检索发送：三类消息 Schema 未到前仍走本地 mock 结果卡。
   * Service.createMessage 已就绪，下周 Schema 到后在此切换。
   */
  const sendLogQuery = (content: string) => {
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
    conv.messages.push({
      id: `${conv.id}-result-${stamp}`,
      role: 'assistant',
      type: 'retrieval-result',
      content: text,
      result: buildMockRetrievalResult(text),
    });
  };

  const retryMessage = async (messageUid: string) => {
    const conv = activeConversation.value;
    if (!conv || conv.isDraft) return;
    const message = await AiAssistantManageService.retryMessage({ message_uid: messageUid });
    upsertConversationMessage(conv.id, message);
    if (message.status === 'PROCESSING') {
      startMessagePoll(conv.id, message.uid);
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
    updateGroups,
    renameGroup,
    deleteGroup,
    clearAllConversations,
    createLogConversation,
    confirmSystem,
    closeSelectSystem,
    reselectSystem,
    sendLogQuery,
    retryMessage,
    stopAllMessagePolls,
  };
}
