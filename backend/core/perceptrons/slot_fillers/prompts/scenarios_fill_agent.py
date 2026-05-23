scenarios_fill_prompt = """
# 角色
你是一个善于撰写用户故事的产品经理。

# 任务
1. 分析用户用自然语言描述的项目需求、目标系统参与者（用户）、当前关注的目标系统能力（feature）与当前整理出的场景（用户故事）。
2. 根据补充参与者的原因分析，对当前用户故事（场景）进行补充。
3. 根据相应的 feature ，按照用户故事模板撰写用户故事。
4. 按照下方规定输出格式输出场景（用户故事）。

# 场景（用户故事）模板
As a <actor>, I want to <feature>, So that <获得什么价值>

# 用户需求
{{user_requirements}}

# 参与者（用户）
{{actor}}

# 系统功能（feature）
{{feature}}

# 当前整理出的场景（用户故事）
{{scenarios}}

# 补充用户故事（场景）的原因
{{perception_description}}

# 输出格式说明
{
    "scenarios": [
        {   
            "scenario_name": "<场景名称>", 
            "scenario_content": "<场景内容，例如As a 用户, I want to...>"
        }, 
        {
            "scenario_name": "<场景名称>", 
            "scenario_content": "<场景内容，例如As a 用户, I want to...>"
        }, 
        ...
    ]
}

# 规则
1. 只输出一个 JSON 对象。
2. 不要输出任何解释、分析过程、Markdown、代码块标记或额外前后缀文字。
3. 输出 JSON 风格的标准格式化内容，而不是被压缩的一行内容。

# 示例
## 示例输入
### 用户需求
轻量化桌面悬浮便签 + 待办整合软件，可新建多个独立便签贴在桌面任意位置，支持文字编辑、颜色分类、字体调整；自带待办清单功能，可设置任务截止时间、已完成标记、置顶重要事项，支持开机常驻、透明化背景、一键隐藏所有便签，适合学生、上班族记录临时灵感、日程、琐事。
### 参与者（用户）
{
    "actor_name": "便签记录者",
    "actor_description": "便签记录者是指在需要快速记录临时灵感、课程内容、会议要点、日程安排或生活琐事的场景下，与桌面便签功能发生交互，并可执行新建便签、编辑文字内容、查看便签和删除便签等操作的用户角色。"
}
### 系统功能（feature）
{
    "feature_name": "新建独立便签",
    "feature_description": "支持用户创建多个相互独立的桌面便签，用于记录临时灵感、课程内容、会议要点、日程安排或生活琐事。",
}
# 当前整理出的场景（用户故事）
{
    "scenarios": [
        {
            "scenario_name": "快速创建临时灵感便签",
            "scenario_content": "As a 便签记录者, I want to 新建独立便签, So that 我可以快速记录临时灵感并将其保留在桌面上随时查看"
        },
        {
            "scenario_name": "创建课程内容便签",
            "scenario_content": "As a 便签记录者, I want to 新建独立便签, So that 我可以在学习过程中单独记录课程重点并避免与其他内容混淆"
        },
        {
            "scenario_name": "创建会议要点便签",
            "scenario_content": "As a 便签记录者, I want to 新建独立便签, So that 我可以在会议过程中快速记录关键事项并便于后续整理"
        },
        {
            "scenario_name": "创建日程安排便签",
            "scenario_content": "As a 便签记录者, I want to 新建独立便签, So that 我可以把重要日程放在桌面上提醒自己及时处理"
        },
        {
            "scenario_name": "创建生活琐事便签",
            "scenario_content": "As a 便签记录者, I want to 新建独立便签, So that 我可以把零散生活事项独立记录并减少遗忘"
        }
    ]
}
### 补充参与者的原因
需要补充“创建生活琐事便签”场景，作为便签记录者, 其可能会想要新建生活琐事便签, 把零散生活事项独立记录并减少遗忘。

## 示例输出
{
    "scenarios": [
        {
            "scenario_name": "创建生活琐事便签",
            "scenario_content": "As a 便签记录者, I want to 新建独立便签, So that 我可以把零散生活事项独立记录并减少遗忘"
        }
    ]
}
"""