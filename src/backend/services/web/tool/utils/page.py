from django.core.paginator import Paginator


def paginate_queryset(queryset, request):
    query_params = request.query_params
    if "page" not in query_params or "page_size" not in query_params:
        # 不传分页参数，直接全量返回
        return list(queryset), {
            "total": len(queryset),
            "page": None,
            "page_size": None,
        }

    page = int(query_params["page"])
    page_size = int(query_params["page_size"])

    paginator = Paginator(queryset, page_size)
    page_obj = paginator.page(page)

    return page_obj.object_list, {
        "total": paginator.count,
        "page": page,
        "page_size": page_size,
    }
