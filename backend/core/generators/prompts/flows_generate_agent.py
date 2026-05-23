# 第一步 生成系统流程
flows_generate_prompt = """
# 角色
你是一个善于设计项目流程的软件设计师。

# 任务
1. 分析用户用自然语言描述的项目需求、目标系统参与者（用户）、系统功能（features）。
2. 基于系统功能（features）提取出系统的主要流程。
3. 基于提取出系统的主要流程，进一步细化每个流程的具体步骤。
4. 按照下方规定输出格式输出系统的主要流程以及每个流程的具体步骤。

# 用户需求
{{user_requirements}}

# 参与者（用户）
{{actors}}

# 系统能力（features）
{{features}}

# 输出格式说明
{
    "flows": [
        {
            "flow_name": "<流程名称（例如‘请假审批流程’）>", 
            "flow_description": "<流程描述>", 
            "feature_ids": [<相关feature1的id>, <相关feature2的id>, ...（非空）], 
            "flow_steps":[
                {
                    "step_number": "<步骤编号：例如S-001>", 
                    "step_name": "<步骤名称>", 
                    "step_description": "<步骤描述>", 
                    "actor_ids": [<相关参与者1的id>, <相关参与者2的id>, ...(可空)], 
                    "step_type": "<步骤类型：actorAction|systemAction|judgment>（例如用户输入即为actorAction类型）", 
                    "next_steps": ["<下一步走向1的编号>", "<下一步走向2的编号>", ...(可空，空表示流程结束；多个值表示该点为分岔点，存在多种可能的路径)]
                }, 
                {
                    "step_number": "<步骤编号：例如S-002>", 
                    "step_name": "<步骤名称>", 
                    "step_description": "<步骤描述>", 
                    "actor_ids": [<相关参与者1的id>, <相关参与者2的id>, ...(可空)], 
                    "step_type": "<步骤类型：actorAction|systemAction|judgment>（例如用户输入即为actorAction类型）", 
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
7. step_type 只能是 actorAction、systemAction、judgment。

# 示例
## 示例输入
### 用户需求
轻量化桌面悬浮便签 + 待办整合软件，可新建多个独立便签贴在桌面任意位置，支持文字编辑、颜色分类、字体调整；自带待办清单功能，可设置任务截止时间、已完成标记、置顶重要事项，支持开机常驻、透明化背景、一键隐藏所有便签，适合学生、上班族记录临时灵感、日程、琐事。
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
### 系统能力（features）
{
    "features": [
        {
            "feature_id": 3,
            "feature_name": "新建独立便签",
            "feature_description": "支持用户创建多个相互独立的桌面便签，用于记录临时灵感、课程内容、会议要点、日程安排或生活琐事。",
            "actor_ids": [
                1
            ]
        },
        {
            "feature_id": 4,
            "feature_name": "编辑便签文字",
            "feature_description": "支持用户在便签中输入、修改和查看文字内容。",
            "actor_ids": [
                1
            ]
        },
        {
            "feature_id": 5,
            "feature_name": "管理便签位置",
            "feature_description": "支持用户将多个便签放置在桌面任意位置，便于按照个人习惯组织桌面信息。",
            "actor_ids": [
                2
            ]
        },
        {
            "feature_id": 7,
            "feature_name": "颜色分类",
            "feature_description": "支持用户为便签设置不同颜色，用于区分信息类别、优先级或使用场景。",
            "actor_ids": [
                2,
                5
            ]
        },
        {
            "feature_id": 8,
            "feature_name": "字体调整",
            "feature_description": "支持用户调整便签文字的字体样式，使便签内容更符合个人阅读和整理习惯。",
            "actor_ids": [
                2,
                5
            ]
        },
        {
            "feature_id": 10,
            "feature_name": "创建待办事项",
            "feature_description": "支持用户新增待办任务，用于记录需要完成的学习、工作或生活事项。",
            "actor_ids": [
                3
            ]
        },
        {
            "feature_id": 11,
            "feature_name": "设置任务截止时间",
            "feature_description": "支持用户为待办事项设置截止时间，用于安排任务完成节点和日程计划。",
            "actor_ids": [
                3
            ]
        },
        {
            "feature_id": 12,
            "feature_name": "标记任务完成状态",
            "feature_description": "支持用户将待办事项标记为已完成，用于跟踪任务处理进度。",
            "actor_ids": [
                3
            ]
        },
        {
            "feature_id": 13,
            "feature_name": "置顶重要事项",
            "feature_description": "支持用户将重要待办事项置顶显示，便于优先关注和处理关键任务。",
            "actor_ids": [
                3
            ]
        },
        {
            "feature_id": 15,
            "feature_name": "透明化背景",
            "feature_description": "支持用户设置便签背景透明效果，使便签与桌面环境更协调。",
            "actor_ids": [
                4,
                5
            ]
        },
        {
            "feature_id": 16,
            "feature_name": "一键隐藏所有便签",
            "feature_description": "支持用户一次性隐藏所有桌面便签，用于临时清理桌面显示或减少视觉干扰。",
            "actor_ids": [
                4
            ]
        },
        {
            "feature_id": 17,
            "feature_name": "恢复显示便签",
            "feature_description": "支持用户在隐藏便签后恢复显示所有便签，便于继续查看和处理记录内容。",
            "actor_ids": [
                4
            ]
        },
        {
            "feature_id": 19,
            "feature_name": "开机常驻",
            "feature_description": "支持用户设置软件开机后自动运行并保持常驻，便于随时查看和记录信息。",
            "actor_ids": [
                5
            ]
        },
        {
            "feature_id": 20,
            "feature_name": "默认便签样式配置",
            "feature_description": "支持用户配置默认字体、默认颜色和默认显示样式，减少重复设置操作。",
            "actor_ids": [
                5
            ]
        }
    ]
}

## 示例输出
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
                    "step_number": "S-001",
                    "step_name": "发起新建便签",
                    "step_description": "便签记录者点击新建便签入口，要求系统创建一个新的独立便签。",
                    "actor_ids": [
                        1
                    ],
                    "step_type": "actorAction",
                    "next_steps": [
                        "S-002"
                    ]
                },
                {
                    "step_number": "S-002",
                    "step_name": "生成空白便签",
                    "step_description": "系统按照默认样式生成空白桌面便签，并分配唯一标识。",
                    "actor_ids": [],
                    "step_type": "systemAction",
                    "next_steps": [
                        "S-003"
                    ]
                },
                {
                    "step_number": "S-003",
                    "step_name": "输入或修改文字",
                    "step_description": "便签记录者在便签中输入临时灵感、日程、会议要点或生活琐事，也可修改已有内容。",
                    "actor_ids": [
                        1
                    ],
                    "step_type": "actorAction",
                    "next_steps": [
                        "S-004"
                    ]
                },
                {
                    "step_number": "S-004",
                    "step_name": "保存便签内容",
                    "step_description": "系统保存便签文字内容和更新时间，并保持便签在桌面显示。",
                    "actor_ids": [],
                    "step_type": "systemAction",
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
                    "step_number": "S-001",
                    "step_name": "选择目标便签",
                    "step_description": "便签整理者从桌面上的多个便签中选择需要整理或调整样式的便签。",
                    "actor_ids": [
                        2
                    ],
                    "step_type": "actorAction",
                    "next_steps": [
                        "S-002",
                        "S-003",
                        "S-004",
                        "S-005"
                    ]
                },
                {
                    "step_number": "S-002",
                    "step_name": "拖动便签位置",
                    "step_description": "便签整理者将便签拖动到桌面任意目标位置。",
                    "actor_ids": [
                        2
                    ],
                    "step_type": "actorAction",
                    "next_steps": [
                        "S-006"
                    ]
                },
                {
                    "step_number": "S-003",
                    "step_name": "设置颜色分类",
                    "step_description": "便签整理者为便签选择颜色，用于区分信息类别、优先级或使用场景。",
                    "actor_ids": [
                        2
                    ],
                    "step_type": "actorAction",
                    "next_steps": [
                        "S-006"
                    ]
                },
                {
                    "step_number": "S-004",
                    "step_name": "调整字体样式",
                    "step_description": "便签整理者调整便签文字的字体、字号或相关显示样式。",
                    "actor_ids": [
                        2
                    ],
                    "step_type": "actorAction",
                    "next_steps": [
                        "S-006"
                    ]
                },
                {
                    "step_number": "S-005",
                    "step_name": "设置背景透明度",
                    "step_description": "便签整理者调整便签背景透明效果，使便签与桌面环境协调。",
                    "actor_ids": [
                        4
                    ],
                    "step_type": "actorAction",
                    "next_steps": [
                        "S-006"
                    ]
                },
                {
                    "step_number": "S-006",
                    "step_name": "保存便签布局与样式",
                    "step_description": "系统保存便签的位置、颜色、字体和透明度设置。",
                    "actor_ids": [],
                    "step_type": "systemAction",
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
                    "step_number": "S-001",
                    "step_name": "创建待办事项",
                    "step_description": "待办管理者输入待办任务标题或内容，提交新增任务。",
                    "actor_ids": [
                        3
                    ],
                    "step_type": "actorAction",
                    "next_steps": [
                        "S-002"
                    ]
                },
                {
                    "step_number": "S-002",
                    "step_name": "设置截止时间",
                    "step_description": "待办管理者为待办事项设置任务截止时间。",
                    "actor_ids": [
                        3
                    ],
                    "step_type": "actorAction",
                    "next_steps": [
                        "S-003"
                    ]
                },
                {
                    "step_number": "S-003",
                    "step_name": "判断是否置顶",
                    "step_description": "系统根据用户操作判断该待办事项是否需要置顶显示。",
                    "actor_ids": [],
                    "step_type": "judgment",
                    "next_steps": [
                        "S-004",
                        "S-005"
                    ]
                },
                {
                    "step_number": "S-004",
                    "step_name": "置顶重要事项",
                    "step_description": "待办管理者将重要待办事项设置为置顶显示。",
                    "actor_ids": [
                        3
                    ],
                    "step_type": "actorAction",
                    "next_steps": [
                        "S-005"
                    ]
                },
                {
                    "step_number": "S-005",
                    "step_name": "保存待办事项",
                    "step_description": "系统保存待办事项内容、截止时间、置顶状态和初始完成状态。",
                    "actor_ids": [],
                    "step_type": "systemAction",
                    "next_steps": [
                        "S-006"
                    ]
                },
                {
                    "step_number": "S-006",
                    "step_name": "标记完成状态",
                    "step_description": "待办管理者在任务完成后将待办事项标记为已完成。",
                    "actor_ids": [
                        3
                    ],
                    "step_type": "actorAction",
                    "next_steps": [
                        "S-007"
                    ]
                },
                {
                    "step_number": "S-007",
                    "step_name": "更新任务状态",
                    "step_description": "系统更新待办事项完成状态，并刷新待办清单展示。",
                    "actor_ids": [],
                    "step_type": "systemAction",
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
                    "step_number": "S-001",
                    "step_name": "选择显示控制操作",
                    "step_description": "桌面显示控制者选择一键隐藏所有便签或恢复显示便签。",
                    "actor_ids": [
                        4
                    ],
                    "step_type": "actorAction",
                    "next_steps": [
                        "S-002"
                    ]
                },
                {
                    "step_number": "S-002",
                    "step_name": "判断控制类型",
                    "step_description": "系统判断用户选择的是隐藏所有便签还是恢复显示便签。",
                    "actor_ids": [],
                    "step_type": "judgment",
                    "next_steps": [
                        "S-003",
                        "S-004"
                    ]
                },
                {
                    "step_number": "S-003",
                    "step_name": "隐藏所有便签",
                    "step_description": "系统将所有桌面便签设置为隐藏状态，并更新全局显示控制状态。",
                    "actor_ids": [],
                    "step_type": "systemAction",
                    "next_steps": []
                },
                {
                    "step_number": "S-004",
                    "step_name": "恢复显示便签",
                    "step_description": "系统将已隐藏的便签恢复显示，并更新全局显示控制状态。",
                    "actor_ids": [],
                    "step_type": "systemAction",
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
                19,
                20
            ],
            "flow_steps": [
                {
                    "step_number": "S-001",
                    "step_name": "进入偏好设置",
                    "step_description": "系统偏好设置者打开软件设置入口，进入偏好配置界面。",
                    "actor_ids": [
                        5
                    ],
                    "step_type": "actorAction",
                    "next_steps": [
                        "S-002"
                    ]
                },
                {
                    "step_number": "S-002",
                    "step_name": "配置开机常驻",
                    "step_description": "系统偏好设置者选择是否启用开机自动运行并保持常驻。",
                    "actor_ids": [
                        5
                    ],
                    "step_type": "actorAction",
                    "next_steps": [
                        "S-003"
                    ]
                },
                {
                    "step_number": "S-003",
                    "step_name": "配置默认便签样式",
                    "step_description": "系统偏好设置者设置默认颜色、默认字体、默认字号和默认透明度。",
                    "actor_ids": [
                        5
                    ],
                    "step_type": "actorAction",
                    "next_steps": [
                        "S-004"
                    ]
                },
                {
                    "step_number": "S-004",
                    "step_name": "保存偏好设置",
                    "step_description": "系统保存偏好设置，并将配置用于后续软件启动和新建便签。",
                    "actor_ids": [],
                    "step_type": "systemAction",
                    "next_steps": []
                }
            ]
        }
    ]
}
"""





