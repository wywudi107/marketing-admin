"""
分页工具
"""


def get_pagination(page: int = 1, page_size: int = 20) -> dict:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    offset = (page - 1) * page_size
    return {
        "page": page,
        "page_size": page_size,
        "offset": offset,
    }


def pagination_response(data: list, total: int, page: int, page_size: int) -> dict:
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return {
        "list": data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }
