# 知识溯源引用转 URL 实现方案

## 1. 背景与目标

**目标**：将引用转换为可点击的 URL 链接，用户点击后：
1. 请求本后端
2. 后端根据文件名在 PageIndex 缓存中查找文档 ID
3. 调用 PageIndex API 获取文档内容
4. 返回内容供前端展示

---

## 2. 引用格式（已约定于 prompts_cust.py）

格式：`[Source: 《文件名》， page X-Y]` 或 `[Source: 《文件名》，第X-Y页]`

示例：
- `[Source: 《Guides_ASEAN 6 wide.pdf》， page 1-2]`
- `[Source: 《Dezshira_BI_Case Study_LaFrance_Multi-Country Benchmarking_Vietnam and Thailand.pdf》，第3-4页]`

文件名必须与 `list_pageindex_documents` 返回的 `name` 完全一致。

**前端**：抽取 `《》` 之间的内容作为 filename，构建链接。正则：`《([^》]+)》`

---

## 3. PageIndex API 页码调研结论

### 3.1 OCR API 能力

| 项目 | 结论 |
|------|------|
| **页码参数** | `get_ocr(doc_id, format)` **不支持**按页请求，只能一次性获取整篇 |
| **返回结构** | `result`: `[{page_index, markdown, images}, ...]`，按页返回数组 |
| **page_index** | **1-based**（首页为 1），见 [PageIndex OCR SDK](https://docs.pageindex.ai/sdk/ocr) |

### 3.2 是否必须提供页码？

**可以不提供页码**。API 一次返回全文，后端行为可以是：

- **不传 page**：返回全部页面
- **传 page**：在后端对 `result` 做过滤，只返回指定页（Phase 2 可选）

**Phase 1 建议**：仅支持 `?file=xxx`，不实现 `page` 参数，先保证「按文件名查文档」的准确性。

---

## 4. 技术约束

**重要**：PageIndex API **不提供**原始 PDF 文件下载。它提供的是：
- **OCR 结果**：按页的 markdown 文本（`get_ocr(doc_id, format='page')`）
- **树结构**：文档结构树（`get_tree(doc_id)`）

因此本方案返回的是 **文档的 OCR/文本内容**（可渲染为 Markdown），供前端在右侧面板展示，而非 PDF 二进制。若将来需展示原始 PDF，需单独存储 PDF 并另建下载接口。

---

## 5. URL 设计

### 5.1 Phase 1 推荐格式（仅文件名）

```
GET /api/v1/knowledge/source?file={filename}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | string | 是 | 文件名，**必须与 list_documents 返回的 name 完全一致** |

**Phase 2 可选**：增加 `page` 参数，用于过滤返回的页。

### 5.2 前端引用转换

**提取规则**：抽取 `《》` 之间的内容作为文件名。

示例：`[Source: 《Guides_ASEAN 6 wide.pdf》， page 1-2]` → 文件名 = `Guides_ASEAN 6 wide.pdf`

链接：`/api/v1/knowledge/source?file=Guides_ASEAN%206%20wide.pdf`

---

## 6. 后端 API 设计

### 6.1 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/knowledge/source` | 根据文件名获取知识库文档内容 |

### 6.2 请求（Phase 1）

```
GET /api/v1/knowledge/source?file=Guides_ASEAN%206%20wide.pdf
```

### 6.3 成功响应 (200)

**Content-Type**: `application/json`

```json
{
  "code": 200,
  "data": {
    "doc_id": "pi-cmmhbhmfd01p8faqnsw3ghlcc",
    "doc_name": "Guides_ASEAN 6 wide.pdf",
    "pages": [
      {
        "page_index": 1,
        "markdown": "...",
        "images": []
      },
      {
        "page_index": 2,
        "markdown": "...",
        "images": []
      }
    ],
    "total_pages": 42
  }
}
```

- `page_index`：**1-based**，与 PageIndex API 一致
- `markdown`：该页 OCR 文本
- `images`：该页 base64 图片数组（若有）

Phase 1 返回**整篇文档**所有页；Phase 2 可增加 `page` 参数过滤。

### 6.4 错误响应

| 状态码 | 场景 | 示例 |
|--------|------|------|
| 400 | 缺少 `file` 参数 | `{"code": 400, "message": "Missing required parameter: file"}` |
| 404 | 缓存中找不到对应文档 | `{"code": 404, "message": "Document not found: Guides_ASEAN 6 wide.pdf"}` |
| 502 | PageIndex API 调用失败 | `{"code": 502, "message": "Failed to fetch document content from PageIndex"}` |
| 503 | PageIndex 未配置 | `{"code": 503, "message": "Knowledge base not available"}` |

---

## 7. 实现模块设计

### 7.1 pageindex_cache 扩展

在 `agent/research/pageindex_cache.py` 中新增：

```python
def find_doc_id_by_filename(self, filename: str) -> Optional[str]:
    """根据文件名在缓存中查找 doc_id。

    Phase 1：精确匹配 name（忽略首尾空格、大小写），与 prompt 约定配合。
    可选扩展：忽略扩展名、模糊匹配等。

    Returns:
        doc_id 或 None
    """
    if not filename or not self.documents:
        return None
    target = filename.strip().lower()
    for doc in self.documents:
        name = (doc.get("name") or "").strip().lower()
        if name == target:
            return doc.get("id") or doc.get("doc_id")
    return None

def get_page_content(self, doc_id: str, pages: Optional[str] = None) -> dict:
    """获取指定文档的 OCR 内容。

    Args:
        doc_id: PageIndex 文档 ID
        pages: （Phase 2 可选）页范围，如 "4", "2-5"。None 表示全部

    Returns:
        {"pages": [...], "total_pages": int, "status": str}
        其中 pages 每项含 page_index(1-based), markdown, images
    """
    if not self.client:
        return {"pages": [], "total_pages": 0, "status": "unavailable"}
    try:
        result = self.client.get_ocr(doc_id, format="page")
        # 解析 pages 参数，过滤出指定页
        # 返回结构化的 page 列表
        ...
    except Exception as e:
        logger.error(f"get_page_content failed: {e}")
        raise
```

### 7.2 新建 API 路由

新建 `api/routes/knowledge.py`：

```python
@router.get("/knowledge/source")
async def get_knowledge_source(file: str, page: Optional[str] = None):
    """根据文件名获取知识库文档内容，供前端展示。"""
    if not file or not file.strip():
        return error(400, "Missing required parameter: file")
    from agent.research.pageindex_cache import pageindex_cache

    doc_id = pageindex_cache.find_doc_id_by_filename(file.strip())
    if not doc_id:
        return error(404, f"Document not found: {file}")

    try:
        content = pageindex_cache.get_page_content(doc_id, pages=page)
        doc = next((d for d in pageindex_cache.documents if (d.get("id") or d.get("doc_id")) == doc_id), {})
        return success({
            "doc_id": doc_id,
            "doc_name": doc.get("name", file),
            "pages": content["pages"],
            "total_pages": content.get("total_pages", 0),
        })
    except Exception as e:
        logger.exception("Failed to fetch knowledge source")
        return error(502, "Failed to fetch document content from PageIndex")
```

在 `api/main.py` 中注册：

```python
from api.routes import completions, knowledge, messages, sessions
# ...
app.include_router(knowledge.router)
```

### 7.3 文件名匹配策略（Phase 1）

PageIndex `list_documents` 返回的 `name` 可能是：
- 原始上传文件名（如 `Guides_ASEAN 6 wide.pdf`）
- 或经处理的名称（如去空格、截断等）

**Phase 1**：与 prompt 约定配合，只需 **精确匹配**：`name == file`（可忽略首尾空格、大小写）。

可选扩展（Phase 2）：忽略扩展名、包含关系、模糊匹配等。

---

## 8. 前端集成要点

1. **解析引用**：抽取 `《》` 之间的内容作为 `filename`，正则如 `《([^》]+)》`
2. **构建链接**：`${BASE_URL}/api/v1/knowledge/source?file=${encodeURIComponent(filename)}`
3. **展示**：将 `《文件名》` 渲染为可点击链接

---

## 9. 实施步骤建议

| 步骤 | 内容 | 预估 |
|------|------|------|
| 1 | 修改 prompt：约定引用格式为 `[Source: 文件名]`，文件名与 name 完全一致 | 0.25d |
| 2 | 在 `pageindex_cache` 中实现 `find_doc_id_by_filename`（精确匹配） | 0.25d |
| 3 | 在 `pageindex_cache` 中实现 `get_page_content(doc_id)`（Phase 1 不传 pages） | 0.25d |
| 4 | 新建 `api/routes/knowledge.py` 并注册路由 | 0.25d |
| 5 | 更新 `API_SPEC.md` | 0.25d |
| 6 | 前端：引用解析 + URL 构建 + 展示逻辑 | 1d |

---

## 10. 可选扩展

- **缓存 OCR 结果**：对高频文档可做短期缓存（如 5 分钟），减少 PageIndex 调用。
- **PDF 存储**：若业务需要展示原始 PDF，可将上传时的 PDF 存到对象存储，本 API 增加 `?format=pdf` 时重定向到 PDF URL。
- **分页与懒加载**：大文档可只返回请求的 `page` 范围，避免一次拉取全量。

---

## 11. API 汇总表更新

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/knowledge/source` | 根据文件名获取知识库文档内容（OCR/markdown） |