# 第二步 业务数据对象建模
business_objects_generate_prompt = """
# 角色
你是一个善于设计业务数据对象的数据建模师。

# 任务
1. 分析用户用自然语言描述的项目需求与系统流程。
2. 基于系统流程步骤的数据流转分析出业务对象，例如请假流程，需要为请假条进行业务数据建模。
3. 按照下方规定输出格式输出系统的业务对象建模。

# 用户需求
{{user_requirements}}

# 系统流程
{{flows}}

# 输出格式说明
{
    "business_objects": [
        {
            "business_object_number": "<业务对象编号：例如B-001>", 
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
    ]
}

# 规则
1. 只输出一个 JSON 对象。
2. 不要输出任何解释、分析过程、Markdown、代码块标记或额外前后缀文字。
3. 输出 JSON 风格的标准格式化内容，而不是被压缩的一行内容。
4. business_object_number 必须全局唯一，格式为 B-001、B-002。
5. input_business_object_numbers 和 output_business_object_numbers 只能引用 business_objects 中存在的 business_object_number。
6. business_object_attribute_example 必须是字符串。即使 business_object_attribute_type 是 integer、bool、array[string]、object等，也必须把示例值写成字符串。例如："business_object_attribute_type": "integer","business_object_attribute_example": "14"。
7. business_object_attribute_example 中若本身带有"符号则需要转义，例如"business_object_attribute_example": "[\"M-001\", \"M-003\", \"M-009\"]"，错误写法为"business_object_attribute_example": "["M-001", "M-003", "M-009"]"。

# 示例
## 示例输入
### 用户需求
轻量化桌面悬浮便签 + 待办整合软件，可新建多个独立便签贴在桌面任意位置，支持文字编辑、颜色分类、字体调整；自带待办清单功能，可设置任务截止时间、已完成标记、置顶重要事项，支持开机常驻、透明化背景、一键隐藏所有便签，适合学生、上班族记录临时灵感、日程、琐事。
### 系统流程
{
  "flows": [
    {
      "flow_name": "本地音乐扫描与导入流程",
      "flow_description": "本地音乐听众选择本地音乐目录或文件，系统扫描并导入支持的音频文件，建立可播放的本地音乐库。",
      "flow_steps": [
        {
          "step_number": "S-001",
          "step_name": "选择导入来源",
          "step_description": "本地音乐听众选择需要扫描的本地文件夹或指定的音乐文件作为导入来源。",,
          "next_steps": [
            "S-002"
          ]
        },
        {
          "step_number": "S-002",
          "step_name": "扫描本地音频文件",
          "step_description": "系统读取所选路径中的文件，并识别其中可用的本地音频资源。",
          "next_steps": [
            "S-003"
          ]
        },
        {
          "step_number": "S-003",
          "step_name": "判断文件格式是否支持",
          "step_description": "系统判断扫描到的文件是否属于 Flac、WAV、MP3 等受支持的音频格式。",
          "next_steps": [
            "S-004",
            "S-005"
          ]
        },
        {
          "step_number": "S-004",
          "step_name": "导入支持格式文件",
          "step_description": "系统将符合要求的音频文件加入本地音乐库，并提取基础元数据用于展示和播放。",
          "next_steps": [
            "S-006"
          ]
        },
        {
          "step_number": "S-005",
          "step_name": "跳过不支持文件",
          "step_description": "系统忽略不支持的文件格式，不将其加入本地音乐库。",
          "next_steps": [
            "S-006"
          ]
        },
        {
          "step_number": "S-006",
          "step_name": "生成导入结果",
          "step_description": "系统完成导入并更新本地音乐列表，供后续浏览、播放和歌单管理使用。",
          "next_steps": []
        }
      ]
    },
    {
      "flow_name": "本地音乐播放控制流程",
      "flow_description": "本地音乐听众或快捷键控制者对已导入的本地音乐执行播放、暂停、切换歌曲和调整播放进度等操作。",
      "flow_steps": [
        {
          "step_number": "S-001",
          "step_name": "选择播放目标",
          "step_description": "本地音乐听众从本地音乐库或当前歌单中选择要播放的歌曲。",
          "next_steps": [
            "S-002"
          ]
        },
        {
          "step_number": "S-002",
          "step_name": "加载音频资源",
          "step_description": "系统读取所选歌曲的本地音频文件并初始化播放状态。",
          "next_steps": [
            "S-003"
          ]
        },
        {
          "step_number": "S-003",
          "step_name": "开始播放歌曲",
          "step_description": "系统开始输出音频，并更新当前播放信息与进度。",
          "next_steps": [
            "S-004"
          ]
        },
        {
          "step_number": "S-004",
          "step_name": "选择播放控制操作",
          "step_description": "本地音乐听众或快捷键控制者选择播放暂停、上一首、下一首或拖动进度条等控制操作。",
          "next_steps": [
            "S-005"
          ]
        },
        {
          "step_number": "S-005",
          "step_name": "判断控制类型",
          "step_description": "系统判断当前控制操作属于暂停或继续播放、切换上一首、切换下一首，还是调整播放进度。",
          "next_steps": [
            "S-006",
            "S-007",
            "S-008",
            "S-009"
          ]
        },
        {
          "step_number": "S-006",
          "step_name": "更新播放暂停状态",
          "step_description": "系统根据操作暂停当前歌曲或恢复播放，并同步更新播放状态显示。",
          "next_steps": []
        },
        {
          "step_number": "S-007",
          "step_name": "切换到上一首",
          "step_description": "系统定位到播放队列中的上一首歌曲并开始播放。",
          "next_steps": []
        },
        {
          "step_number": "S-008",
          "step_name": "切换到下一首",
          "step_description": "系统定位到播放队列中的下一首歌曲并开始播放。",
          "next_steps": []
        },
        {
          "step_number": "S-009",
          "step_name": "调整播放进度",
          "step_description": "系统将当前播放位置移动到用户指定进度，并从新位置继续播放。",
          "next_steps": []
        }
      ]
    },
    {
      "flow_name": "歌单创建与维护流程",
      "flow_description": "歌单管理者或本地音乐听众创建歌单，并将本地歌曲添加、移除、排序和删除歌单内容。",
      "flow_steps": [
        {
          "step_number": "S-001",
          "step_name": "选择歌单管理操作",
          "step_description": "歌单管理者进入歌单管理界面，选择新建歌单或维护已有歌单内容。",
          "next_steps": [
            "S-002"
          ]
        },
        {
          "step_number": "S-002",
          "step_name": "判断是否已有目标歌单",
          "step_description": "系统判断当前操作是创建新歌单，还是编辑已有歌单。",
          "next_steps": [
            "S-003",
            "S-004"
          ]
        },
        {
          "step_number": "S-003",
          "step_name": "新建歌单",
          "step_description": "歌单管理者输入歌单名称并提交创建请求。",
          "next_steps": [
            "S-004"
          ]
        },
        {
          "step_number": "S-004",
          "step_name": "选择歌单编辑动作",
          "step_description": "歌单管理者或本地音乐听众选择向歌单添加歌曲、从歌单移除歌曲、调整顺序或删除歌单。",
          "next_steps": [
            "S-005"
          ]
        },
        {
          "step_number": "S-005",
          "step_name": "判断编辑动作类型",
          "step_description": "系统判断当前歌单编辑动作属于添加歌曲、移除歌曲、排序歌曲还是删除歌单。",
          "next_steps": [
            "S-006",
            "S-007",
            "S-008",
            "S-009"
          ]
        },
        {
          "step_number": "S-006",
          "step_name": "添加歌曲到歌单",
          "step_description": "系统将选中的本地歌曲加入目标歌单，并更新歌单内容。",
          "next_steps": []
        },
        {
          "step_number": "S-007",
          "step_name": "从歌单移除歌曲",
          "step_description": "系统将指定歌曲从目标歌单中移除，并更新歌单内容。",
          "next_steps": []
        },
        {
          "step_number": "S-008",
          "step_name": "调整歌单顺序",
          "step_description": "系统保存歌单内歌曲的新顺序和自定义内容布局。",
          "next_steps": []
        },
        {
          "step_number": "S-009",
          "step_name": "删除歌单",
          "step_description": "系统删除目标歌单及其关联的歌单结构，但不删除本地音乐文件本身。",
          "next_steps": []
        }
      ]
    },
    {
      "flow_name": "本地歌词匹配与显示流程",
      "flow_description": "歌词匹配者或本地音乐听众为当前歌曲匹配本地歌词，显示歌词内容，并在需要时调整同步与维护关联关系。",
      "flow_steps": [
        {
          "step_number": "S-001",
          "step_name": "播放目标歌曲",
          "step_description": "本地音乐听众播放一首本地歌曲，触发对应歌词的查找与展示需求。",
          "next_steps": [
            "S-002"
          ]
        },
        {
          "step_number": "S-002",
          "step_name": "自动匹配本地歌词",
          "step_description": "系统根据歌曲名称、艺术家或同名文件规则，在本地目录中查找可用歌词文件或歌词内容。",
          "next_steps": [
            "S-003"
          ]
        },
        {
          "step_number": "S-003",
          "step_name": "判断是否匹配成功",
          "step_description": "系统判断当前歌曲是否找到可关联的本地歌词资源。",
          "next_steps": [
            "S-004",
            "S-005"
          ]
        },
        {
          "step_number": "S-004",
          "step_name": "显示歌词内容",
          "step_description": "系统在播放界面展示已匹配歌词，并随播放进度进行同步滚动或定位。",
          "next_steps": [
            "S-006"
          ]
        },
        {
          "step_number": "S-005",
          "step_name": "提示无可用歌词",
          "step_description": "系统提示当前歌曲未找到可匹配的本地歌词，并保留后续手动维护关联的入口。",
          "next_steps": [
            "S-006"
          ]
        },
        {
          "step_number": "S-006",
          "step_name": "选择歌词维护操作",
          "step_description": "歌词匹配者可选择调整歌词同步偏移，或重新管理歌词与歌曲的关联结果。",
          "next_steps": [
            "S-007"
          ]
        },
        {
          "step_number": "S-007",
          "step_name": "判断维护类型",
          "step_description": "系统判断当前维护操作属于歌词同步调整还是歌词关联管理。",
          "next_steps": [
            "S-008",
            "S-009"
          ]
        },
        {
          "step_number": "S-008",
          "step_name": "保存歌词同步设置",
          "step_description": "系统记录歌词时间偏移或同步参数，并立即刷新歌词显示效果。",
          "next_steps": []
        },
        {
          "step_number": "S-009",
          "step_name": "更新歌词关联关系",
          "step_description": "系统保存歌词文件与歌曲之间的关联结果，用于后续自动显示与匹配优化。",
          "next_steps": []
        }
      ]
    },
    {
      "flow_name": "音效与均衡器配置流程",
      "flow_description": "音效调节者进入音效设置界面，选择预设方案或手动调节均衡器与相关参数，并保存个人偏好。",
      "flow_steps": [
        {
          "step_number": "S-001",
          "step_name": "进入音效设置",
          "step_description": "音效调节者打开播放器音效设置界面，准备调整当前播放的听感效果。",
          "next_steps": [
            "S-002"
          ]
        },
        {
          "step_number": "S-002",
          "step_name": "选择音效调整方式",
          "step_description": "音效调节者选择使用系统预设音效方案，或手动配置均衡器和其他音效参数。",
          "next_steps": [
            "S-003"
          ]
        },
        {
          "step_number": "S-003",
          "step_name": "判断调整方式",
          "step_description": "系统判断当前使用的是预设音效切换，还是手动参数调节。",
          "next_steps": [
            "S-004",
            "S-005"
          ]
        },
        {
          "step_number": "S-004",
          "step_name": "切换预设音效",
          "step_description": "系统应用所选预设音效方案到当前播放输出。",
          "next_steps": [
            "S-006"
          ]
        },
        {
          "step_number": "S-005",
          "step_name": "手动调节均衡器参数",
          "step_description": "音效调节者调整各频段均衡器和相关音效参数，以满足个人听感偏好。",
          "next_steps": [
            "S-006"
          ]
        },
        {
          "step_number": "S-006",
          "step_name": "保存音效偏好",
          "step_description": "系统保存当前音效参数配置或预设选择结果，供后续播放继续使用。",
          "next_steps": []
        }
      ]
    },
    {
      "flow_name": "睡眠定时关闭流程",
      "flow_description": "睡眠定时设置者设置播放器定时关闭时间，查看剩余倒计时，并可取消定时或指定到时后的播放处理方式。",
      "flow_steps": [
        {
          "step_number": "S-001",
          "step_name": "进入睡眠定时设置",
          "step_description": "睡眠定时设置者打开睡眠定时功能入口，准备配置自动结束播放行为。",
          "next_steps": [
            "S-002"
          ]
        },
        {
          "step_number": "S-002",
          "step_name": "设置关闭时间与结束行为",
          "step_description": "睡眠定时设置者设置定时关闭时长，并选择到时后停止播放或关闭程序等处理方式。",
          "next_steps": [
            "S-003"
          ]
        },
        {
          "step_number": "S-003",
          "step_name": "启动定时任务",
          "step_description": "系统记录定时关闭配置并开始倒计时。",
          "next_steps": [
            "S-004"
          ]
        },
        {
          "step_number": "S-004",
          "step_name": "查看或管理定时状态",
          "step_description": "睡眠定时设置者查看剩余倒计时，并决定继续等待还是取消当前定时任务。",
          "next_steps": [
            "S-005"
          ]
        },
        {
          "step_number": "S-005",
          "step_name": "判断是否取消定时",
          "step_description": "系统判断用户是否发起取消定时操作，或继续等待倒计时结束。",
          "next_steps": [
            "S-006",
            "S-007"
          ]
        },
        {
          "step_number": "S-006",
          "step_name": "取消定时任务",
          "step_description": "系统停止当前倒计时并清除已设置的定时关闭任务。",
          "next_steps": []
        },
        {
          "step_number": "S-007",
          "step_name": "执行到时结束行为",
          "step_description": "系统在倒计时结束后，按配置执行停止播放或关闭程序等处理方式。",
          "next_steps": []
        }
      ]
    },
    {
      "flow_name": "全局快捷键配置与控制流程",
      "flow_description": "快捷键控制者设置全局快捷键，并在播放器前后台场景下通过快捷键快速控制播放状态与切歌操作。",
      "flow_steps": [
        {
          "step_number": "S-001",
          "step_name": "进入快捷键设置",
          "step_description": "快捷键控制者打开播放器的快捷键设置界面。",
          "next_steps": [
            "S-002"
          ]
        },
        {
          "step_number": "S-002",
          "step_name": "配置全局快捷键",
          "step_description": "快捷键控制者为播放暂停、上一首、下一首等操作设置全局快捷键组合。",
          "next_steps": [
            "S-003"
          ]
        },
        {
          "step_number": "S-003",
          "step_name": "保存快捷键映射",
          "step_description": "系统保存快捷键配置并注册全局快捷键监听能力。",
          "next_steps": [
            "S-004"
          ]
        },
        {
          "step_number": "S-004",
          "step_name": "触发全局快捷键",
          "step_description": "快捷键控制者在任意界面下按下已配置的全局快捷键以控制播放器。",
          "next_steps": [
            "S-005"
          ]
        },
        {
          "step_number": "S-005",
          "step_name": "判断快捷键对应动作",
          "step_description": "系统识别当前快捷键对应的是播放暂停、上一首、下一首或其他快速播放状态调节操作。",
          "next_steps": [
            "S-006",
            "S-007",
            "S-008",
            "S-009"
          ]
        },
        {
          "step_number": "S-006",
          "step_name": "执行播放暂停控制",
          "step_description": "系统根据快捷键指令切换播放或暂停状态。",
          "next_steps": []
        },
        {
          "step_number": "S-007",
          "step_name": "执行上一首切换",
          "step_description": "系统根据快捷键指令切换到上一首歌曲。",
          "next_steps": []
        },
        {
          "step_number": "S-008",
          "step_name": "执行下一首切换",
          "step_description": "系统根据快捷键指令切换到下一首歌曲。",
          "next_steps": []
        },
        {
          "step_number": "S-009",
          "step_name": "执行快速播放状态调节",
          "step_description": "系统根据快捷键指令执行其他已配置的播放状态快速调节操作。",
          "next_steps": []
        }
      ]
    },
    {
      "flow_name": "界面偏好与轻量化布局设置流程",
      "flow_description": "界面偏好设置者调整播放器显示样式、切换轻量化布局并管理视觉风格偏好，以保持清爽低干扰的使用体验。",
      "flow_steps": [
        {
          "step_number": "S-001",
          "step_name": "进入界面设置",
          "step_description": "界面偏好设置者打开播放器界面与外观设置入口。",
          "next_steps": [
            "S-002"
          ]
        },
        {
          "step_number": "S-002",
          "step_name": "选择界面调整项目",
          "step_description": "界面偏好设置者选择调整显示样式、切换轻量化布局或修改视觉风格与外观偏好。",
          "next_steps": [
            "S-003"
          ]
        },
        {
          "step_number": "S-003",
          "step_name": "判断调整类型",
          "step_description": "系统判断当前修改属于界面显示样式调整、轻量化布局切换还是视觉风格偏好管理。",
          "next_steps": [
            "S-004",
            "S-005",
            "S-006"
          ]
        },
        {
          "step_number": "S-004",
          "step_name": "应用显示样式调整",
          "step_description": "系统应用新的界面显示样式设置，使界面元素更清爽直观。",
          "next_steps": [
            "S-007"
          ]
        },
        {
          "step_number": "S-005",
          "step_name": "应用轻量化布局",
          "step_description": "系统切换为更精简的布局方案，减少非必要视觉元素和操作干扰。",
          "next_steps": [
            "S-007"
          ]
        },
        {
          "step_number": "S-006",
          "step_name": "应用视觉风格偏好",
          "step_description": "系统应用用户设置的视觉风格和外观偏好，使播放器符合长期使用习惯。",
          "next_steps": [
            "S-007"
          ]
        },
        {
          "step_number": "S-007",
          "step_name": "保存界面配置",
          "step_description": "系统保存界面相关设置，并在后续启动和使用过程中持续生效。",
          "next_steps": []
        }
      ]
    }
  ]
}

## 示例输出
{
    "business_objects": [
        {
            "business_object_number": "B-001",
            "business_object_name": "桌面便签",
            "business_object_description": "用户创建并贴在桌面任意位置的独立便签实体，用于记录文字内容、灵感、日程和琐事。",
            "business_object_attributes": [
                {
                    "business_object_attribute_name": "note_id",
                    "business_object_attribute_description": "便签唯一标识",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "N-20260520-001"
                },
                {
                    "business_object_attribute_name": "title",
                    "business_object_attribute_description": "便签标题或摘要",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "今日复习重点"
                },
                {
                    "business_object_attribute_name": "content",
                    "business_object_attribute_description": "便签正文内容",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "整理英语单词，完成数学错题本"
                },
                {
                    "business_object_attribute_name": "created_at",
                    "business_object_attribute_description": "便签创建时间",
                    "business_object_attribute_type": "datetime",
                    "business_object_attribute_example": "2026-05-20 09:30:00"
                },
                {
                    "business_object_attribute_name": "updated_at",
                    "business_object_attribute_description": "便签最近更新时间",
                    "business_object_attribute_type": "datetime",
                    "business_object_attribute_example": "2026-05-20 10:15:00"
                },
                {
                    "business_object_attribute_name": "is_deleted",
                    "business_object_attribute_description": "便签是否已删除",
                    "business_object_attribute_type": "bool",
                    "business_object_attribute_example": "false"
                }
            ]
        },
        {
            "business_object_number": "B-002",
            "business_object_name": "便签样式配置",
            "business_object_description": "描述单个便签的颜色分类、字体、字号和背景透明度等显示样式。",
            "business_object_attributes": [
                {
                    "business_object_attribute_name": "style_id",
                    "business_object_attribute_description": "样式配置唯一标识",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "STYLE-001"
                },
                {
                    "business_object_attribute_name": "note_id",
                    "business_object_attribute_description": "关联的便签标识",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "N-20260520-001"
                },
                {
                    "business_object_attribute_name": "color_category",
                    "business_object_attribute_description": "便签颜色分类",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "学习"
                },
                {
                    "business_object_attribute_name": "background_color",
                    "business_object_attribute_description": "便签背景颜色",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "#FFF6A6"
                },
                {
                    "business_object_attribute_name": "font_family",
                    "business_object_attribute_description": "便签文字字体",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "Microsoft YaHei"
                },
                {
                    "business_object_attribute_name": "font_size",
                    "business_object_attribute_description": "便签文字字号",
                    "business_object_attribute_type": "integer",
                    "business_object_attribute_example": "14"
                },
                {
                    "business_object_attribute_name": "opacity",
                    "business_object_attribute_description": "便签背景透明度",
                    "business_object_attribute_type": "float",
                    "business_object_attribute_example": "0.75"
                }
            ]
        },
        {
            "business_object_number": "B-003",
            "business_object_name": "便签桌面位置状态",
            "business_object_description": "记录便签在桌面上的窗口位置、尺寸、层级和显示状态。",
            "business_object_attributes": [
                {
                    "business_object_attribute_name": "position_id",
                    "business_object_attribute_description": "位置状态唯一标识",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "POS-001"
                },
                {
                    "business_object_attribute_name": "note_id",
                    "business_object_attribute_description": "关联的便签标识",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "N-20260520-001"
                },
                {
                    "business_object_attribute_name": "x",
                    "business_object_attribute_description": "便签窗口左上角横坐标",
                    "business_object_attribute_type": "integer",
                    "business_object_attribute_example": "1280"
                },
                {
                    "business_object_attribute_name": "y",
                    "business_object_attribute_description": "便签窗口左上角纵坐标",
                    "business_object_attribute_type": "integer",
                    "business_object_attribute_example": "220"
                },
                {
                    "business_object_attribute_name": "width",
                    "business_object_attribute_description": "便签窗口宽度",
                    "business_object_attribute_type": "integer",
                    "business_object_attribute_example": "280"
                },
                {
                    "business_object_attribute_name": "height",
                    "business_object_attribute_description": "便签窗口高度",
                    "business_object_attribute_type": "integer",
                    "business_object_attribute_example": "180"
                },
                {
                    "business_object_attribute_name": "is_visible",
                    "business_object_attribute_description": "便签当前是否显示",
                    "business_object_attribute_type": "bool",
                    "business_object_attribute_example": "true"
                },
                {
                    "business_object_attribute_name": "is_topmost",
                    "business_object_attribute_description": "便签窗口是否保持置顶显示",
                    "business_object_attribute_type": "bool",
                    "business_object_attribute_example": "true"
                }
            ]
        },
        {
            "business_object_number": "B-004",
            "business_object_name": "待办事项",
            "business_object_description": "用户在待办清单中创建的具体任务，用于管理日程、琐事、学习或工作事项。",
            "business_object_attributes": [
                {
                    "business_object_attribute_name": "todo_id",
                    "business_object_attribute_description": "待办事项唯一标识",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "T-20260520-001"
                },
                {
                    "business_object_attribute_name": "content",
                    "business_object_attribute_description": "待办事项内容",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "17点前提交周报"
                },
                {
                    "business_object_attribute_name": "deadline_at",
                    "business_object_attribute_description": "待办事项截止时间",
                    "business_object_attribute_type": "datetime",
                    "business_object_attribute_example": "2026-05-20 17:00:00"
                },
                {
                    "business_object_attribute_name": "is_completed",
                    "business_object_attribute_description": "待办事项是否已完成",
                    "business_object_attribute_type": "bool",
                    "business_object_attribute_example": "false"
                },
                {
                    "business_object_attribute_name": "completed_at",
                    "business_object_attribute_description": "待办事项完成时间",
                    "business_object_attribute_type": "datetime",
                    "business_object_attribute_example": "2026-05-20 16:45:00"
                },
                {
                    "business_object_attribute_name": "is_pinned",
                    "business_object_attribute_description": "待办事项是否置顶为重要事项",
                    "business_object_attribute_type": "bool",
                    "business_object_attribute_example": "true"
                },
                {
                    "business_object_attribute_name": "priority",
                    "business_object_attribute_description": "待办事项优先级",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "high"
                }
            ]
        },
        {
            "business_object_number": "B-005",
            "business_object_name": "待办清单",
            "business_object_description": "承载多个待办事项的清单集合，用于集中展示和管理任务。",
            "business_object_attributes": [
                {
                    "business_object_attribute_name": "todo_list_id",
                    "business_object_attribute_description": "待办清单唯一标识",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "TL-001"
                },
                {
                    "business_object_attribute_name": "list_name",
                    "business_object_attribute_description": "待办清单名称",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "今日待办"
                },
                {
                    "business_object_attribute_name": "todo_ids",
                    "business_object_attribute_description": "清单内待办事项标识列表",
                    "business_object_attribute_type": "array[string]",
                    "business_object_attribute_example": "[\"T-20260520-001\", \"T-20260520-002\"]"
                },
                {
                    "business_object_attribute_name": "sort_rule",
                    "business_object_attribute_description": "待办事项排序规则",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "pinned_first_then_deadline"
                }
            ]
        },
        {
            "business_object_number": "B-006",
            "business_object_name": "应用运行配置",
            "business_object_description": "记录软件启动、常驻、全局隐藏和基础运行行为的配置。",
            "business_object_attributes": [
                {
                    "business_object_attribute_name": "config_id",
                    "business_object_attribute_description": "运行配置唯一标识",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "APP-CONFIG-001"
                },
                {
                    "business_object_attribute_name": "launch_on_startup",
                    "business_object_attribute_description": "是否开机自启动",
                    "business_object_attribute_type": "bool",
                    "business_object_attribute_example": "true"
                },
                {
                    "business_object_attribute_name": "stay_resident",
                    "business_object_attribute_description": "是否后台常驻运行",
                    "business_object_attribute_type": "bool",
                    "business_object_attribute_example": "true"
                },
                {
                    "business_object_attribute_name": "all_notes_hidden",
                    "business_object_attribute_description": "是否处于一键隐藏全部便签状态",
                    "business_object_attribute_type": "bool",
                    "business_object_attribute_example": "false"
                },
                {
                    "business_object_attribute_name": "default_opacity",
                    "business_object_attribute_description": "新建便签默认透明度",
                    "business_object_attribute_type": "float",
                    "business_object_attribute_example": "0.85"
                }
            ]
        },
        {
            "business_object_number": "B-007",
            "business_object_name": "便签待办关联关系",
            "business_object_description": "记录便签与待办事项之间的关联，用于从便签内容转化待办或在便签中展示待办任务。",
            "business_object_attributes": [
                {
                    "business_object_attribute_name": "relation_id",
                    "business_object_attribute_description": "关联关系唯一标识",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "REL-001"
                },
                {
                    "business_object_attribute_name": "note_id",
                    "business_object_attribute_description": "关联的便签标识",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "N-20260520-001"
                },
                {
                    "business_object_attribute_name": "todo_id",
                    "business_object_attribute_description": "关联的待办事项标识",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "T-20260520-001"
                },
                {
                    "business_object_attribute_name": "relation_type",
                    "business_object_attribute_description": "便签与待办的关联方式",
                    "business_object_attribute_type": "string",
                    "business_object_attribute_example": "note_contains_todo"
                }
            ]
        }
    ]
}
"""





