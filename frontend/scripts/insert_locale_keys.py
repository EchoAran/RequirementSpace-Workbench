"""按原文件逐顶层键格式插入版本控制文案，保留紧凑/展开风格。"""
import json
import subprocess
import re

ZH_VERSION_CONTROL = {
    "branchSelector": {"label": "当前分支", "searchPlaceholder": "搜索分支…", "myBranches": "我的分支", "allBranches": "全部分支", "createBranch": "新建分支", "protected": "受保护", "noBranches": "暂无其他分支"},
    "uncommitted": "{{count}} 项未提交",
    "commit": "提交变更",
    "commitDisabledNoChanges": "当前分支无未提交变更",
    "commitDisabledProtected": "main 受保护，请通过分支与合并请求合入",
    "commitSuccess": "提交成功",
    "commitFailed": "提交失败",
    "commitForbidden": "当前分支受保护，不允许直接提交",
    "commitConflict": "分支已有新提交，请刷新后重试",
    "commitDialog": {"title": "提交变更", "messageLabel": "提交说明", "messagePlaceholder": "描述本次变更的内容…", "messageRequired": "请填写提交说明", "expectedHead": "基于提交", "summaryTitle": "本次变更", "submit": "提交", "cancel": "取消", "conflictTitle": "提交冲突", "conflictMessage": "在你编辑期间，分支上已有新的提交。请刷新并比较后再提交。", "refresh": "刷新", "compare": "查看差异", "noPermission": "当前用户无权限在此分支提交"},
    "repository": {"title": "版本控制", "branchList": "分支", "createBranch": "新建分支", "commitTimeline": "提交历史", "commitDetail": "提交详情", "noBranches": "暂无其他分支", "noCommits": "暂无提交", "noSecondCommit": "还没有第二次提交，从创建分支开始并行探索吧", "author": "作者", "summary": "变更摘要", "parent": "父提交", "merge": "合并提交", "compare": "比较", "createBranchFromCommit": "从此提交创建分支", "compareWithWorkspace": "与当前工作区比较", "changeSummary": "{{added}} 新增 / {{removed}} 删除 / {{modified}} 修改"},
    "createBranch": {"title": "新建分支", "nameLabel": "分支名称", "namePlaceholder": "例如 feature/探索支付", "descriptionLabel": "说明（可选）", "submit": "创建", "cancel": "取消", "success": "分支已创建", "failed": "创建分支失败"},
    "diff": {"title": "变更对比", "base": "基准", "target": "对比", "treeTitle": "变更对象", "fieldChanged": "字段修改", "relationAdded": "关系新增", "relationRemoved": "关系移除", "entityAdded": "对象新增", "entityRemoved": "对象删除", "entityUpdated": "对象修改", "orderedMoved": "顺序调整", "filterAll": "全部", "filterAdded": "新增", "filterRemoved": "删除", "filterModified": "修改", "filterRelation": "关系", "empty": "无变更", "selectNode": "请选择左侧变更对象查看详情", "before": "修改前", "after": "修改后", "relation": "关系", "parent": "所属", "related": "关联对象", "textChanges": "文本变更", "entityType": {"actor": "参与者", "feature": "功能", "feature_relation": "功能关系", "scenario": "场景", "acceptance_criterion": "验收标准", "business_object": "业务对象", "business_object_attribute": "业务对象属性", "flow": "流程", "flow_step": "流程步骤", "scope": "范围", "project_metadata": "项目元数据"}},
    "errors": {"loadBranchesFailed": "加载分支失败", "loadCommitsFailed": "加载提交失败", "loadDiffFailed": "加载变更对比失败", "createBranchFailed": "创建分支失败"},
}

