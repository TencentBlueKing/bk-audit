from bk_resource.routers import ResourceRouter
from django.urls import include, path

from services.web.ai_assistant import views

router = ResourceRouter()
# 手工注册保留 conversation_sidebar/nodes 的嵌套语义，避免将内部 Node ID 暴露为详情主键。
router.register("conversation_groups", views.ConversationGroupsViewSet)
router.register("conversations", views.ConversationsViewSet)
router.register("messages", views.MessagesViewSet)
router.register("attachments", views.AttachmentsViewSet)
router.register("feedback", views.FeedbackViewSet)
router.register("conversation_sidebar", views.ConversationSidebarViewSet)
router.register("conversation_sidebar/nodes", views.ConversationSidebarNodesViewSet)

urlpatterns = (path("", include(router.urls)),)