# 第三步 对齐业务数据对象与系统流程
business_object_in_flows_prompt = """
# 角色
你是一个善于设计业务数据流转的软件设计师。

# 任务
1. 分析业务对象与系统流程。
2. 基于系统流程步骤的数据流转，对齐业务对象。
3. 按照下方规定输出格式输出系统的主要流程以及每个流程的具体步骤。

# 用户需求
{{user_requirements}}

# 系统流程
{{flows}}

# 业务对象
{{business_objects}}

# 输出格式
{
    "business_object_in_flows": [ 
        { 
            "flow_name": "<流程名称（例如‘请假审批流程’）>", 
            "flow_steps":[ 
                { 
                    "step_number": "<步骤编号：例如S-001>", 
                    "input_business_object_numbers": ["<输入的业务对象1的编号>", "<输入的业务对象2的编号>", ...(可空)], 
                    "output_business_object_numbers": ["<输出的业务对象1的编号>", "<输出的业务对象2的编号>", ...(可空)], 
                    "next_steps": ["<下一步走向1的编号>", "<下一步走向2的编号>", ...(可空，空表示流程结束；多个值表示该点为分岔点，存在多种可能的路径)] 
                }, 
                { 
                    "step_number": "<步骤编号：例如S-001>",
                    "input_business_object_numbers": ["<输入的业务对象1的编号>", "<输入的业务对象2的编号>", ...(可空)],
                    "output_business_object_numbers": ["<输出的业务对象1的编号>", "<输出的业务对象2的编号>", ...(可空)], 
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

# 示例
## 示例输入
### 用户需求
轻量化桌面悬浮便签 + 待办整合软件，可新建多个独立便签贴在桌面任意位置，支持文字编辑、颜色分类、字体调整；自带待办清单功能，可设置任务截止时间、已完成标记、置顶重要事项，支持开机常驻、透明化背景、一键隐藏所有便签，适合学生、上班族记录临时灵感、日程、琐事。
### 系统流程
{
  "flows": [
    {
      "flow_name": "本地音乐扫描与导入流程",
      "flow_description": "本地音乐听众选择本地音乐目录或文件，系统扫描并导入支持的音频文件，建立可播放的本地音乐库。",
      "flow_steps": [
        {
          "step_number": "S-001",
          "step_name": "选择导入来源",
          "step_description": "本地音乐听众选择需要扫描的本地文件夹或指定的音乐文件作为导入来源。",
          "next_steps": [
            "S-002"
          ]
        },
        {
          "step_number": "S-002",
          "step_name": "扫描本地音频文件",
          "step_description": "系统读取所选路径中的文件，并识别其中可用的本地音频资源。",
          "next_steps": [
            "S-003"
          ]
        },
        {
          "step_number": "S-003",
          "step_name": "判断文件格式是否支持",
          "step_description": "系统判断扫描到的文件是否属于 Flac、WAV、MP3 等受支持的音频格式。",
          "next_steps": [
            "S-004",
            "S-005"
          ]
        },
        {
          "step_number": "S-004",
          "step_name": "导入支持格式文件",
          "step_description": "系统将符合要求的音频文件加入本地音乐库，并提取基础元数据用于展示和播放。",
          "next_steps": [
            "S-006"
          ]
        },
        {
          "step_number": "S-005",
          "step_name": "跳过不支持文件",
          "step_description": "系统忽略不支持的文件格式，不将其加入本地音乐库。",
          "next_steps": [
            "S-006"
          ]
        },
        {
          "step_number": "S-006",
          "step_name": "生成导入结果",
          "step_description": "系统完成导入并更新本地音乐列表，供后续浏览、播放和歌单管理使用。",
          "next_steps": []
        }
      ]
    },
    {
      "flow_name": "本地音乐播放控制流程",
      "flow_description": "本地音乐听众或快捷键控制者对已导入的本地音乐执行播放、暂停、切换歌曲和调整播放进度等操作。",
      "flow_steps": [
        {
          "step_number": "S-001",
          "step_name": "选择播放目标",
          "step_description": "本地音乐听众从本地音乐库或当前歌单中选择要播放的歌曲。",
          "next_steps": [
            "S-002"
          ]
        },
        {
          "step_number": "S-002",
          "step_name": "加载音频资源",
          "step_description": "系统读取所选歌曲的本地音频文件并初始化播放状态。",
          "next_steps": [
            "S-003"
          ]
        },
        {
          "step_number": "S-003",
          "step_name": "开始播放歌曲",
          "step_description": "系统开始输出音频，并更新当前播放信息与进度。",
          "next_steps": [
            "S-004"
          ]
        },
        {
          "step_number": "S-004",
          "step_name": "选择播放控制操作",
          "step_description": "本地音乐听众或快捷键控制者选择播放暂停、上一首、下一首或拖动进度条等控制操作。",
          "next_steps": [
            "S-005"
          ]
        },
        {
          "step_number": "S-005",
          "step_name": "判断控制类型",
          "step_description": "系统判断当前控制操作属于暂停或继续播放、切换上一首、切换下一首，还是调整播放进度。",
          "next_steps": [
            "S-006",
            "S-007",
            "S-008",
            "S-009"
          ]
        },
        {
          "step_number": "S-006",
          "step_name": "更新播放暂停状态",
          "step_description": "系统根据操作暂停当前歌曲或恢复播放，并同步更新播放状态显示。",
          "next_steps": []
        },
        {
          "step_number": "S-007",
          "step_name": "切换到上一首",
          "step_description": "系统定位到播放队列中的上一首歌曲并开始播放。",
          "next_steps": []
        },
        {
          "step_number": "S-008",
          "step_name": "切换到下一首",
          "step_description": "系统定位到播放队列中的下一首歌曲并开始播放。",
          "next_steps": []
        },
        {
          "step_number": "S-009",
          "step_name": "调整播放进度",
          "step_description": "系统将当前播放位置移动到用户指定进度，并从新位置继续播放。", 
          "next_steps": []
        }
      ]
    },
    {
      "flow_name": "歌单创建与维护流程",
      "flow_description": "歌单管理者或本地音乐听众创建歌单，并将本地歌曲添加、移除、排序和删除歌单内容。",
      "flow_steps": [
        {
          "step_number": "S-001",
          "step_name": "选择歌单管理操作",
          "step_description": "歌单管理者进入歌单管理界面，选择新建歌单或维护已有歌单内容。",
          "next_steps": [
            "S-002"
          ]
        },
        {
          "step_number": "S-002",
          "step_name": "判断是否已有目标歌单",
          "step_description": "系统判断当前操作是创建新歌单，还是编辑已有歌单。",
          "next_steps": [
            "S-003",
            "S-004"
          ]
        },
        {
          "step_number": "S-003",
          "step_name": "新建歌单",
          "step_description": "歌单管理者输入歌单名称并提交创建请求。",
          "next_steps": [
            "S-004"
          ]
        },
        {
          "step_number": "S-004",
          "step_name": "选择歌单编辑动作",
          "step_description": "歌单管理者或本地音乐听众选择向歌单添加歌曲、从歌单移除歌曲、调整顺序或删除歌单。",
          "next_steps": [
            "S-005"
          ]
        },
        {
          "step_number": "S-005",
          "step_name": "判断编辑动作类型",
          "step_description": "系统判断当前歌单编辑动作属于添加歌曲、移除歌曲、排序歌曲还是删除歌单。",
          "next_steps": [
            "S-006",
            "S-007",
            "S-008",
            "S-009"
          ]
        },
        {
          "step_number": "S-006",
          "step_name": "添加歌曲到歌单",
          "step_description": "系统将选中的本地歌曲加入目标歌单，并更新歌单内容。",
          "next_steps": []
        },
        {
          "step_number": "S-007",
          "step_name": "从歌单移除歌曲",
          "step_description": "系统将指定歌曲从目标歌单中移除，并更新歌单内容。",
          "next_steps": []
        },
        {
          "step_number": "S-008",
          "step_name": "调整歌单顺序",
          "step_description": "系统保存歌单内歌曲的新顺序和自定义内容布局。",
          "next_steps": []
        },
        {
          "step_number": "S-009",
          "step_name": "删除歌单",
          "step_description": "系统删除目标歌单及其关联的歌单结构，但不删除本地音乐文件本身。",
          "next_steps": []
        }
      ]
    },
    {
      "flow_name": "本地歌词匹配与显示流程",
      "flow_description": "歌词匹配者或本地音乐听众为当前歌曲匹配本地歌词，显示歌词内容，并在需要时调整同步与维护关联关系。",
      "flow_steps": [
        {
          "step_number": "S-001",
          "step_name": "播放目标歌曲",
          "step_description": "本地音乐听众播放一首本地歌曲，触发对应歌词的查找与展示需求。",
          "next_steps": [
            "S-002"
          ]
        },
        {
          "step_number": "S-002",
          "step_name": "自动匹配本地歌词",
          "step_description": "系统根据歌曲名称、艺术家或同名文件规则，在本地目录中查找可用歌词文件或歌词内容。",
          "next_steps": [
            "S-003"
          ]
        },
        {
          "step_number": "S-003",
          "step_name": "判断是否匹配成功",
          "step_description": "系统判断当前歌曲是否找到可关联的本地歌词资源。",
          "next_steps": [
            "S-004",
            "S-005"
          ]
        },
        {
          "step_number": "S-004",
          "step_name": "显示歌词内容",
          "step_description": "系统在播放界面展示已匹配歌词，并随播放进度进行同步滚动或定位。",
          "next_steps": [
            "S-006"
          ]
        },
        {
          "step_number": "S-005",
          "step_name": "提示无可用歌词",
          "step_description": "系统提示当前歌曲未找到可匹配的本地歌词，并保留后续手动维护关联的入口。",
          "next_steps": [
            "S-006"
          ]
        },
        {
          "step_number": "S-006",
          "step_name": "选择歌词维护操作",
          "step_description": "歌词匹配者可选择调整歌词同步偏移，或重新管理歌词与歌曲的关联结果。",
          "next_steps": [
            "S-007"
          ]
        },
        {
          "step_number": "S-007",
          "step_name": "判断维护类型",
          "step_description": "系统判断当前维护操作属于歌词同步调整还是歌词关联管理。",
          "next_steps": [
            "S-008",
            "S-009"
          ]
        },
        {
          "step_number": "S-008",
          "step_name": "保存歌词同步设置",
          "step_description": "系统记录歌词时间偏移或同步参数，并立即刷新歌词显示效果。",
          "next_steps": []
        },
        {
          "step_number": "S-009",
          "step_name": "更新歌词关联关系",
          "step_description": "系统保存歌词文件与歌曲之间的关联结果，用于后续自动显示与匹配优化。",
          "next_steps": []
        }
      ]
    },
    {
      "flow_name": "音效与均衡器配置流程",
      "flow_description": "音效调节者进入音效设置界面，选择预设方案或手动调节均衡器与相关参数，并保存个人偏好。",
      "flow_steps": [
        {
          "step_number": "S-001",
          "step_name": "进入音效设置",
          "step_description": "音效调节者打开播放器音效设置界面，准备调整当前播放的听感效果。",
          "next_steps": [
            "S-002"
          ]
        },
        {
          "step_number": "S-002",
          "step_name": "选择音效调整方式",
          "step_description": "音效调节者选择使用系统预设音效方案，或手动配置均衡器和其他音效参数。",
          "next_steps": [
            "S-003"
          ]
        },
        {
          "step_number": "S-003",
          "step_name": "判断调整方式",
          "step_description": "系统判断当前使用的是预设音效切换，还是手动参数调节。",
          "next_steps": [
            "S-004",
            "S-005"
          ]
        },
        {
          "step_number": "S-004",
          "step_name": "切换预设音效",
          "step_description": "系统应用所选预设音效方案到当前播放输出。",
          "next_steps": [
            "S-006"
          ]
        },
        {
          "step_number": "S-005",
          "step_name": "手动调节均衡器参数",
          "step_description": "音效调节者调整各频段均衡器和相关音效参数，以满足个人听感偏好。",
          "next_steps": [
            "S-006"
          ]
        },
        {
          "step_number": "S-006",
          "step_name": "保存音效偏好",
          "step_description": "系统保存当前音效参数配置或预设选择结果，供后续播放继续使用。",
          "next_steps": []
        }
      ]
    },
    {
      "flow_name": "睡眠定时关闭流程",
      "flow_description": "睡眠定时设置者设置播放器定时关闭时间，查看剩余倒计时，并可取消定时或指定到时后的播放处理方式。",
      "flow_steps": [
        {
          "step_number": "S-001",
          "step_name": "进入睡眠定时设置",
          "step_description": "睡眠定时设置者打开睡眠定时功能入口，准备配置自动结束播放行为。",
          "next_steps": [
            "S-002"
          ]
        },
        {
          "step_number": "S-002",
          "step_name": "设置关闭时间与结束行为",
          "step_description": "睡眠定时设置者设置定时关闭时长，并选择到时后停止播放或关闭程序等处理方式。",
          "next_steps": [
            "S-003"
          ]
        },
        {
          "step_number": "S-003",
          "step_name": "启动定时任务",
          "step_description": "系统记录定时关闭配置并开始倒计时。",
          "next_steps": [
            "S-004"
          ]
        },
        {
          "step_number": "S-004",
          "step_name": "查看或管理定时状态",
          "step_description": "睡眠定时设置者查看剩余倒计时，并决定继续等待还是取消当前定时任务。",
          "next_steps": [
            "S-005"
          ]
        },
        {
          "step_number": "S-005",
          "step_name": "判断是否取消定时",
          "step_description": "系统判断用户是否发起取消定时操作，或继续等待倒计时结束。",
          "next_steps": [
            "S-006",
            "S-007"
          ]
        },
        {
          "step_number": "S-006",
          "step_name": "取消定时任务",
          "step_description": "系统停止当前倒计时并清除已设置的定时关闭任务。",
          "next_steps": []
        },
        {
          "step_number": "S-007",
          "step_name": "执行到时结束行为",
          "step_description": "系统在倒计时结束后，按配置执行停止播放或关闭程序等处理方式。",
          "next_steps": []
        }
      ]
    },
    {
      "flow_name": "全局快捷键配置与控制流程",
      "flow_description": "快捷键控制者设置全局快捷键，并在播放器前后台场景下通过快捷键快速控制播放状态与切歌操作。",
      "flow_steps": [
        {
          "step_number": "S-001",
          "step_name": "进入快捷键设置",
          "step_description": "快捷键控制者打开播放器的快捷键设置界面。",
          "actor_ids": [
            6
          ],
          "step_type": "actorAction",
          "next_steps": [
            "S-002"
          ]
        },
        {
          "step_number": "S-002",
          "step_name": "配置全局快捷键",
          "step_description": "快捷键控制者为播放暂停、上一首、下一首等操作设置全局快捷键组合。",
          "next_steps": [
            "S-003"
          ]
        },
        {
          "step_number": "S-003",
          "step_name": "保存快捷键映射",
          "step_description": "系统保存快捷键配置并注册全局快捷键监听能力。",
          "next_steps": [
            "S-004"
          ]
        },
        {
          "step_number": "S-004",
          "step_name": "触发全局快捷键",
          "step_description": "快捷键控制者在任意界面下按下已配置的全局快捷键以控制播放器。",
          "next_steps": [
            "S-005"
          ]
        },
        {
          "step_number": "S-005",
          "step_name": "判断快捷键对应动作",
          "step_description": "系统识别当前快捷键对应的是播放暂停、上一首、下一首或其他快速播放状态调节操作。",
          "next_steps": [
            "S-006",
            "S-007",
            "S-008",
            "S-009"
          ]
        },
        {
          "step_number": "S-006",
          "step_name": "执行播放暂停控制",
          "step_description": "系统根据快捷键指令切换播放或暂停状态。",
          "next_steps": []
        },
        {
          "step_number": "S-007",
          "step_name": "执行上一首切换",
          "step_description": "系统根据快捷键指令切换到上一首歌曲。",
          "next_steps": []
        },
        {
          "step_number": "S-008",
          "step_name": "执行下一首切换",
          "step_description": "系统根据快捷键指令切换到下一首歌曲。",
          "next_steps": []
        },
        {
          "step_number": "S-009",
          "step_name": "执行快速播放状态调节",
          "step_description": "系统根据快捷键指令执行其他已配置的播放状态快速调节操作。",
          "next_steps": []
        }
      ]
    },
    {
      "flow_name": "界面偏好与轻量化布局设置流程",
      "flow_description": "界面偏好设置者调整播放器显示样式、切换轻量化布局并管理视觉风格偏好，以保持清爽低干扰的使用体验。",
      "flow_steps": [
        {
          "step_number": "S-001",
          "step_name": "进入界面设置",
          "step_description": "界面偏好设置者打开播放器界面与外观设置入口。",
          "next_steps": [
            "S-002"
          ]
        },
        {
          "step_number": "S-002",
          "step_name": "选择界面调整项目",
          "step_description": "界面偏好设置者选择调整显示样式、切换轻量化布局或修改视觉风格与外观偏好。",
          "next_steps": [
            "S-003"
          ]
        },
        {
          "step_number": "S-003",
          "step_name": "判断调整类型",
          "step_description": "系统判断当前修改属于界面显示样式调整、轻量化布局切换还是视觉风格偏好管理。",
          "next_steps": [
            "S-004",
            "S-005",
            "S-006"
          ]
        },
        {
          "step_number": "S-004",
          "step_name": "应用显示样式调整",
          "step_description": "系统应用新的界面显示样式设置，使界面元素更清爽直观。",
          "next_steps": [
            "S-007"
          ]
        },
        {
          "step_number": "S-005",
          "step_name": "应用轻量化布局",
          "step_description": "系统切换为更精简的布局方案，减少非必要视觉元素和操作干扰。",
          "next_steps": [
            "S-007"
          ]
        },
        {
          "step_number": "S-006",
          "step_name": "应用视觉风格偏好",
          "step_description": "系统应用用户设置的视觉风格和外观偏好，使播放器符合长期使用习惯。",
          "next_steps": [
            "S-007"
          ]
        },
        {
          "step_number": "S-007",
          "step_name": "保存界面配置",
          "step_description": "系统保存界面相关设置，并在后续启动和使用过程中持续生效。",
          "next_steps": []
        }
      ]
    }
  ]
}

## 示例输出
{
    [
        {
            "flow_name": "桌面便签新建与编辑流程",
            "flow_steps": [
                {
                    "step_number": "S-001",
                    "input_business_object_numbers": [],
                    "output_business_object_numbers": [],
                    "next_steps": [
                        "S-002"
                    ]
                },
                {
                    "step_number": "S-002",
                    "input_business_object_numbers": [],
                    "output_business_object_numbers": [
                        "B-001"
                    ],
                    "next_steps": [
                        "S-003"
                    ]
                },
                {
                    "step_number": "S-003",
                    "input_business_object_numbers": [
                        "B-001"
                    ],
                    "output_business_object_numbers": [
                        "B-001"
                    ],
                    "next_steps": [
                        "S-004"
                    ]
                },
                {
                    "step_number": "S-004",
                    "input_business_object_numbers": [
                        "B-001"
                    ],
                    "output_business_object_numbers": [
                        "B-002"
                    ],
                    "next_steps": [
                        "S-005"
                    ]
                },
                {
                    "step_number": "S-005",
                    "input_business_object_numbers": [
                        "B-001",
                        "B-002"
                    ],
                    "output_business_object_numbers": [
                        "B-001",
                        "B-002"
                    ],
                    "next_steps": []
                }
            ]
        },
        {
            "flow_name": "便签桌面定位与显示状态维护流程",
            "flow_steps": [
                {
                    "step_number": "S-001",
                    "input_business_object_numbers": [
                        "B-001"
                    ],
                    "output_business_object_numbers": [],
                    "next_steps": [
                        "S-002"
                    ]
                },
                {
                    "step_number": "S-002",
                    "input_business_object_numbers": [
                        "B-001",
                        "B-003"
                    ],
                    "output_business_object_numbers": [
                        "B-003"
                    ],
                    "next_steps": [
                        "S-003"
                    ]
                },
                {
                    "step_number": "S-003",
                    "input_business_object_numbers": [
                        "B-003"
                    ],
                    "output_business_object_numbers": [
                        "B-003"
                    ],
                    "next_steps": [
                        "S-004",
                        "S-005"
                    ]
                },
                {
                    "step_number": "S-004",
                    "input_business_object_numbers": [
                        "B-003"
                    ],
                    "output_business_object_numbers": [
                        "B-003"
                    ],
                    "next_steps": []
                },
                {
                    "step_number": "S-005",
                    "input_business_object_numbers": [
                        "B-003"
                    ],
                    "output_business_object_numbers": [
                        "B-003"
                    ],
                    "next_steps": []
                }
            ]
        },
        {
            "flow_name": "待办事项创建与截止时间设置流程",
            "flow_steps": [
                {
                    "step_number": "S-001",
                    "input_business_object_numbers": [
                        "B-005"
                    ],
                    "output_business_object_numbers": [],
                    "next_steps": [
                        "S-002"
                    ]
                },
                {
                    "step_number": "S-002",
                    "input_business_object_numbers": [],
                    "output_business_object_numbers": [
                        "B-004"
                    ],
                    "next_steps": [
                        "S-003"
                    ]
                },
                {
                    "step_number": "S-003",
                    "input_business_object_numbers": [
                        "B-004"
                    ],
                    "output_business_object_numbers": [
                        "B-004"
                    ],
                    "next_steps": [
                        "S-004"
                    ]
                },
                {
                    "step_number": "S-004",
                    "input_business_object_numbers": [
                        "B-004",
                        "B-005"
                    ],
                    "output_business_object_numbers": [
                        "B-005"
                    ],
                    "next_steps": []
                }
            ]
        },
        {
            "flow_name": "待办完成与重要事项置顶流程",
            "flow_steps": [
                {
                    "step_number": "S-001",
                    "input_business_object_numbers": [
                        "B-005"
                    ],
                    "output_business_object_numbers": [],
                    "next_steps": [
                        "S-002"
                    ]
                },
                {
                    "step_number": "S-002",
                    "input_business_object_numbers": [
                        "B-004"
                    ],
                    "output_business_object_numbers": [],
                    "next_steps": [
                        "S-003"
                    ]
                },
                {
                    "step_number": "S-003",
                    "input_business_object_numbers": [
                        "B-004"
                    ],
                    "output_business_object_numbers": [],
                    "next_steps": [
                        "S-004",
                        "S-005"
                    ]
                },
                {
                    "step_number": "S-004",
                    "input_business_object_numbers": [
                        "B-004"
                    ],
                    "output_business_object_numbers": [
                        "B-004",
                        "B-005"
                    ],
                    "next_steps": []
                },
                {
                    "step_number": "S-005",
                    "input_business_object_numbers": [
                        "B-004"
                    ],
                    "output_business_object_numbers": [
                        "B-004",
                        "B-005"
                    ],
                    "next_steps": []
                }
            ]
        },
        {
            "flow_name": "便签与待办整合流程",
            "flow_steps": [
                {
                    "step_number": "S-001",
                    "input_business_object_numbers": [
                        "B-001"
                    ],
                    "output_business_object_numbers": [],
                    "next_steps": [
                        "S-002"
                    ]
                },
                {
                    "step_number": "S-002",
                    "input_business_object_numbers": [
                        "B-001"
                    ],
                    "output_business_object_numbers": [],
                    "next_steps": [
                        "S-003",
                        "S-004"
                    ]
                },
                {
                    "step_number": "S-003",
                    "input_business_object_numbers": [
                        "B-001"
                    ],
                    "output_business_object_numbers": [
                        "B-004"
                    ],
                    "next_steps": [
                        "S-005"
                    ]
                },
                {
                    "step_number": "S-004",
                    "input_business_object_numbers": [
                        "B-001",
                        "B-004"
                    ],
                    "output_business_object_numbers": [
                        "B-007"
                    ],
                    "next_steps": [
                        "S-005"
                    ]
                },
                {
                    "step_number": "S-005",
                    "input_business_object_numbers": [
                        "B-004",
                        "B-005",
                        "B-007"
                    ],
                    "output_business_object_numbers": [
                        "B-005",
                        "B-007"
                    ],
                    "next_steps": []
                }
            ]
        },
        {
            "flow_name": "全局隐藏与恢复便签流程",
            "flow_steps": [
                {
                    "step_number": "S-001",
                    "input_business_object_numbers": [
                        "B-006"
                    ],
                    "output_business_object_numbers": [],
                    "next_steps": [
                        "S-002"
                    ]
                },
                {
                    "step_number": "S-002",
                    "input_business_object_numbers": [
                        "B-006"
                    ],
                    "output_business_object_numbers": [],
                    "next_steps": [
                        "S-003",
                        "S-004"
                    ]
                },
                {
                    "step_number": "S-003",
                    "input_business_object_numbers": [
                        "B-003",
                        "B-006"
                    ],
                    "output_business_object_numbers": [
                        "B-003",
                        "B-006"
                    ],
                    "next_steps": []
                },
                {
                    "step_number": "S-004",
                    "input_business_object_numbers": [
                        "B-003",
                        "B-006"
                    ],
                    "output_business_object_numbers": [
                        "B-003",
                        "B-006"
                    ],
                    "next_steps": []
                }
            ]
        },
        {
            "flow_name": "开机常驻与运行配置流程",
            "flow_steps": [
                {
                    "step_number": "S-001",
                    "input_business_object_numbers": [
                        "B-006"
                    ],
                    "output_business_object_numbers": [],
                    "next_steps": [
                        "S-002"
                    ]
                },
                {
                    "step_number": "S-002",
                    "input_business_object_numbers": [
                        "B-006"
                    ],
                    "output_business_object_numbers": [
                        "B-006"
                    ],
                    "next_steps": [
                        "S-003"
                    ]
                },
                {
                    "step_number": "S-003",
                    "input_business_object_numbers": [
                        "B-006"
                    ],
                    "output_business_object_numbers": [
                        "B-006"
                    ],
                    "next_steps": [
                        "S-004"
                    ]
                },
                {
                    "step_number": "S-004",
                    "input_business_object_numbers": [
                        "B-006"
                    ],
                    "output_business_object_numbers": [
                        "B-006"
                    ],
                    "next_steps": []
                }
            ]
        }
    ]
}
"""





