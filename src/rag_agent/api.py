"""
RAG Agent API 路由
需要在 server.py 中注册这些路由
"""
from flask import Blueprint, request, jsonify
from .database import DatabaseManager
from .services.document_service import DocumentService
from .services.text_parsing_service import TextParsingService
from .services.chunk_service import ChunkService
from .models import DocumentStatus, ChunkStatus

# 创建蓝图
rag_bp = Blueprint('rag', __name__, url_prefix='/api/rag')

# 初始化服务
_db = DatabaseManager()
_doc_service = DocumentService(_db)
_text_parsing_service = TextParsingService(_db)
_chunk_service = ChunkService(_db)


# ==================== 文档管理接口 ====================

@rag_bp.route('/documents/upload', methods=['POST'])
def upload_document():
    """上传文档"""
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "未上传文件"}), 400
        
        file = request.files['file']
        if not file.filename:
            return jsonify({"success": False, "error": "文件名为空"}), 400
        
        name = request.form.get('name')
        document = _doc_service.upload_document(file, name)
        
        return jsonify({
            "success": True,
            "document": document.to_dict()
        }), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"上传失败: {str(e)}"}), 500


@rag_bp.route('/documents', methods=['GET'])
def list_documents():
    """获取文档列表"""
    try:
        status_str = request.args.get('status')
        status = DocumentStatus(status_str) if status_str else None
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        
        print(f"[API] 获取文档列表: status={status}, page={page}, page_size={page_size}")
        result = _doc_service.list_documents(status, page, page_size)
        print(f"[API] 查询到 {len(result['documents'])} 个文档，总计 {result['total']} 个")
        
        return jsonify({
            "success": True,
            "documents": [doc.to_dict() for doc in result["documents"]],
            "total": result["total"],
            "page": result["page"],
            "page_size": result["page_size"]
        }), 200
    except Exception as e:
        print(f"[API] 获取文档列表失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@rag_bp.route('/documents/<document_id>', methods=['GET'])
def get_document(document_id: str):
    """获取文档详情"""
    try:
        document = _doc_service.get_document(document_id)
        if not document:
            return jsonify({"success": False, "error": "文档未找到"}), 404
        return jsonify({"success": True, "document": document.to_dict()}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@rag_bp.route('/documents/<document_id>', methods=['DELETE'])
def delete_document(document_id: str):
    """
    删除文档
    输出: {
      "success": bool,
      "message": str
    }
    """
    try:
        print(f"[API] 收到删除文档请求: {document_id}")
        success = _doc_service.delete_document(document_id)
        print(f"[API] 删除结果: {success}")
        if success:
            return jsonify({
                "success": True,
                "message": "文档删除成功"
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": "文档不存在或删除失败"
            }), 404
    except Exception as e:
        print(f"[API] 删除文档异常: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"删除失败: {str(e)}"
        }), 500


# ==================== 文档解析接口 ====================

@rag_bp.route('/documents/<document_id>/pages/<int:page_number>', methods=['GET'])
def get_page_content(document_id: str, page_number: int):
    """
    获取文档页面内容（PDF预览）
    查询参数:
      - format: 返回格式（image/png, image/jpeg）
    输出: {
      "success": bool,
      "page": {
        "page_number": int,
        "image_url": str,  # 图片 URL
        "width": int,
        "height": int
      }
    }
    """
    try:
        from flask import send_file
        from pathlib import Path
        
        # 获取页面信息
        page_info = _db.get_page(document_id, page_number)
        if not page_info:
            return jsonify({
                "success": False,
                "error": f"页面 {page_number} 不存在"
            }), 404
        
        image_path = Path(page_info['image_path'])
        if not image_path.exists():
            return jsonify({
                "success": False,
                "error": "图片文件不存在"
            }), 404
        
        # 返回图片文件
        return send_file(
            str(image_path),
            mimetype=f"image/{page_info.get('format', 'png')}",
            as_attachment=False
        )
    except Exception as e:
        print(f"[API] 获取页面内容失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@rag_bp.route('/documents/<document_id>/pages', methods=['GET'])
def list_pages(document_id: str):
    """
    获取文档的所有页面信息
    输出: {
      "success": bool,
      "pages": [
        {
          "page_number": int,
          "image_url": str,
          "width": int,
          "height": int
        }
      ],
      "total": int
    }
    """
    try:
        pages = _db.list_pages(document_id)
        pages_data = []
        for page in pages:
            pages_data.append({
                "page_number": page['page_number'],
                "image_url": f"/api/rag/documents/{document_id}/pages/{page['page_number']}",
                "width": page.get('width'),
                "height": page.get('height'),
                "format": page.get('format', 'png')
            })
        
        return jsonify({
            "success": True,
            "pages": pages_data,
            "total": len(pages_data)
        }), 200
    except Exception as e:
        print(f"[API] 获取页面列表失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@rag_bp.route('/documents/<document_id>/parsed-text', methods=['GET'])
def get_parsed_text(document_id: str):
    """
    获取解析后的文本流
    查询参数:
      - page: 页码（可选，对 PDF 有效；其他类型忽略）
    输出: {
      "success": bool,
      "content": str,  # Markdown 文本
      "page_number": int or null
    }
    """
    try:
        # 先获取文档信息，用于判断类型
        document = _doc_service.get_document(document_id)
        if not document:
            return jsonify({
                "success": False,
                "error": "文档未找到"
            }), 404

        page = request.args.get('page', type=int)

        # 对于非 PDF 文档，忽略 page 参数，直接返回整篇解析结果
        if document.file_type.lower() != "pdf":
            page = None

        content = _text_parsing_service.get_parsed_text(document_id, page)

        if content:
            return jsonify({
                "success": True,
                "content": content,
                "page_number": page
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": "解析文本未找到",
                "content": "",
                "page_number": page
            }), 404
    except Exception as e:
        print(f"[API] 获取解析文本失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@rag_bp.route('/documents/<document_id>/parsed-text/stream', methods=['GET'])
def stream_parsed_text(document_id: str):
    """
    流式获取解析后的文本（用于 PDF 实时显示）
    查询参数:
      - page: 页码（必需）
    输出: Server-Sent Events (SSE) 流
    """
    from flask import Response, stream_with_context
    
    try:
        page = request.args.get('page', type=int)
        if not page:
            return jsonify({"success": False, "error": "缺少 page 参数"}), 400
        
        # 获取文档信息
        document = _doc_service.get_document(document_id)
        if not document:
            return jsonify({"success": False, "error": "文档未找到"}), 404
        
        # 如果是 PDF，使用流式解析
        if document.file_type.lower() == 'pdf':
            def generate():
                from src.rag_agent.parsers.pdf_vl_parser import PDFVLParser
                parser = PDFVLParser()
                
                for chunk in parser.parse_page_stream(str(document.file_path), page):
                    # 确保chunk是字符串
                    chunk_str = chunk if isinstance(chunk, str) else str(chunk)
                    yield f"data: {chunk_str}\n\n"
            
            return Response(
                stream_with_context(generate()),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'X-Accel-Buffering': 'no'
                }
            )
        else:
            # 非 PDF 文件，直接返回已解析的文本
            content = _text_parsing_service.get_parsed_text(document_id, page)
            if content:
                def generate():
                    yield f"data: {content}\n\n"
                
                return Response(
                    stream_with_context(generate()),
                    mimetype='text/event-stream'
                )
            else:
                return jsonify({"success": False, "error": "解析文本未找到"}), 404
    except Exception as e:
        print(f"[API] 流式获取解析文本失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@rag_bp.route('/documents/<document_id>/parse', methods=['POST'])
def parse_document(document_id: str):
    """
    触发文档解析
    输入: {
      "force_reparse": bool,
      "parser_options": dict
    }
    输出: {
      "success": bool,
      "task_id": str,
      "status": str,
      "message": str
    }
    """
    # TODO: 实现文档解析任务创建
    # 1. 创建解析任务
    # 2. 异步执行解析
    # 3. 返回任务ID
    pass


# ==================== 知识切片接口 ====================

@rag_bp.route('/documents/<document_id>/chunks', methods=['GET'])
def list_chunks(document_id: str):
    """获取文档的知识切片列表"""
    try:
        status_str = request.args.get('status')
        status = ChunkStatus(status_str) if status_str else None
        page = request.args.get('page', default=1, type=int)
        page_size = request.args.get('page_size', default=20, type=int)

        result = _chunk_service.list_chunks(document_id, status, page, page_size)
        return jsonify(
            {
                "success": True,
                "chunks": [chunk.to_dict() for chunk in result["chunks"]],
                "total": result["total"],
                "page": result["page"],
                "page_size": result["page_size"],
            }
        ), 200
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@rag_bp.route('/documents/<document_id>/chunks', methods=['POST'])
def create_chunk(document_id: str):
    """创建知识切片"""
    try:
        data = request.get_json(force=True) or {}
        content = (data.get("content") or "").strip()
        source_page = data.get("source_page")
        if not content:
            return jsonify({"success": False, "error": "content 不能为空"}), 400
        if source_page is None:
            source_page = 1

        tags = data.get("tags") or []
        start_char = data.get("start_char")
        end_char = data.get("end_char")

        chunk = _chunk_service.create_chunk(
            document_id=document_id,
            content=content,
            source_page=int(source_page),
            tags=tags,
            start_char=start_char,
            end_char=end_char,
        )
        return jsonify({"success": True, "chunk": chunk.to_dict()}), 201
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@rag_bp.route('/chunks/<chunk_id>', methods=['PUT'])
def update_chunk(chunk_id: str):
    """更新知识切片"""
    try:
        data = request.get_json(force=True) or {}
        content = data.get("content")
        tags = data.get("tags")
        source_page = data.get("source_page")

        chunk = _chunk_service.update_chunk(
            chunk_id=chunk_id,
            content=content,
            tags=tags,
            source_page=source_page,
        )
        if not chunk:
            return jsonify({"success": False, "error": "切片未找到"}), 404
        return jsonify({"success": True, "chunk": chunk.to_dict()}), 200
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@rag_bp.route('/chunks/<chunk_id>', methods=['DELETE'])
def delete_chunk(chunk_id: str):
    """删除知识切片"""
    try:
        success = _chunk_service.delete_chunk(chunk_id)
        if success:
            return jsonify({"success": True, "message": "切片已删除"}), 200
        return jsonify({"success": False, "error": "切片未找到"}), 404
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@rag_bp.route('/chunks/<chunk_id>/confirm', methods=['POST'])
def confirm_chunk(chunk_id: str):
    """确认切片入库 / 归档"""
    try:
        data = request.get_json(force=True) or {}
        status_str = (data.get("status") or "").lower()
        if status_str == "archived":
            status = ChunkStatus.ARCHIVED
        else:
            status = ChunkStatus.CONFIRMED

        chunk = _chunk_service.confirm_chunk(chunk_id, status=status)
        if not chunk:
            return jsonify({"success": False, "error": "切片未找到"}), 404
        return jsonify({"success": True, "chunk": chunk.to_dict()}), 200
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@rag_bp.route('/documents/<document_id>/auto-chunk', methods=['POST'])
def auto_chunk(document_id: str):
    """
    自动分块（从文档生成知识切片，默认使用大模型语义分块）
    """
    try:
        data = request.get_json(force=True) or {}
        chunker_type = data.get("chunker_type", "semantic")
        chunk_size = int(data.get("chunk_size", 500))
        chunk_overlap = int(data.get("chunk_overlap", 50))
        min_chunk_size = int(data.get("min_chunk_size", 100))

        chunks = _chunk_service.auto_chunk(
            document_id=document_id,
            chunker_type=chunker_type,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            min_chunk_size=min_chunk_size,
        )
        return jsonify(
            {
                "success": True,
                "chunks_created": len(chunks),
                "chunks": [c.to_dict() for c in chunks],
            }
        ), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

