"""
Optimistic Lock & Node Snapshot domain module.

承载跨领域复用的乐观锁校验（check_optimistic_lock）、节点语义快照（get_snapshot_and_hash）
以及节点更新后的协作任务冲销（supersede_tasks_for_node_update）。

该能力被 requirements_core 与 collaboration 共同使用；为避免形成
requirements_core -> collaboration -> ai_interaction -> requirements_core 的依赖环，
独立为基础设施模块，并通过 public.py 暴露稳定入口。
"""