flows_generate_prompt_old = """
# 角色
你是一个善于设计项目流程的软件设计师。

# 任务
1. 分析用户用自然语言描述的项目需求、目标系统参与者（用户）、系统功能（features）。
2. 基于系统功能（features）提取出系统的主要流程。
3. 基于提取出系统的主要流程，进一步细化每个流程的具体步骤。
4. 基于提取出的业务流程步骤的输入输出分析出业务对象，例如请假流程，需要为请假条进行业务数据建模。
5. 按照下方规定输出格式输出系统的主要流程以及每个流程的具体步骤。

# 用户需求
{{user_requirements}}

# 参与者（用户）
{{actors}}

# 系统能力（features）
{{features}}

# 输出格式说明
{
    "business_objects": [
        {
            "business_object_number": "<业务对象编号：例如B-001>", 
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
            "flow_name": "<流程名称（例如‘请假审批流程’）>", 
            "flow_description": "<流程描述>", 
            "feature_ids": [<相关feature1的id>, <相关feature2的id>, ...（非空）], 
            "flow_steps":[
                {
                    "step_number": "<步骤编号：例如S-001>", 
                    "step_name": "<步骤名称>", 
                    "step_description": "<步骤描述>", 
                    "actor_ids": [<相关参与者1的id>, <相关参与者2的id>, ...(可空)], 
                    "step_type": "<步骤类型：actorAction|systemAction|judgment>（例如用户输入即为actorAction类型）", 
                    "input_business_object_numbers": ["<输入的业务对象1的编号>", "<输入的业务对象2的编号>", ...(可空)], 
                    "output_business_object_numbers": ["<输出的业务对象1的编号>", "<输出的业务对象2的编号>", ...(可空)], 
                    "next_steps": ["<下一步走向1的编号>", "<下一步走向2的编号>", ...(可空，空表示流程结束；多个值表示该点为分岔点，存在多种可能的路径)]
                }, 
                {
                    "step_number": "<步骤编号：例如S-002>", 
                    "step_name": "<步骤名称>", 
                    "step_description": "<步骤描述>", 
                    "actor_ids": [<相关参与者1的id>, <相关参与者2的id>, ...(可空)], 
                    "step_type": "<步骤类型：actorAction|systemAction|judgment>（例如用户输入即为actorAction类型）", 
                    "input_business_object_numbers": ["<输入的业务对象1的编号>", "<输入的业务对象2的编号>", ...(可空)], 
                    "output_business_object_numbers": ["<输出的业务对象1的编号>", "<输出的业务对象2的编号>", ...(可空)], 
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
4. business_object_number 必须全局唯一，格式为 B-001、B-002。
5. step_number 只需要在当前 flow 内唯一，格式为 S-001、S-002。
6. next_steps 只能引用当前 flow 内存在的 step_number。
7. input_business_object_numbers 和 output_business_object_numbers 只能引用 business_objects 中存在的 business_object_number。
8. feature_ids 只能引用系统能力输入中存在的 feature_id。
9. step_type 只能是 actorAction、systemAction、judgment。
10. business_object_attribute_example 必须是字符串。即使 business_object_attribute_type 是 integer、bool、array[string]、object等，也必须把示例值写成字符串。例如："business_object_attribute_type": "integer","business_object_attribute_example": "14"。
11. business_object_attribute_example 中若本身带有"符号则需要转义，例如"business_object_attribute_example": "[\"M-001\", \"M-003\", \"M-009\"]"，错误写法为"business_object_attribute_example": "["M-001", "M-003", "M-009"]"。

# 示例
## 示例输入
### 用户需求
轻量化桌面悬浮便签 + 待办整合软件，可新建多个独立便签贴在桌面任意位置，支持文字编辑、颜色分类、字体调整；自带待办清单功能，可设置任务截止时间、已完成标记、置顶重要事项，支持开机常驻、透明化背景、一键隐藏所有便签，适合学生、上班族记录临时灵感、日程、琐事。
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
### 系统能力（features）
{
    "features": [
        {
            "feature_id": 3,
            "feature_name": "新建独立便签",
            "feature_description": "支持用户创建多个相互独立的桌面便签，用于记录临时灵感、课程内容、会议要点、日程安排或生活琐事。",
            "actor_ids": [
                1
            ]
        },
        {
            "feature_id": 4,
            "feature_name": "编辑便签文字",
            "feature_description": "支持用户在便签中输入、修改和查看文字内容。",
            "actor_ids": [
                1
            ]
        },
        {
            "feature_id": 5,
            "feature_name": "管理便签位置",
            "feature_description": "支持用户将多个便签放置在桌面任意位置，便于按照个人习惯组织桌面信息。",
            "actor_ids": [
                2
            ]
        },
        {
            "feature_id": 7,
            "feature_name": "颜色分类",
            "feature_description": "支持用户为便签设置不同颜色，用于区分信息类别、优先级或使用场景。",
            "actor_ids": [
                2,
                5
            ]
        },
        {
            "feature_id": 8,
            "feature_name": "字体调整",
            "feature_description": "支持用户调整便签文字的字体样式，使便签内容更符合个人阅读和整理习惯。",
            "actor_ids": [
                2,
                5
            ]
        },
        {
            "feature_id": 10,
            "feature_name": "创建待办事项",
            "feature_description": "支持用户新增待办任务，用于记录需要完成的学习、工作或生活事项。",
            "actor_ids": [
                3
            ]
        },
        {
            "feature_id": 11,
            "feature_name": "设置任务截止时间",
            "feature_description": "支持用户为待办事项设置截止时间，用于安排任务完成节点和日程计划。",
            "actor_ids": [
                3
            ]
        },
        {
            "feature_id": 12,
            "feature_name": "标记任务完成状态",
            "feature_description": "支持用户将待办事项标记为已完成，用于跟踪任务处理进度。",
            "actor_ids": [
                3
            ]
        },
        {
            "feature_id": 13,
            "feature_name": "置顶重要事项",
            "feature_description": "支持用户将重要待办事项置顶显示，便于优先关注和处理关键任务。",
            "actor_ids": [
                3
            ]
        },
        {
            "feature_id": 15,
            "feature_name": "透明化背景",
            "feature_description": "支持用户设置便签背景透明效果，使便签与桌面环境更协调。",
            "actor_ids": [
                4,
                5
            ]
        },
        {
            "feature_id": 16,
            "feature_name": "一键隐藏所有便签",
            "feature_description": "支持用户一次性隐藏所有桌面便签，用于临时清理桌面显示或减少视觉干扰。",
            "actor_ids": [
                4
            ]
        },
        {
            "feature_id": 17,
            "feature_name": "恢复显示便签",
            "feature_description": "支持用户在隐藏便签后恢复显示所有便签，便于继续查看和处理记录内容。",
            "actor_ids": [
                4
            ]
        },
        {
            "feature_id": 19,
            "feature_name": "开机常驻",
            "feature_description": "支持用户设置软件开机后自动运行并保持常驻，便于随时查看和记录信息。",
            "actor_ids": [
                5
            ]
        },
        {
            "feature_id": 20,
            "feature_name": "默认便签样式配置",
            "feature_description": "支持用户配置默认字体、默认颜色和默认显示样式，减少重复设置操作。",
            "actor_ids": [
                5
            ]
        }
    ]
}

## 示例输出
{
    "business_objects": [
        {
            "business_object_number": "B-001",
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
            "business_object_number": "B-002",
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
            "business_object_number": "B-003",
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
            "business_object_number": "B-004",
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
    ],
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
                    "step_number": "S-001",
                    "step_name": "发起新建便签",
                    "step_description": "便签记录者点击新建便签入口，要求系统创建一个新的独立便签。",
                    "actor_ids": [
                        1
                    ],
                    "step_type": "actorAction",
                    "input_business_object_numbers": [],
                    "output_business_object_numbers": [],
                    "next_steps": [
                        "S-002"
                    ]
                },
                {
                    "step_number": "S-002",
                    "step_name": "生成空白便签",
                    "step_description": "系统按照默认样式生成空白桌面便签，并分配唯一标识。",
                    "actor_ids": [],
                    "step_type": "systemAction",
                    "input_business_object_numbers": [
                        "B-004"
                    ],
                    "output_business_object_numbers": [
                        "B-001"
                    ],
                    "next_steps": [
                        "S-003"
                    ]
                },
                {
                    "step_number": "S-003",
                    "step_name": "输入或修改文字",
                    "step_description": "便签记录者在便签中输入临时灵感、日程、会议要点或生活琐事，也可修改已有内容。",
                    "actor_ids": [
                        1
                    ],
                    "step_type": "actorAction",
                    "input_business_object_numbers": [
                        "B-001"
                    ],
                    "output_business_object_numbers": [
                        "B-001"
                    ],
                    "next_steps": [
                        "S-004"
                    ]
                },
                {
                    "step_number": "S-004",
                    "step_name": "保存便签内容",
                    "step_description": "系统保存便签文字内容和更新时间，并保持便签在桌面显示。",
                    "actor_ids": [],
                    "step_type": "systemAction",
                    "input_business_object_numbers": [
                        "B-001"
                    ],
                    "output_business_object_numbers": [
                        "B-001"
                    ],
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
                    "step_number": "S-001",
                    "step_name": "选择目标便签",
                    "step_description": "便签整理者从桌面上的多个便签中选择需要整理或调整样式的便签。",
                    "actor_ids": [
                        2
                    ],
                    "step_type": "actorAction",
                    "input_business_object_numbers": [
                        "B-001"
                    ],
                    "output_business_object_numbers": [
                        "B-001"
                    ],
                    "next_steps": [
                        "S-002",
                        "S-003",
                        "S-004",
                        "S-005"
                    ]
                },
                {
                    "step_number": "S-002",
                    "step_name": "拖动便签位置",
                    "step_description": "便签整理者将便签拖动到桌面任意目标位置。",
                    "actor_ids": [
                        2
                    ],
                    "step_type": "actorAction",
                    "input_business_object_numbers": [
                        "B-001"
                    ],
                    "output_business_object_numbers": [
                        "B-001"
                    ],
                    "next_steps": [
                        "S-006"
                    ]
                },
                {
                    "step_number": "S-003",
                    "step_name": "设置颜色分类",
                    "step_description": "便签整理者为便签选择颜色，用于区分信息类别、优先级或使用场景。",
                    "actor_ids": [
                        2
                    ],
                    "step_type": "actorAction",
                    "input_business_object_numbers": [
                        "B-001"
                    ],
                    "output_business_object_numbers": [
                        "B-001"
                    ],
                    "next_steps": [
                        "S-006"
                    ]
                },
                {
                    "step_number": "S-004",
                    "step_name": "调整字体样式",
                    "step_description": "便签整理者调整便签文字的字体、字号或相关显示样式。",
                    "actor_ids": [
                        2
                    ],
                    "step_type": "actorAction",
                    "input_business_object_numbers": [
                        "B-001"
                    ],
                    "output_business_object_numbers": [
                        "B-001"
                    ],
                    "next_steps": [
                        "S-006"
                    ]
                },
                {
                    "step_number": "S-005",
                    "step_name": "设置背景透明度",
                    "step_description": "便签整理者调整便签背景透明效果，使便签与桌面环境协调。",
                    "actor_ids": [
                        4
                    ],
                    "step_type": "actorAction",
                    "input_business_object_numbers": [
                        "B-001"
                    ],
                    "output_business_object_numbers": [
                        "B-001"
                    ],
                    "next_steps": [
                        "S-006"
                    ]
                },
                {
                    "step_number": "S-006",
                    "step_name": "保存便签布局与样式",
                    "step_description": "系统保存便签的位置、颜色、字体和透明度设置。",
                    "actor_ids": [],
                    "step_type": "systemAction",
                    "input_business_object_numbers": [
                        "B-001"
                    ],
                    "output_business_object_numbers": [
                        "B-001"
                    ],
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
                    "step_number": "S-001",
                    "step_name": "创建待办事项",
                    "step_description": "待办管理者输入待办任务标题或内容，提交新增任务。",
                    "actor_ids": [
                        3
                    ],
                    "step_type": "actorAction",
                    "input_business_object_numbers": [],
                    "output_business_object_numbers": [
                        "B-002"
                    ],
                    "next_steps": [
                        "S-002"
                    ]
                },
                {
                    "step_number": "S-002",
                    "step_name": "设置截止时间",
                    "step_description": "待办管理者为待办事项设置任务截止时间。",
                    "actor_ids": [
                        3
                    ],
                    "step_type": "actorAction",
                    "input_business_object_numbers": [
                        "B-002"
                    ],
                    "output_business_object_numbers": [
                        "B-002"
                    ],
                    "next_steps": [
                        "S-003"
                    ]
                },
                {
                    "step_number": "S-003",
                    "step_name": "判断是否置顶",
                    "step_description": "系统根据用户操作判断该待办事项是否需要置顶显示。",
                    "actor_ids": [],
                    "step_type": "judgment",
                    "input_business_object_numbers": [
                        "B-002"
                    ],
                    "output_business_object_numbers": [],
                    "next_steps": [
                        "S-004",
                        "S-005"
                    ]
                },
                {
                    "step_number": "S-004",
                    "step_name": "置顶重要事项",
                    "step_description": "待办管理者将重要待办事项设置为置顶显示。",
                    "actor_ids": [
                        3
                    ],
                    "step_type": "actorAction",
                    "input_business_object_numbers": [
                        "B-002"
                    ],
                    "output_business_object_numbers": [
                        "B-002"
                    ],
                    "next_steps": [
                        "S-005"
                    ]
                },
                {
                    "step_number": "S-005",
                    "step_name": "保存待办事项",
                    "step_description": "系统保存待办事项内容、截止时间、置顶状态和初始完成状态。",
                    "actor_ids": [],
                    "step_type": "systemAction",
                    "input_business_object_numbers": [
                        "B-002"
                    ],
                    "output_business_object_numbers": [
                        "B-002"
                    ],
                    "next_steps": [
                        "S-006"
                    ]
                },
                {
                    "step_number": "S-006",
                    "step_name": "标记完成状态",
                    "step_description": "待办管理者在任务完成后将待办事项标记为已完成。",
                    "actor_ids": [
                        3
                    ],
                    "step_type": "actorAction",
                    "input_business_object_numbers": [
                        "B-002"
                    ],
                    "output_business_object_numbers": [
                        "B-002"
                    ],
                    "next_steps": [
                        "S-007"
                    ]
                },
                {
                    "step_number": "S-007",
                    "step_name": "更新任务状态",
                    "step_description": "系统更新待办事项完成状态，并刷新待办清单展示。",
                    "actor_ids": [],
                    "step_type": "systemAction",
                    "input_business_object_numbers": [
                        "B-002"
                    ],
                    "output_business_object_numbers": [
                        "B-002"
                    ],
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
                    "step_number": "S-001",
                    "step_name": "选择显示控制操作",
                    "step_description": "桌面显示控制者选择一键隐藏所有便签或恢复显示便签。",
                    "actor_ids": [
                        4
                    ],
                    "step_type": "actorAction",
                    "input_business_object_numbers": [
                        "B-003"
                    ],
                    "output_business_object_numbers": [],
                    "next_steps": [
                        "S-002"
                    ]
                },
                {
                    "step_number": "S-002",
                    "step_name": "判断控制类型",
                    "step_description": "系统判断用户选择的是隐藏所有便签还是恢复显示便签。",
                    "actor_ids": [],
                    "step_type": "judgment",
                    "input_business_object_numbers": [
                        "B-003"
                    ],
                    "output_business_object_numbers": [],
                    "next_steps": [
                        "S-003",
                        "S-004"
                    ]
                },
                {
                    "step_number": "S-003",
                    "step_name": "隐藏所有便签",
                    "step_description": "系统将所有桌面便签设置为隐藏状态，并更新全局显示控制状态。",
                    "actor_ids": [],
                    "step_type": "systemAction",
                    "input_business_object_numbers": [
                        "B-001",
                        "B-003"
                    ],
                    "output_business_object_numbers": [
                        "B-001",
                        "B-003"
                    ],
                    "next_steps": []
                },
                {
                    "step_number": "S-004",
                    "step_name": "恢复显示便签",
                    "step_description": "系统将已隐藏的便签恢复显示，并更新全局显示控制状态。",
                    "actor_ids": [],
                    "step_type": "systemAction",
                    "input_business_object_numbers": [
                        "B-001",
                        "B-003"
                    ],
                    "output_business_object_numbers": [
                        "B-001",
                        "B-003"
                    ],
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
                19,
                20
            ],
            "flow_steps": [
                {
                    "step_number": "S-001",
                    "step_name": "进入偏好设置",
                    "step_description": "系统偏好设置者打开软件设置入口，进入偏好配置界面。",
                    "actor_ids": [
                        5
                    ],
                    "step_type": "actorAction",
                    "input_business_object_numbers": [
                        "B-004"
                    ],
                    "output_business_object_numbers": [],
                    "next_steps": [
                        "S-002"
                    ]
                },
                {
                    "step_number": "S-002",
                    "step_name": "配置开机常驻",
                    "step_description": "系统偏好设置者选择是否启用开机自动运行并保持常驻。",
                    "actor_ids": [
                        5
                    ],
                    "step_type": "actorAction",
                    "input_business_object_numbers": [
                        "B-004"
                    ],
                    "output_business_object_numbers": [
                        "B-004"
                    ],
                    "next_steps": [
                        "S-003"
                    ]
                },
                {
                    "step_number": "S-003",
                    "step_name": "配置默认便签样式",
                    "step_description": "系统偏好设置者设置默认颜色、默认字体、默认字号和默认透明度。",
                    "actor_ids": [
                        5
                    ],
                    "step_type": "actorAction",
                    "input_business_object_numbers": [
                        "B-004"
                    ],
                    "output_business_object_numbers": [
                        "B-004"
                    ],
                    "next_steps": [
                        "S-004"
                    ]
                },
                {
                    "step_number": "S-004",
                    "step_name": "保存偏好设置",
                    "step_description": "系统保存偏好设置，并将配置用于后续软件启动和新建便签。",
                    "actor_ids": [],
                    "step_type": "systemAction",
                    "input_business_object_numbers": [
                        "B-004"
                    ],
                    "output_business_object_numbers": [
                        "B-004"
                    ],
                    "next_steps": []
                }
            ]
        }
    ]
}
"""