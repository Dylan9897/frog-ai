"""
RAG Agent API 路由
需要在 server.py 中注册这些路由
"""
from flask import Blueprint, request, jsonify
from .database import DatabaseManager
from .services.document_service import DocumentService
from .models import DocumentStatus

# 创建蓝图
rag_bp = Blueprint('rag', __name__, url_prefix='/api/rag')

# 初始化服务
_db = DatabaseManager()
_doc_service = DocumentService(_db)


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
    """
    获取文档详情
    输出: {
      "success": bool,
      "document": Document.to_dict()
    }
    """
    # TODO: 实现文档详情查询
    pass


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
      - format: 返回格式（image/png, text, json）
    输出: {
      "success": bool,
      "page": PageContent.to_dict()
    }
    """
    # TODO: 实现页面内容获取
    pass


@rag_bp.route('/documents/<document_id>/parsed-text', methods=['GET'])
def get_parsed_text(document_id: str):
    """
    获取解析后的文本流
    查询参数:
      - page: 页码（可选）
    输出: {
      "success": bool,
      "parsed_text": ParsedText.to_dict()
    }
    """
    # TODO: 实现解析文本获取
    pass


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
    """
    获取文档的知识切片列表
    查询参数:
      - status: 切片状态
      - page: 页码
      - page_size: 每页数量
    输出: {
      "success": bool,
      "chunks": [Chunk.to_dict()],
      "total": int,
      "page": int,
      "page_size": int
    }
    """
    # TODO: 实现切片列表查询
    pass


@rag_bp.route('/documents/<document_id>/chunks', methods=['POST'])
def create_chunk(document_id: str):
    """
    创建知识切片
    输入: {
      "content": str,
      "source_page": int,
      "start_char": int,
      "end_char": int,
      "tags": [str]
    }
    输出: {
      "success": bool,
      "chunk": Chunk.to_dict()
    }
    """
    # TODO: 实现切片创建
    pass


@rag_bp.route('/chunks/<chunk_id>', methods=['PUT'])
def update_chunk(chunk_id: str):
    """
    更新知识切片
    输入: {
      "content": str (可选),
      "tags": [str] (可选),
      "source_page": int (可选)
    }
    输出: {
      "success": bool,
      "chunk": Chunk.to_dict()
    }
    """
    # TODO: 实现切片更新
    pass


@rag_bp.route('/chunks/<chunk_id>', methods=['DELETE'])
def delete_chunk(chunk_id: str):
    """
    删除知识切片
    输出: {
      "success": bool,
      "message": str
    }
    """
    # TODO: 实现切片删除
    pass


@rag_bp.route('/chunks/<chunk_id>/confirm', methods=['POST'])
def confirm_chunk(chunk_id: str):
    """
    确认切片入库
    输入: {
      "status": str  # "confirmed" 或 "archived"
    }
    输出: {
      "success": bool,
      "chunk": Chunk.to_dict()
    }
    """
    # TODO: 实现切片确认
    pass


@rag_bp.route('/documents/<document_id>/auto-chunk', methods=['POST'])
def auto_chunk(document_id: str):
    """
    自动分块（从文档生成切片）
    输入: {
      "chunker_type": str,  # "semantic" 或 "rule"
      "chunk_size": int,
      "chunk_overlap": int,
      "min_chunk_size": int
    }
    输出: {
      "success": bool,
      "task_id": str,
      "chunks_created": int,
      "message": str
    }
    """
    # TODO: 实现自动分块
    # 1. 获取文档解析后的文本
    # 2. 使用分块器进行分块
    # 3. 创建切片记录
    # 4. 返回结果
    pass

