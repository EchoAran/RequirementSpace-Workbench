# 第一步：生成需要补充的流程，先不管类型、用户、数据
flows_fill_prompt = """
# 角色
你是一个善于补充目标系统流程完整性的软件设计师。

# 任务
1. 分析用户用自然语言描述的项目需求、目标系统功能与当前确定的系统流程。
2. 基于项目需求与目标系统功能，根据补充功能的原因分析，对系统当前确定的流程进行补充。
3. 按照下方规定输出格式输出补充的功能。

# 用户需求
{{user_requirements}}

# 目标系统功能
{{features}}

# 当前确定的系统流程
{{flows}}

# 补充流程的类型与原因
{{perception_description}}

# 输出格式说明
{
    "flows": [
        {
            "flow_name": "<流程名称（例如‘请假审批流程’），若是>", 
            "flow_description": "<流程描述>", 
            "feature_ids": [<相关feature1的id>, <相关feature2的id>, ...（非空）], 
            "flow_steps":[
                {
                    "step_number": "<步骤编号：例如S-001>", 
                    "step_name": "<步骤名称>", 
                    "step_description": "<步骤描述>", 
                    "next_steps": ["<下一步走向1的编号>", "<下一步走向2的编号>", ...(可空，空表示流程结束；多个值表示该点为分岔点，存在多种可能的路径)]
                }, 
                {
                    "step_number": "<步骤编号：例如S-002>", 
                    "step_name": "<步骤名称>", 
                    "step_description": "<步骤描述>", 
                    "next_steps": ["<下一步走向1的编号>", "<下一步走向2的编号>", ...(可空，空表示流程结束；多个值表示该点为分岔点，存在多种可能的路径)]
                }, 
                ...
            ]  
        },  
        ... 
    ]
}

# 规则
1. 只输出一个 JSON 对象。
2. 不要输出任何解释、分析过程、Markdown、代码块标记或额外前后缀文字。
3. 输出 JSON 风格的标准格式化内容，而不是被压缩的一行内容。
4. step_number 只需要在当前 flow 内唯一，格式为 S-001、S-002。
5. next_steps 只能引用当前 flow 内存在的 step_number。
6. feature_ids 只能引用系统能力输入中存在的 feature_id。
7. 步骤之间必须是连续的，不能存在不连接或不被链接的结点。
8. 判断类型的步骤必须至少具有两个后继分支。

# 示例
## 示例输入
### 用户需求
轻量化桌面悬浮便签 + 待办整合软件，可新建多个独立便签贴在桌面任意位置，支持文字编辑、颜色分类、字体调整；自带待办清单功能，可设置任务截止时间、已完成标记、置顶重要事项，支持开机常驻、透明化背景、一键隐藏所有便签，适合学生、上班族记录临时灵感、日程、琐事。
### 目标系统功能
{
    "features": [
        {
            "feature_id": 3,
            "feature_name": "新建独立便签",
            "feature_description": "支持用户创建多个相互独立的桌面便签，用于记录临时灵感、课程内容、会议要点、日程安排或生活琐事。",
        },
        {
            "feature_id": 4,
            "feature_name": "编辑便签文字",
            "feature_description": "支持用户在便签中输入、修改和查看文字内容。",
        },
        {
            "feature_id": 5,
            "feature_name": "管理便签位置",
            "feature_description": "支持用户将多个便签放置在桌面任意位置，便于按照个人习惯组织桌面信息。",
        },
        {
            "feature_id": 7,
            "feature_name": "颜色分类",
            "feature_description": "支持用户为便签设置不同颜色，用于区分信息类别、优先级或使用场景。",
        },
        {
            "feature_id": 8,
            "feature_name": "字体调整",
            "feature_description": "支持用户调整便签文字的字体样式，使便签内容更符合个人阅读和整理习惯。",
        },
        {
            "feature_id": 10,
            "feature_name": "创建待办事项",
            "feature_description": "支持用户新增待办任务，用于记录需要完成的学习、工作或生活事项。",
        },
        {
            "feature_id": 11,
            "feature_name": "设置任务截止时间",
            "feature_description": "支持用户为待办事项设置截止时间，用于安排任务完成节点和日程计划。",
        },
        {
            "feature_id": 12,
            "feature_name": "标记任务完成状态",
            "feature_description": "支持用户将待办事项标记为已完成，用于跟踪任务处理进度。",
        },
        {
            "feature_id": 13,
            "feature_name": "置顶重要事项",
            "feature_description": "支持用户将重要待办事项置顶显示，便于优先关注和处理关键任务。",
        },
        {
            "feature_id": 15,
            "feature_name": "透明化背景",
            "feature_description": "支持用户设置便签背景透明效果，使便签与桌面环境更协调。",
        },
        {
            "feature_id": 16,
            "feature_name": "一键隐藏所有便签",
            "feature_description": "支持用户一次性隐藏所有桌面便签，用于临时清理桌面显示或减少视觉干扰。",
        },
        {
            "feature_id": 17,
            "feature_name": "恢复显示便签",
            "feature_description": "支持用户在隐藏便签后恢复显示所有便签，便于继续查看和处理记录内容。",
        },
        {
            "feature_id": 19,
            "feature_name": "开机常驻",
            "feature_description": "支持用户设置软件开机后自动运行并保持常驻，便于随时查看和记录信息。",
        },
        {
            "feature_id": 20,
            "feature_name": "默认便签样式配置",
            "feature_description": "支持用户配置默认字体、默认颜色和默认显示样式，减少重复设置操作。",
        }
    ]
}
### 当前确定的系统流程
{
    "flows": [
        {
            "flow_name": "便签创建与编辑流程",
            "flow_description": "便签记录者创建独立桌面便签，并输入、修改和保存便签文字内容。",
            "feature_ids": [
                3,
                4
            ],
            "flow_steps": [
                {
                    "step_id": 1,
                    "step_name": "发起新建便签",
                    "step_description": "便签记录者点击新建便签入口，要求系统创建一个新的独立便签。",
                    "next_steps": [
                        2
                    ]
                },
                {
                    "step_id": 2,
                    "step_name": "生成空白便签",
                    "step_description": "系统按照默认样式生成空白桌面便签，并分配唯一标识。",
                    "next_steps": [
                        3
                    ]
                },
                {
                    "step_id": 3,
                    "step_name": "输入或修改文字",
                    "step_description": "便签记录者在便签中输入临时灵感、日程、会议要点或生活琐事，也可修改已有内容。",
                    "next_steps": [
                        4
                    ]
                },
                {
                    "step_id": 4,
                    "step_name": "保存便签内容",
                    "step_description": "系统保存便签文字内容和更新时间，并保持便签在桌面显示。",
                    "next_steps": []
                }
            ]
        },
        {
            "flow_name": "便签整理与样式调整流程",
            "flow_description": "便签整理者对多个独立便签进行位置管理、颜色分类、字体调整和透明化外观设置。",
            "feature_ids": [
                5,
                7,
                8,
                15
            ],
            "flow_steps": [
                {
                    "step_id": 5,
                    "step_name": "选择目标便签",
                    "step_description": "便签整理者从桌面上的多个便签中选择需要整理或调整样式的便签。",
                    "next_steps": [
                        6,
                        7,
                        8,
                        9
                    ]
                },
                {
                    "step_id": 6,
                    "step_name": "拖动便签位置",
                    "step_description": "便签整理者将便签拖动到桌面任意目标位置。",
                    "next_steps": [
                        10
                    ]
                },
                {
                    "step_id": 7,
                    "step_name": "设置颜色分类",
                    "step_description": "便签整理者为便签选择颜色，用于区分信息类别、优先级或使用场景。",
                    "next_steps": [
                        10
                    ]
                },
                {
                    "step_id": 8,
                    "step_name": "调整字体样式",
                    "step_description": "便签整理者调整便签文字的字体、字号或相关显示样式。",
                    "next_steps": [
                        10
                    ]
                },
                {
                    "step_id": 9,
                    "step_name": "设置背景透明度",
                    "step_description": "便签整理者调整便签背景透明效果，使便签与桌面环境协调。",
                    "next_steps": [
                        10
                    ]
                },
                {
                    "step_id": 10,
                    "step_name": "保存便签布局与样式",
                    "step_description": "系统保存便签的位置、颜色、字体和透明度设置。",
                    "next_steps": []
                }
            ]
        },
        {
            "flow_name": "待办事项管理流程",
            "flow_description": "待办管理者创建待办事项，设置截止时间，置顶重要事项，并标记任务完成状态。",
            "feature_ids": [
                10,
                11,
                12,
                13
            ],
            "flow_steps": [
                {
                    "step_id": 11,
                    "step_name": "创建待办事项",
                    "step_description": "待办管理者输入待办任务标题或内容，提交新增任务。",
                    "next_steps": [
                        12
                    ]
                },
                {
                    "step_id": 12,
                    "step_name": "设置截止时间",
                    "step_description": "待办管理者为待办事项设置任务截止时间。",
                    "next_steps": [
                        13
                    ]
                },
                {
                    "step_id": 13,
                    "step_name": "判断是否置顶",
                    "step_description": "系统根据用户操作判断该待办事项是否需要置顶显示。",
                    "next_steps": [
                        14,
                        15
                    ]
                },
                {
                    "step_id": 14,
                    "step_name": "置顶重要事项",
                    "step_description": "待办管理者将重要待办事项设置为置顶显示。",
                    "next_steps": [
                        15
                    ]
                },
                {
                    "step_id": 15,
                    "step_name": "保存待办事项",
                    "step_description": "系统保存待办事项内容、截止时间、置顶状态和初始完成状态。",
                    "next_steps": [
                        16
                    ]
                },
                {
                    "step_id": 16,
                    "step_name": "标记完成状态",
                    "step_description": "待办管理者在任务完成后将待办事项标记为已完成。",
                    "next_steps": [
                        17
                    ]
                },
                {
                    "step_id": 17,
                    "step_name": "更新任务状态",
                    "step_description": "系统更新待办事项完成状态，并刷新待办清单展示。",
                    "next_steps": []
                }
            ]
        },
        {
            "flow_name": "桌面显示控制流程",
            "flow_description": "桌面显示控制者对所有桌面便签执行一键隐藏、恢复显示和常驻显示控制。",
            "feature_ids": [
                16,
                17
            ],
            "flow_steps": [
                {
                    "step_id": 18,
                    "step_name": "选择显示控制操作",
                    "step_description": "桌面显示控制者选择一键隐藏所有便签或恢复显示便签。",
                    "next_steps": [
                        19
                    ]
                },
                {
                    "step_id": 19,
                    "step_name": "判断控制类型",
                    "step_description": "系统判断用户选择的是隐藏所有便签还是恢复显示便签。",
                    "next_steps": [
                        3,
                        4
                    ]
                },
                {
                    "step_id": 20,
                    "step_name": "隐藏所有便签",
                    "step_description": "系统将所有桌面便签设置为隐藏状态，并更新全局显示控制状态。",
                    "next_steps": []
                },
                {
                    "step_id": 21,
                    "step_name": "恢复显示便签",
                    "step_description": "系统将已隐藏的便签恢复显示，并更新全局显示控制状态。",
                    "next_steps": []
                }
            ]
        },
        {
            "flow_name": "系统偏好配置流程",
            "flow_description": "系统偏好设置者配置开机常驻、默认便签颜色、默认字体和默认显示样式，供后续新建便签和启动行为使用。",
            "feature_ids": [
                7,
                8,
                15,
                18,
                19
            ],
            "flow_steps": [
                {
                    "step_id": 22,
                    "step_name": "进入偏好设置",
                    "step_description": "系统偏好设置者打开软件设置入口，进入偏好配置界面。",
                    "next_steps": [
                        23
                    ]
                },
                {
                    "step_id": 23,
                    "step_name": "配置开机常驻",
                    "step_description": "系统偏好设置者选择是否启用开机自动运行并保持常驻。",
                    "next_steps": [
                        24
                    ]
                },
                {
                    "step_id": 24,
                    "step_name": "配置默认便签样式",
                    "step_description": "系统偏好设置者设置默认颜色、默认字体、默认字号和默认透明度。",
                    "next_steps": [
                        25
                    ]
                },
                {
                    "step_id": 25,
                    "step_name": "保存偏好设置",
                    "step_description": "系统保存偏好设置，并将配置用于后续软件启动和新建便签。",
                    "next_steps": []
                }
            ]
        }
    ]
}
### 补充功能的原因
需要补充“软件启动与常驻运行流程”。原因是当前“系统偏好配置流程”只覆盖了用户配置开机常驻偏好的过程，但未覆盖软件在系统启动或用户启动后，根据已保存偏好自动运行、加载便签与待办数据、恢复桌面显示状态并保持后台常驻的实际运行流程；而“开机常驻”不仅是设置项，也是目标系统的重要运行能力。补充方式是新增一个流程，关联 feature_id 18，可包括读取开机常驻配置、启动软件进程、加载已保存便签和待办事项、恢复便签位置与显示状态、进入常驻运行状态等步骤。

## 示例输出
{
    "flows": [
        {
            "flow_name": "软件启动与常驻运行流程",
            "flow_description": "系统在开机自动启动或用户手动启动软件后，读取已保存偏好配置，加载历史便签与待办数据，恢复便签样式、位置和显示状态，并进入后台常驻运行状态，便于用户随时查看和记录信息。",
            "feature_ids": [
                19,
                20
            ],
            "flow_steps": [
                {
                    "step_number": "S-001",
                    "step_name": "触发软件启动",
                    "step_description": "系统因开机自动运行配置生效或用户手动打开软件而触发启动流程。",
                    "next_steps": [
                        "S-002"
                    ]
                },
                {
                    "step_number": "S-002",
                    "step_name": "读取启动与默认配置",
                    "step_description": "系统读取已保存的开机常驻配置、默认便签颜色、默认字体、默认字号、默认透明度和默认显示样式。",
                    "next_steps": [
                        "S-003"
                    ]
                },
                {
                    "step_number": "S-003",
                    "step_name": "判断是否允许常驻运行",
                    "step_description": "系统根据已保存的开机常驻配置和当前启动方式，判断软件是否需要进入常驻运行状态。",
                    "next_steps": [
                        "S-004",
                        "S-008"
                    ]
                },
                {
                    "step_number": "S-004",
                    "step_name": "启动软件主进程",
                    "step_description": "系统启动桌面便签软件主进程，初始化便签管理、待办清单管理和桌面显示控制模块。",
                    "next_steps": [
                        "S-005"
                    ]
                },
                {
                    "step_number": "S-005",
                    "step_name": "加载已保存数据",
                    "step_description": "系统加载已保存的便签内容、便签位置、颜色分类、字体样式、透明度设置、待办事项、截止时间、完成状态和置顶状态。",
                    "next_steps": [
                        "S-006"
                    ]
                },
                {
                    "step_number": "S-006",
                    "step_name": "恢复桌面显示状态",
                    "step_description": "系统根据上次保存的显示状态，恢复便签在桌面上的位置、样式和可见状态；若上次为隐藏状态，则保持隐藏并保留恢复显示能力。",
                    "next_steps": [
                        "S-007"
                    ]
                },
                {
                    "step_number": "S-007",
                    "step_name": "进入常驻运行状态",
                    "step_description": "系统保持后台常驻运行，使用户可随时新建便签、编辑内容、查看待办事项、隐藏或恢复桌面便签。",
                    "next_steps": []
                },
                {
                    "step_number": "S-008",
                    "step_name": "按普通启动方式运行",
                    "step_description": "系统不启用常驻运行能力，仅按照用户本次手动启动行为打开软件，并在用户退出后结束运行。",
                    "next_steps": [
                        "S-004"
                    ]
                }
            ]
        }
    ]
}
"""