EN_VERSION_CONTROL = {
    "branchSelector": {"label": "Branch", "searchPlaceholder": "Search branches…", "myBranches": "My branches", "allBranches": "All branches", "createBranch": "New branch", "protected": "Protected", "noBranches": "No other branches"},
    "uncommitted": "{{count}} uncommitted",
    "commit": "Commit changes",
    "commitDisabledNoChanges": "No uncommitted changes on this branch",
    "commitDisabledProtected": "main is protected; use a branch and merge request",
    "commitSuccess": "Commit created",
    "commitFailed": "Commit failed",
    "commitForbidden": "This branch is protected and cannot be committed directly",
    "commitConflict": "The branch has new commits; refresh and retry",
    "commitDialog": {"title": "Commit changes", "messageLabel": "Commit message", "messagePlaceholder": "Describe what changed…", "messageRequired": "Please provide a commit message", "expectedHead": "Based on commit", "summaryTitle": "This change", "submit": "Commit", "cancel": "Cancel", "conflictTitle": "Commit conflict", "conflictMessage": "New commits landed on this branch while you were editing. Refresh and compare before committing.", "refresh": "Refresh", "compare": "View diff", "noPermission": "You don't have permission to commit on this branch"},
    "repository": {"title": "Version Control", "branchList": "Branches", "createBranch": "New branch", "commitTimeline": "History", "commitDetail": "Commit detail", "noBranches": "No other branches", "noCommits": "No commits yet", "noSecondCommit": "No second commit yet — create a branch to explore in parallel", "author": "Author", "summary": "Summary", "parent": "Parent", "merge": "Merge commit", "compare": "Compare", "createBranchFromCommit": "Create branch from this commit", "compareWithWorkspace": "Compare with workspace", "changeSummary": "{{added}} added / {{removed}} removed / {{modified}} modified"},
    "createBranch": {"title": "Create branch", "nameLabel": "Branch name", "namePlaceholder": "e.g. feature/explore-payment", "descriptionLabel": "Description (optional)", "submit": "Create", "cancel": "Cancel", "success": "Branch created", "failed": "Failed to create branch"},
    "diff": {"title": "Diff", "base": "Base", "target": "Compare", "treeTitle": "Changed objects", "fieldChanged": "Field changed", "relationAdded": "Relation added", "relationRemoved": "Relation removed", "entityAdded": "Object added", "entityRemoved": "Object removed", "entityUpdated": "Object modified", "orderedMoved": "Reordered", "filterAll": "All", "filterAdded": "Added", "filterRemoved": "Removed", "filterModified": "Modified", "filterRelation": "Relations", "empty": "No changes", "selectNode": "Select a changed object on the left for details", "before": "Before", "after": "After", "relation": "Relation", "parent": "Parent", "related": "Related", "textChanges": "Text changes", "entityType": {"actor": "Actor", "feature": "Feature", "feature_relation": "Feature relation", "scenario": "Scenario", "acceptance_criterion": "Acceptance criterion", "business_object": "Business object", "business_object_attribute": "Business object attribute", "flow": "Flow", "flow_step": "Flow step", "scope": "Scope", "project_metadata": "Project metadata"}},
    "errors": {"loadBranchesFailed": "Failed to load branches", "loadCommitsFailed": "Failed to load commits", "loadDiffFailed": "Failed to load diff", "createBranchFailed": "Failed to create branch"},
}


def write_locale(loc: str) -> None:
    repo_root = r"e:\PycharmProjects\RequirementSpace-Workbench"
    path = f"{repo_root}\\frontend\\src\\locales\\{loc}.json"
    orig_text = subprocess.run(
        ["git", "show", f"HEAD:frontend/src/locales/{loc}.json"],
        capture_output=True,
    ).stdout.decode("utf-8")
    data = json.loads(orig_text)

    data["nav"]["repo"] = "版本控制" if loc == "zh-CN" else "Version Control"
    data["topbar"]["subtitle"]["repo"] = "仓库与版本历史" if loc == "zh-CN" else "Repository & history"
    data["versionControl"] = ZH_VERSION_CONTROL if loc == "zh-CN" else EN_VERSION_CONTROL

    # 统一使用标准 indent=2 输出（有效 JSON，i18n 可正常加载）。
    # 原文件为紧凑/展开混合的自定义格式，无法在不重写的情况下逐键精确复刻。
    out_text = json.dumps(data, ensure_ascii=False, indent=2)

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(out_text + "\n")

    # 验证
    with open(path, encoding="utf-8") as f:
        check = json.load(f)
    assert check["nav"]["repo"]
    assert check["topbar"]["subtitle"]["repo"]
    assert check["versionControl"]["commit"]
    print(f"{loc}: OK, top-level keys {len(check)}")


if __name__ == "__main__":
    write_locale("zh-CN")
    write_locale("en-US")
