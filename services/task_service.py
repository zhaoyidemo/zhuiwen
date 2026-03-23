"""后台任务状态管理（内存存储）"""
import uuid
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# 内存中的任务状态存储
_tasks: dict[str, dict] = {}

# 最多保留 200 个任务状态
MAX_TASKS = 200


def create_task(name: str = "") -> str:
    """创建一个新任务，返回 task_id"""
    task_id = f"t_{uuid.uuid4().hex[:12]}"
    _tasks[task_id] = {
        "task_id": task_id,
        "name": name,
        "status": "running",
        "progress": "",
        "result": None,
        "error": None,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": None,
    }
    # 清理过旧的任务
    if len(_tasks) > MAX_TASKS:
        oldest = sorted(_tasks.keys(), key=lambda k: _tasks[k]["created_at"])
        for k in oldest[:len(_tasks) - MAX_TASKS]:
            del _tasks[k]
    return task_id


def update_progress(task_id: str, progress: str) -> None:
    """更新任务进度"""
    if task_id in _tasks:
        _tasks[task_id]["progress"] = progress


def complete_task(task_id: str, result: dict = None) -> None:
    """标记任务完成"""
    if task_id in _tasks:
        _tasks[task_id]["status"] = "done"
        _tasks[task_id]["result"] = result
        _tasks[task_id]["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def fail_task(task_id: str, error: str) -> None:
    """标记任务失败"""
    if task_id in _tasks:
        _tasks[task_id]["status"] = "failed"
        _tasks[task_id]["error"] = error
        _tasks[task_id]["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_task(task_id: str) -> dict | None:
    """查询任务状态"""
    return _tasks.get(task_id)