# 第二步：生成或标记“补充的流程”相关的类型、用户、数据
business_objects_actors_label_prompt = """
# 角色
你是一个善于为某条系统流程补充参与与类型完整性的软件设计师。

# 任务
1. 分析当前系统流程各步骤的数据流转。
2. 基于分析出来的步骤间数据流转关系，从已经建模的业务数据模型中选择合适的数据或者新建业务数据模型，对流程步骤的输入输出进行补充。
3. 分析每个流程步骤的操作类型，若是用户操作则从参与者列表中选择合适的参与者对齐进行标记。
4. 按照下方规定输出格式输出补充了参与者、操作类型、参数的流程。

# 参与者（用户）
{{actors}}

# 已经建模的业务数据模型
{{business_objects}}

# 流程
{{flow}}

# 输出格式说明
{
    "business_objects": [
        {
            "business_object_id": <已有业务对象使用输入中的业务对象id；新增业务对象可使用临时引用，例如"B-001">,
            "business_object_name": "<业务对象名字>", 
            "business_object_description": "<业务对象描述>", 
            "business_object_attributes": [
                {
                    "business_object_attribute_name": "<业务对象属性名字>", 
                    "business_object_attribute_description": "<业务对象属性描述>",  
                    "business_object_attribute_type": "<业务对象属性类型，例如string、bool等>", 
                    "business_object_attribute_example": "<属性值的示例>" 
                }, 
                {
                    "business_object_attribute_name": "<业务对象属性名字>", 
                    "business_object_attribute_description": "<业务对象属性描述>",  
                    "business_object_attribute_type": "<业务对象属性类型，例如string、bool等>", 
                    "business_object_attribute_example": "<属性值的示例>" 
                }, 
                ... 
            ]
        }, 
        ... 
    ], 
    "flows": [
        {
            "flow_name": "<流程名称（例如‘请假审批流程’），原样输出>", 
            "flow_description": "<流程描述，原样输出>", 
            "feature_ids": [<相关feature1的id>, <相关feature2的id>, ...（非空），原样输出], 
            "flow_steps":[
                {
                    "step_number": "<步骤编号：例如S-001，原样输出>", 
                    "step_name": "<步骤名称，原样输出>", 
                    "step_description": "<步骤描述，原样输出>", 
                    "actor_ids": [<相关参与者1的id>, <相关参与者2的id>, ...(可空)], 
                    "step_type": "<步骤类型：actorAction|systemAction|judgment>（例如用户输入即为actorAction类型）", 
                    "input_business_object_ids": [<输入的业务对象1的id>, <输入的业务对象2的id>, ...(可空)], 
                    "output_business_object_ids": [<输出的业务对象1的id>, <输出的业务对象2的id>, ...(可空)], 
                    "next_steps": ["<下一步走向1的编号>", "<下一步走向2的编号>", ...(可空，空表示流程结束；多个值表示该点为分岔点，存在多种可能的路径)，原样输出]
                }, 
                {
                    "step_number": "<步骤编号：例如S-002，原样输出>", 
                    "step_name": "<步骤名称，原样输出>", 
                    "step_description": "<步骤描述，原样输出>", 
                    "actor_ids": [<相关参与者1的id>, <相关参与者2的id>, ...(可空)], 
                    "step_type": "<步骤类型：actorAction|systemAction|judgment>（例如用户输入即为actorAction类型）", 
                    "input_business_object_ids": [<输入的业务对象1的id>, <输入的业务对象2的id>, ...(可空)], 
                    "output_business_object_ids": [<输出的业务对象1的id>, <输出的业务对象2的id>, ...(可空)], 
                    "next_steps": ["<下一步走向1的编号>", "<下一步走向2的编号>", ...(可空，空表示流程结束；多个值表示该点为分岔点，存在多种可能的路径)，原样输出]
                }, 
                ...
            ]  
        },  
        ... 
    ]
}

# 规则
1. 只输出一个 JSON 对象。
2. 不要输出任何解释、分析过程、Markdown、代码块标记或额外前后缀文字。
3. 输出 JSON 风格的标准格式化内容，而不是被压缩的一行内容。
4. step_type 只能是 actorAction、systemAction、judgment。
5. 若某些步骤需要的输入输出是尚未建模的数据模型，那你需要把这部分数据建模并输出（注意是仅输出新增的）。若不需要，这部分直接输出"business_objects": []即可。
6. 已有业务对象必须使用输入中的 business_object_id；新增业务对象不要假设数据库真实 id，可使用临时引用（例如"B-001"、"B-002"）。流程步骤中的 input_business_object_ids / output_business_object_ids 引用同一个临时值即可，系统会在入库时转换为真实数据库 id。
7. business_object_attribute_example 必须是字符串。即使 business_object_attribute_type 是 integer、bool、array[string]、object等，也必须把示例值写成字符串。例如："business_object_attribute_type": "integer","business_object_attribute_example": "14"。
8. business_object_attribute_example 中若本身带有"符号则需要转义，例如"business_object_attribute_example": "[\"M-001\", \"M-003\", \"M-009\"]"，错误写法为"business_object_attribute_example": "["M-001", "M-003", "M-009"]"。

# 示例
## 示例输入
### 参与者（用户）
{
    "actors": [
        {
            "actor_id": 1,
            "actor_name": "便签记录者",
            "actor_description": "便签记录者是指在需要快速记录临时灵感、课程内容、会议要点、日程安排或生活琐事的场景下，与桌面便签功能发生交互，并可执行新建便签、编辑文字内容、查看便签和删除便签等操作的用户角色。"
        },
        {
            "actor_id": 2,
            "actor_name": "便签整理者",
            "actor_description": "便签整理者是指在需要对桌面上的多条便签进行分类、区分和排布的场景下，与便签管理功能发生交互，并可执行移动便签位置、设置颜色分类、调整字体样式、调整便签外观和管理多个独立便签等操作的用户角色。"
        },
        {
            "actor_id": 3,
            "actor_name": "待办管理者",
            "actor_description": "待办管理者是指在需要规划、跟踪和处理个人任务的场景下，与待办清单功能发生交互，并可执行创建待办事项、设置任务截止时间、标记任务已完成、查看任务状态和置顶重要事项等操作的用户角色。"
        },
        {
             "actor_id": 4,
            "actor_name": "桌面显示控制者",
            "actor_description": "桌面显示控制者是指在需要控制便签在桌面上的显示状态、降低桌面干扰或保持重要信息可见的场景下，与桌面悬浮显示功能发生交互，并可执行设置透明化背景、一键隐藏所有便签、恢复显示便签和控制便签常驻桌面等操作的用户角色。"
        },
        {
            "actor_id": 5,
            "actor_name": "系统偏好设置者",
            "actor_description": "系统偏好设置者是指在需要让软件符合个人长期使用习惯的场景下，与软件设置功能发生交互，并可执行设置开机常驻、配置默认便签样式、调整默认字体、设置默认颜色分类和配置显示偏好等操作的用户角色。"
        }
    ]
} 
### 业务数据模型
{
    "business_objects": [
        {
            "business_object_id": 1,
            "business_object_name": "桌面便签",
            "business_object_description": "用户创建并悬浮显示在桌面上的独立便签，用于记录文字信息并承载位置、颜色、字体和显示状态等数据。",
            "business_object_attributes": [
                {
                    "business_object_attribute_name": "note_id",
                    "business_object_attribute_description": "便签唯一标识",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "N-001"
                },
                {
                    "business_object_attribute_name": "content",
                    "business_object_attribute_description": "便签文字内容",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "下午三点提交课程作业"
                },
                {
                    "business_object_attribute_name": "position_x",
                    "business_object_attribute_description": "便签在桌面上的横向坐标",
                    "business_object_attribute_type": "integer",
                    "business_object_attribute_example": "320"
                },
                {
                    "business_object_attribute_name": "position_y",
                    "business_object_attribute_description": "便签在桌面上的纵向坐标",
                    "business_object_attribute_type": "integer",
                    "business_object_attribute_example": "180"
                },
                {
                    "business_object_attribute_name": "color_category",
                    "business_object_attribute_description": "便签颜色分类",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "黄色"
                },
                {
                    "business_object_attribute_name": "font_family",
                    "business_object_attribute_description": "便签字体名称",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "Microsoft YaHei"
                },
                {
                    "business_object_attribute_name": "font_size",
                    "business_object_attribute_description": "便签字号",
                    "business_object_attribute_type": "integer",
                    "business_object_attribute_example": "14"
                },
                {
                    "business_object_attribute_name": "opacity",
                    "business_object_attribute_description": "便签背景透明度",
                    "business_object_attribute_type": "decimal",
                    "business_object_attribute_example": "0.75"
                },
                {
                    "business_object_attribute_name": "is_hidden",
                    "business_object_attribute_description": "便签是否处于隐藏状态",
                    "business_object_attribute_type": "bool",
                    "business_object_attribute_example": "false"
                }
            ]
        },
        {
            "business_object_id": 2,
            "business_object_name": "待办事项",
            "business_object_description": "用户创建的个人任务条目，用于记录任务内容、截止时间、完成状态和重要程度。",
            "business_object_attributes": [
                {
                    "business_object_attribute_name": "todo_id",
                    "business_object_attribute_description": "待办事项唯一标识",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "T-001"
                },
                {
                    "business_object_attribute_name": "title",
                    "business_object_attribute_description": "待办事项标题",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "整理会议纪要"
                },
                {
                    "business_object_attribute_name": "due_time",
                    "business_object_attribute_description": "任务截止时间",
                    "business_object_attribute_type": "datetime",
                    "business_object_attribute_example": "2026-05-21 18:00:00"
                },
                {
                    "business_object_attribute_name": "is_completed",
                    "business_object_attribute_description": "任务是否完成",
                    "business_object_attribute_type": "bool",
                    "business_object_attribute_example": "false"
                },
                {
                    "business_object_attribute_name": "is_pinned",
                    "business_object_attribute_description": "任务是否置顶",
                    "business_object_attribute_type": "bool",
                    "business_object_attribute_example": "true"
                }
            ]
        },
        {
            "business_object_id": 3,
            "business_object_name": "显示控制状态",
            "business_object_description": "桌面便签整体显示控制数据，用于记录全局隐藏、恢复显示和常驻桌面等状态。",
            "business_object_attributes": [
                {
                    "business_object_attribute_name": "display_state_id",
                    "business_object_attribute_description": "显示控制状态唯一标识",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "D-001"
                },
                {
                    "business_object_attribute_name": "all_notes_hidden",
                    "business_object_attribute_description": "是否已隐藏所有便签",
                    "business_object_attribute_type": "bool",
                    "business_object_attribute_example": "true"
                },
                {
                    "business_object_attribute_name": "resident_enabled",
                    "business_object_attribute_description": "是否启用桌面常驻",
                    "business_object_attribute_type": "bool",
                    "business_object_attribute_example": "true"
                }
            ]
        },
        {
            "business_object_id": 4,
            "business_object_name": "系统偏好设置",
            "business_object_description": "用户长期使用偏好配置，包括开机常驻、默认颜色、默认字体和默认显示样式。",
            "business_object_attributes": [
                {
                    "business_object_attribute_name": "preference_id",
                    "business_object_attribute_description": "偏好设置唯一标识",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "P-001"
                },
                {
                    "business_object_attribute_name": "auto_start_enabled",
                    "business_object_attribute_description": "是否启用开机自动运行",
                    "business_object_attribute_type": "bool",
                    "business_object_attribute_example": "true"
                },
                {
                    "business_object_attribute_name": "default_color",
                    "business_object_attribute_description": "新建便签默认颜色",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "浅黄色"
                },
                {
                    "business_object_attribute_name": "default_font_family",
                    "business_object_attribute_description": "新建便签默认字体",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "Microsoft YaHei"
                },
                {
                    "business_object_attribute_name": "default_font_size",
                    "business_object_attribute_description": "新建便签默认字号",
                    "business_object_attribute_type": "integer",
                    "business_object_attribute_example": "14"
                },
                {
                    "business_object_attribute_name": "default_opacity",
                    "business_object_attribute_description": "新建便签默认透明度",
                    "business_object_attribute_type": "decimal",
                    "business_object_attribute_example": "0.85"
                }
            ]
        }
    ]
}
### 流程
{
    "flows": [
        {
            "flow_name": "软件启动与常驻运行流程",
            "flow_description": "系统在开机自动启动或用户手动启动软件后，读取已保存偏好配置，加载历史便签与待办数据，恢复便签样式、位置和显示状态，并进入后台常驻运行状态，便于用户随时查看和记录信息。",
            "feature_ids": [
                19,
                20
            ],
            "flow_steps": [
                {
                    "step_number": "S-001",
                    "step_name": "触发软件启动",
                    "step_description": "系统因开机自动运行配置生效或用户手动打开软件而触发启动流程。",
                    "next_steps": [
                        "S-002"
                    ]
                },
                {
                    "step_number": "S-002",
                    "step_name": "读取启动与默认配置",
                    "step_description": "系统读取已保存的开机常驻配置、默认便签颜色、默认字体、默认字号、默认透明度和默认显示样式。",
                    "next_steps": [
                        "S-003"
                    ]
                },
                {
                    "step_number": "S-003",
                    "step_name": "判断是否允许常驻运行",
                    "step_description": "系统根据已保存的开机常驻配置和当前启动方式，判断软件是否需要进入常驻运行状态。",
                    "next_steps": [
                        "S-004",
                        "S-008"
                    ]
                },
                {
                    "step_number": "S-004",
                    "step_name": "启动软件主进程",
                    "step_description": "系统启动桌面便签软件主进程，初始化便签管理、待办清单管理和桌面显示控制模块。",
                    "next_steps": [
                        "S-005"
                    ]
                },
                {
                    "step_number": "S-005",
                    "step_name": "加载已保存数据",
                    "step_description": "系统加载已保存的便签内容、便签位置、颜色分类、字体样式、透明度设置、待办事项、截止时间、完成状态和置顶状态。",
                    "next_steps": [
                        "S-006"
                    ]
                },
                {
                    "step_number": "S-006",
                    "step_name": "恢复桌面显示状态",
                    "step_description": "系统根据上次保存的显示状态，恢复便签在桌面上的位置、样式和可见状态；若上次为隐藏状态，则保持隐藏并保留恢复显示能力。",
                    "next_steps": [
                        "S-007"
                    ]
                },
                {
                    "step_number": "S-007",
                    "step_name": "进入常驻运行状态",
                    "step_description": "系统保持后台常驻运行，使用户可随时新建便签、编辑内容、查看待办事项、隐藏或恢复桌面便签。",
                    "next_steps": []
                },
                {
                    "step_number": "S-008",
                    "step_name": "按普通启动方式运行",
                    "step_description": "系统不启用常驻运行能力，仅按照用户本次手动启动行为打开软件，并在用户退出后结束运行。",
                    "next_steps": [
                        "S-004"
                    ]
                }
            ]
        }
    ]
}

## 示例输出
{
    "business_objects": [
        {
            "business_object_id": 5,
            "business_object_name": "软件运行状态",
            "business_object_description": "桌面便签软件在启动、初始化、常驻或普通运行过程中的运行态数据，用于记录启动方式、主进程状态、模块初始化状态和是否处于常驻运行。",
            "business_object_attributes": [
                {
                    "business_object_attribute_name": "runtime_state_id",
                    "business_object_attribute_description": "软件运行状态唯一标识",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "R-001"
                },
                {
                    "business_object_attribute_name": "startup_type",
                    "business_object_attribute_description": "软件启动方式，例如开机自动启动或用户手动启动",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "auto_start"
                },
                {
                    "business_object_attribute_name": "main_process_status",
                    "business_object_attribute_description": "软件主进程运行状态",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "running"
                },
                {
                    "business_object_attribute_name": "note_module_initialized",
                    "business_object_attribute_description": "便签管理模块是否已完成初始化",
                    "business_object_attribute_type": "bool",
                    "business_object_attribute_example": "true"
                },
                {
                    "business_object_attribute_name": "todo_module_initialized",
                    "business_object_attribute_description": "待办清单管理模块是否已完成初始化",
                    "business_object_attribute_type": "bool",
                    "business_object_attribute_example": "true"
                },
                {
                    "business_object_attribute_name": "display_module_initialized",
                    "business_object_attribute_description": "桌面显示控制模块是否已完成初始化",
                    "business_object_attribute_type": "bool",
                    "business_object_attribute_example": "true"
                },
                {
                    "business_object_attribute_name": "resident_running",
                    "business_object_attribute_description": "软件当前是否处于后台常驻运行状态",
                    "business_object_attribute_type": "bool",
                    "business_object_attribute_example": "true"
                }
            ]
        }
    ],
    "flows": [
        {
            "flow_name": "软件启动与常驻运行流程",
            "flow_description": "系统在开机自动启动或用户手动启动软件后，读取已保存偏好配置，加载历史便签与待办数据，恢复便签样式、位置和显示状态，并进入后台常驻运行状态，便于用户随时查看和记录信息。",
            "feature_ids": [
                19,
                20
            ],
            "flow_steps": [
                {
                    "step_number": "S-001",
                    "step_name": "触发软件启动",
                    "step_description": "系统因开机自动运行配置生效或用户手动打开软件而触发启动流程。",
                    "actor_ids": [
                        1,
                        2,
                        3,
                        4,
                        5
                    ],
                    "step_type": "actorAction",
                    "input_business_object_ids": [
                        4
                    ],
                    "output_business_object_ids": [
                        5
                    ],
                    "next_steps": [
                        "S-002"
                    ]
                },
                {
                    "step_number": "S-002",
                    "step_name": "读取启动与默认配置",
                    "step_description": "系统读取已保存的开机常驻配置、默认便签颜色、默认字体、默认字号、默认透明度和默认显示样式。",
                    "actor_ids": [],
                    "step_type": "systemAction",
                    "input_business_object_ids": [
                        4
                    ],
                    "output_business_object_ids": [
                        4
                    ],
                    "next_steps": [
                        "S-003"
                    ]
                },
                {
                    "step_number": "S-003",
                    "step_name": "判断是否允许常驻运行",
                    "step_description": "系统根据已保存的开机常驻配置和当前启动方式，判断软件是否需要进入常驻运行状态。",
                    "actor_ids": [],
                    "step_type": "judgment",
                    "input_business_object_ids": [
                        4,
                        5
                    ],
                    "output_business_object_ids": [
                        5
                    ],
                    "next_steps": [
                        "S-004",
                        "S-008"
                    ]
                },
                {
                    "step_number": "S-004",
                    "step_name": "启动软件主进程",
                    "step_description": "系统启动桌面便签软件主进程，初始化便签管理、待办清单管理和桌面显示控制模块。",
                    "actor_ids": [],
                    "step_type": "systemAction",
                    "input_business_object_ids": [
                        5
                    ],
                    "output_business_object_ids": [
                        5
                    ],
                    "next_steps": [
                        "S-005"
                    ]
                },
                {
                    "step_number": "S-005",
                    "step_name": "加载已保存数据",
                    "step_description": "系统加载已保存的便签内容、便签位置、颜色分类、字体样式、透明度设置、待办事项、截止时间、完成状态和置顶状态。",
                    "actor_ids": [],
                    "step_type": "systemAction",
                    "input_business_object_ids": [
                        1,
                        2,
                        4,
                        5
                    ],
                    "output_business_object_ids": [
                        1,
                        2
                    ],
                    "next_steps": [
                        "S-006"
                    ]
                },
                {
                    "step_number": "S-006",
                    "step_name": "恢复桌面显示状态",
                    "step_description": "系统根据上次保存的显示状态，恢复便签在桌面上的位置、样式和可见状态；若上次为隐藏状态，则保持隐藏并保留恢复显示能力。",
                    "actor_ids": [],
                    "step_type": "systemAction",
                    "input_business_object_ids": [
                        1,
                        3,
                        4,
                        5
                    ],
                    "output_business_object_ids": [
                        1,
                        3
                    ],
                    "next_steps": [
                        "S-007"
                    ]
                },
                {
                    "step_number": "S-007",
                    "step_name": "进入常驻运行状态",
                    "step_description": "系统保持后台常驻运行，使用户可随时新建便签、编辑内容、查看待办事项、隐藏或恢复桌面便签。",
                    "actor_ids": [],
                    "step_type": "systemAction",
                    "input_business_object_ids": [
                        1,
                        2,
                        3,
                        5
                    ],
                    "output_business_object_ids": [
                        5
                    ],
                    "next_steps": []
                },
                {
                    "step_number": "S-008",
                    "step_name": "按普通启动方式运行",
                    "step_description": "系统不启用常驻运行能力，仅按照用户本次手动启动行为打开软件，并在用户退出后结束运行。",
                    "actor_ids": [],
                    "step_type": "systemAction",
                    "input_business_object_ids": [
                        4,
                        5
                    ],
                    "output_business_object_ids": [
                        5
                    ],
                    "next_steps": [
                        "S-004"
                    ]
                }
            ]
        }
    ]
}
"""
