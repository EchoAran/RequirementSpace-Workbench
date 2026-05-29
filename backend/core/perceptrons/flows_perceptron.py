from dataclasses import dataclass
import json
from typing import Dict, List

from backend.core.perceptrons.prompts import flows_perceive_prompt
from backend.core.perceptrons.base_perceptron import BasePerceptron, PerceptronInput
from backend.schemas import FeatureNode, FlowNode


# 为流程感知器定义专属的输入类型
@dataclass
class FlowsPerceptronInput(PerceptronInput):
    user_requirements: str
    features: List[FeatureNode]
    flows: List[FlowNode]

class FlowsPerceptron(BasePerceptron[FlowsPerceptronInput]):
    async def perceive(self, input_data: FlowsPerceptronInput) -> Dict:
        user_requirements_ = input_data.user_requirements

        features_payload = FeatureNode.schema(
            many=True,
            only=("featureId", "featureName", "featureDescription", "actorIds")
        ).dump(node for node in input_data.features if len(node.childrenIds) == 0)      # 筛选出没有孩子的结点，即叶子结点

        features_ = json.dumps(
            {"features": features_payload},
            ensure_ascii=False,
            indent=2
        )

        flows_payload = FlowNode.schema(
            many=True,
            only=(
                "flowId",
                "flowName",
                "flowDescription",
                "featureIds",
                "flowSteps.stepId",
                "flowSteps.stepName",
                "flowSteps.stepDescription",
                "flowSteps.nextStepIds",
            ),
        ).dump(input_data.flows)

        flows_ = json.dumps(
            {"flows": flows_payload,},
            ensure_ascii=False,
            indent=2,
        )

        response = await self._llm_handler.call_llm(
            prompt=flows_perceive_prompt.replace(
                "{{user_requirements}}", user_requirements_).replace(
                "{{features}}", features_).replace(
                "{{flows}}", flows_),
            print_log=True,
        )

        return json.loads(response)

if __name__ == "__main__":
    import asyncio
    from backend.schemas import (
        FlowNode,
        FlowStepNode,
        FlowStepType,
    )

    flows_perceptron = FlowsPerceptron()

    user_requirements = "极简纯净本地音乐播放器，不联网、无会员、无广告，只读取电脑本地音乐文件，支持无损格式 Flac/WAV/MP3 播放，自带歌词本地匹配、音效均衡器、歌单自定义、睡眠定时关闭、全局快捷键切歌，界面清爽轻量化，替代臃肿的主流音乐播放器。"
    test_features: List[FeatureNode] = [
        FeatureNode(
            featureId=1,
            featureName="极简纯净本地音乐播放器",
            featureDescription="系统用于在电脑本地离线播放音乐文件，支持无损与常见音频格式播放，并提供歌词匹配、音效均衡、歌单管理、睡眠定时、全局快捷键和轻量化界面等功能，旨在替代臃肿的主流音乐播放器。",
            actorIds=[1, 2, 3, 4, 5, 6, 7],
            childrenIds=[2, 6, 10, 14, 18, 22, 26]
        ),
        FeatureNode(
            featureId=2,
            featureName="本地音乐播放管理",
            featureDescription="支持读取电脑本地音乐文件并进行播放控制、进度调整和格式播放管理。",
            actorIds=[1],
            childrenIds=[3, 4, 5]
        ),
        FeatureNode(
            featureId=3,
            featureName="扫描与导入本地音乐",
            featureDescription="支持从电脑本地读取、扫描和导入音乐文件，作为播放器的媒体来源。",
            actorIds=[1],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=4,
            featureName="播放控制",
            featureDescription="支持播放、暂停、上一首、下一首和播放进度调整等基础播放操作。",
            actorIds=[1, 6],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=5,
            featureName="音频格式播放",
            featureDescription="支持播放本地无损及常见音频格式文件，包括 Flac、WAV 和 MP3。",
            actorIds=[1],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=6,
            featureName="歌单自定义管理",
            featureDescription="支持用户按个人喜好创建、编辑和维护本地音乐歌单。",
            actorIds=[2, 1],
            childrenIds=[7, 8, 9]
        ),
        FeatureNode(
            featureId=7,
            featureName="新建与删除歌单",
            featureDescription="支持用户创建新的歌单并删除不再需要的歌单。",
            actorIds=[2],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=8,
            featureName="添加或移除歌曲",
            featureDescription="支持用户将本地歌曲添加到歌单中或从歌单中移除。",
            actorIds=[2, 1],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=9,
            featureName="歌单排序与自定义内容",
            featureDescription="支持用户调整歌单内歌曲顺序，并按个人偏好自定义歌单内容。",
            actorIds=[2],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=10,
            featureName="歌词匹配与显示",
            featureDescription="支持本地歌曲歌词自动匹配、显示与同步管理。",
            actorIds=[4],
            childrenIds=[11, 12, 13]
        ),
        FeatureNode(
            featureId=11,
            featureName="本地歌词自动匹配",
            featureDescription="支持根据本地歌曲自动匹配对应歌词文件或歌词内容。",
            actorIds=[4],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=12,
            featureName="歌词显示与同步调整",
            featureDescription="支持在播放界面显示歌词，并调整歌词同步效果以匹配播放进度。",
            actorIds=[4, 1],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=13,
            featureName="歌词关联管理",
            featureDescription="支持用户管理歌词与歌曲的关联结果，便于维护匹配准确性。",
            actorIds=[4],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=14,
            featureName="音效与均衡器设置",
            featureDescription="支持用户根据听感调整音效参数与均衡器配置。",
            actorIds=[3],
            childrenIds=[15, 16, 17]
        ),
        FeatureNode(
            featureId=15,
            featureName="均衡器调节",
            featureDescription="支持用户调整均衡器各频段参数，以优化不同音乐风格的听感。",
            actorIds=[3],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=16,
            featureName="音效参数配置",
            featureDescription="支持用户配置音效相关参数，并保存个人偏好设置。",
            actorIds=[3],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=17,
            featureName="预设音效切换",
            featureDescription="支持用户切换系统提供的预设音效方案。",
            actorIds=[3],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=18,
            featureName="睡眠定时关闭",
            featureDescription="支持设置定时关闭播放器，在指定时间自动停止播放并退出或关闭程序。",
            actorIds=[5],
            childrenIds=[19, 20, 21]
        ),
        FeatureNode(
            featureId=19,
            featureName="设置定时关闭时间",
            featureDescription="支持用户设置播放器在指定时间后自动关闭。",
            actorIds=[5],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=20,
            featureName="取消定时与查看倒计时",
            featureDescription="支持用户取消已设置的定时关闭，并查看剩余倒计时。",
            actorIds=[5],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=21,
            featureName="管理播放结束行为",
            featureDescription="支持用户配置定时结束后播放器的处理方式，如停止播放或关闭程序。",
            actorIds=[5],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=22,
            featureName="全局快捷键控制",
            featureDescription="支持通过系统全局快捷键快速控制音乐播放。",
            actorIds=[6],
            childrenIds=[23, 24, 25]
        ),
        FeatureNode(
            featureId=23,
            featureName="切歌快捷键设置",
            featureDescription="支持用户设置全局切歌快捷键，以便快速控制播放。",
            actorIds=[6],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=24,
            featureName="快捷键播放控制",
            featureDescription="支持通过全局快捷键执行播放、暂停、上一首和下一首操作。",
            actorIds=[6, 1],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=25,
            featureName="快速调节播放状态",
            featureDescription="支持通过快捷键快速调整当前播放状态，提升操作效率。",
            actorIds=[6],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=26,
            featureName="清爽轻量化界面设置",
            featureDescription="支持配置播放器界面风格与显示方式，保持界面简洁、轻量和低干扰。",
            actorIds=[7],
            childrenIds=[27, 28, 29]
        ),
        FeatureNode(
            featureId=27,
            featureName="界面显示样式调整",
            featureDescription="支持用户调整界面显示样式，使播放器保持清爽直观。",
            actorIds=[7],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=28,

            featureName="轻量化布局切换",
            featureDescription="支持用户切换轻量化布局，减少不必要的视觉元素与操作干扰。",
            actorIds=[7],
            childrenIds=[]
        ),
        FeatureNode(
            featureId=29,
            featureName="视觉风格与外观偏好管理",
            featureDescription="支持用户配置播放器视觉风格，满足长期使用中的外观偏好。",
            actorIds=[7],
            childrenIds=[]
        )
    ]
    test_flows = [
        FlowNode(
            flowId=1,
            flowName="本地音乐导入与播放流程",
            flowDescription="用户扫描或导入电脑本地音乐文件，系统识别可播放音频格式并加入音乐库，用户选择歌曲后进行播放控制。",
            featureIds=[1, 2, 3],
            flowSteps=[
                FlowStepNode(
                    stepId=1,
                    stepName="选择音乐导入入口",
                    stepDescription="用户选择扫描本地目录或手动导入音乐文件。",
                    stepType=FlowStepType.ACTOR_ACTION,
                    actorIds=[1],
                    inputBusinessObjectIds=[],
                    outputBusinessObjectIds=[1],
                    nextStepIds=[2],
                ),
                FlowStepNode(
                    stepId=2,
                    stepName="读取本地音乐文件",
                    stepDescription="系统读取用户指定目录或文件，并提取文件路径、文件名、格式和时长等基础信息。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[1],
                    outputBusinessObjectIds=[1],
                    nextStepIds=[3],
                ),
                FlowStepNode(
                    stepId=3,
                    stepName="判断音频格式是否支持",
                    stepDescription="系统判断导入文件是否属于支持的音频格式，如 MP3、WAV 或 Flac。",
                    stepType=FlowStepType.JUDGMENT,
                    actorIds=[],
                    inputBusinessObjectIds=[1],
                    outputBusinessObjectIds=[],
                    nextStepIds=[4, 5],
                ),
                FlowStepNode(
                    stepId=4,
                    stepName="加入音乐库",
                    stepDescription="系统将支持播放的本地音乐文件写入音乐库。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[1],
                    outputBusinessObjectIds=[2],
                    nextStepIds=[6],
                ),
                FlowStepNode(
                    stepId=5,
                    stepName="忽略不支持文件",
                    stepDescription="系统忽略不支持的音频文件，并结束该文件的导入处理。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[1],
                    outputBusinessObjectIds=[],
                    nextStepIds=[],
                ),
                FlowStepNode(
                    stepId=6,
                    stepName="选择歌曲播放",
                    stepDescription="用户从音乐库中选择一首歌曲进行播放。",
                    stepType=FlowStepType.ACTOR_ACTION,
                    actorIds=[1],
                    inputBusinessObjectIds=[2],
                    outputBusinessObjectIds=[3],
                    nextStepIds=[7],
                ),
                FlowStepNode(
                    stepId=7,
                    stepName="执行播放",
                    stepDescription="系统加载用户选择的音乐文件并创建播放会话。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[1, 3],
                    outputBusinessObjectIds=[3],
                    nextStepIds=[8],
                ),
                FlowStepNode(
                    stepId=8,
                    stepName="控制播放状态",
                    stepDescription="用户执行播放、暂停、上一首、下一首或调整播放进度等操作。",
                    stepType=FlowStepType.ACTOR_ACTION,
                    actorIds=[1, 6],
                    inputBusinessObjectIds=[3],
                    outputBusinessObjectIds=[3],
                    nextStepIds=[9],
                ),
                FlowStepNode(
                    stepId=9,
                    stepName="更新播放会话",
                    stepDescription="系统根据用户操作更新当前歌曲、播放状态和播放进度。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[3],
                    outputBusinessObjectIds=[3],
                    nextStepIds=[],
                ),
            ],
        ),
        FlowNode(
            flowId=2,
            flowName="歌单管理流程",
            flowDescription="用户创建或删除歌单，将本地歌曲添加到歌单或从歌单移除，并按照个人偏好调整歌曲顺序。",
            featureIds=[4, 5, 6],
            flowSteps=[
                FlowStepNode(
                    stepId=10,
                    stepName="创建或选择歌单",
                    stepDescription="用户创建新的歌单，或选择已有歌单进行维护。",
                    stepType=FlowStepType.ACTOR_ACTION,
                    actorIds=[2],
                    inputBusinessObjectIds=[4],
                    outputBusinessObjectIds=[4],
                    nextStepIds=[11],
                ),
                FlowStepNode(
                    stepId=11,
                    stepName="保存歌单基础信息",
                    stepDescription="系统保存歌单名称、歌单编号和初始歌曲集合。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[4],
                    outputBusinessObjectIds=[4],
                    nextStepIds=[12],
                ),
                FlowStepNode(
                    stepId=12,
                    stepName="选择歌单操作类型",
                    stepDescription="用户选择添加歌曲、移除歌曲、调整排序或删除歌单。",
                    stepType=FlowStepType.ACTOR_ACTION,
                    actorIds=[2, 1],
                    inputBusinessObjectIds=[2, 4],
                    outputBusinessObjectIds=[],
                    nextStepIds=[13],
                ),
                FlowStepNode(
                    stepId=13,
                    stepName="判断操作类型",
                    stepDescription="系统判断用户当前选择的歌单维护操作。",
                    stepType=FlowStepType.JUDGMENT,
                    actorIds=[],
                    inputBusinessObjectIds=[4],
                    outputBusinessObjectIds=[],
                    nextStepIds=[14, 15, 16, 17],
                ),
                FlowStepNode(
                    stepId=14,
                    stepName="添加歌曲到歌单",
                    stepDescription="系统将用户从音乐库中选择的歌曲加入目标歌单。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[1, 2, 4],
                    outputBusinessObjectIds=[4],
                    nextStepIds=[18],
                ),
                FlowStepNode(
                    stepId=15,
                    stepName="从歌单移除歌曲",
                    stepDescription="系统将用户指定的歌曲从目标歌单中移除。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[4],
                    outputBusinessObjectIds=[4],
                    nextStepIds=[18],
                ),
                FlowStepNode(
                    stepId=16,
                    stepName="调整歌曲顺序",
                    stepDescription="系统根据用户指定的顺序更新歌单内歌曲排序。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[4],
                    outputBusinessObjectIds=[4],
                    nextStepIds=[18],
                ),
                FlowStepNode(
                    stepId=17,
                    stepName="删除歌单",
                    stepDescription="系统删除用户指定的不再需要的歌单。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[4],
                    outputBusinessObjectIds=[],
                    nextStepIds=[],
                ),
                FlowStepNode(
                    stepId=18,
                    stepName="保存歌单变更",
                    stepDescription="系统保存歌单内容和排序变更，供后续播放和管理使用。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[4],
                    outputBusinessObjectIds=[4],
                    nextStepIds=[],
                ),
            ],
        ),
        FlowNode(
            flowId=3,
            flowName="歌词匹配与同步流程",
            flowDescription="系统根据本地歌曲自动匹配歌词，用户查看歌词显示效果，并可调整同步偏移或管理歌词关联关系。",
            featureIds=[7, 8, 9],
            flowSteps=[
                FlowStepNode(
                    stepId=19,
                    stepName="选择需要匹配歌词的歌曲",
                    stepDescription="用户选择一首本地歌曲，触发歌词匹配或歌词显示。",
                    stepType=FlowStepType.ACTOR_ACTION,
                    actorIds=[4, 1],
                    inputBusinessObjectIds=[1],
                    outputBusinessObjectIds=[],
                    nextStepIds=[20],
                ),
                FlowStepNode(
                    stepId=20,
                    stepName="自动查找歌词",
                    stepDescription="系统根据歌曲文件名、歌曲信息或本地歌词目录自动查找对应歌词文件。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[1],
                    outputBusinessObjectIds=[5],
                    nextStepIds=[21],
                ),
                FlowStepNode(
                    stepId=21,
                    stepName="判断歌词是否匹配成功",
                    stepDescription="系统判断是否找到可用歌词，并确认歌词是否可与当前歌曲建立关联。",
                    stepType=FlowStepType.JUDGMENT,
                    actorIds=[],
                    inputBusinessObjectIds=[1, 5],
                    outputBusinessObjectIds=[],
                    nextStepIds=[22, 23],
                ),
                FlowStepNode(
                    stepId=22,
                    stepName="建立歌词关联",
                    stepDescription="系统将匹配到的歌词与当前歌曲建立关联关系。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[1, 5],
                    outputBusinessObjectIds=[6],
                    nextStepIds=[24],
                ),
                FlowStepNode(
                    stepId=23,
                    stepName="手动管理歌词关联",
                    stepDescription="用户手动选择歌词文件或调整歌曲与歌词的关联结果。",
                    stepType=FlowStepType.ACTOR_ACTION,
                    actorIds=[4],
                    inputBusinessObjectIds=[1, 5, 6],
                    outputBusinessObjectIds=[6],
                    nextStepIds=[24],
                ),
                FlowStepNode(
                    stepId=24,
                    stepName="显示歌词",
                    stepDescription="系统在播放界面中按照当前播放进度显示歌词。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[3, 5, 6],
                    outputBusinessObjectIds=[5],
                    nextStepIds=[25],
                ),
                FlowStepNode(
                    stepId=25,
                    stepName="调整歌词同步效果",
                    stepDescription="用户根据播放效果调整歌词时间偏移，使歌词与音乐播放进度一致。",
                    stepType=FlowStepType.ACTOR_ACTION,
                    actorIds=[4, 1],
                    inputBusinessObjectIds=[5],
                    outputBusinessObjectIds=[5],
                    nextStepIds=[26],
                ),
                FlowStepNode(
                    stepId=26,
                    stepName="保存歌词同步设置",
                    stepDescription="系统保存歌词时间偏移和关联结果，供后续播放时复用。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[5, 6],
                    outputBusinessObjectIds=[5, 6],
                    nextStepIds=[],
                ),
            ],
        ),
        FlowNode(
            flowId=4,
            flowName="音效调节流程",
            flowDescription="用户通过预设音效、均衡器和音效参数配置优化音乐播放效果，系统保存并应用个人音效偏好。",
            featureIds=[10, 11, 12],
            flowSteps=[
                FlowStepNode(
                    stepId=27,
                    stepName="打开音效设置",
                    stepDescription="用户进入音效设置界面，准备调整播放效果。",
                    stepType=FlowStepType.ACTOR_ACTION,
                    actorIds=[3],
                    inputBusinessObjectIds=[],
                    outputBusinessObjectIds=[],
                    nextStepIds=[28],
                ),
                FlowStepNode(
                    stepId=28,
                    stepName="选择音效调节方式",
                    stepDescription="用户选择切换预设音效、手动调整均衡器或配置其他音效参数。",
                    stepType=FlowStepType.ACTOR_ACTION,
                    actorIds=[3],
                    inputBusinessObjectIds=[7],
                    outputBusinessObjectIds=[],
                    nextStepIds=[29],
                ),
                FlowStepNode(
                    stepId=29,
                    stepName="判断音效调节方式",
                    stepDescription="系统判断用户选择的是预设音效、均衡器调整还是参数配置。",
                    stepType=FlowStepType.JUDGMENT,
                    actorIds=[],
                    inputBusinessObjectIds=[7],
                    outputBusinessObjectIds=[],
                    nextStepIds=[30, 31, 32],
                ),
                FlowStepNode(
                    stepId=30,
                    stepName="切换预设音效",
                    stepDescription="系统根据用户选择切换到对应的预设音效方案。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[7],
                    outputBusinessObjectIds=[7],
                    nextStepIds=[33],
                ),
                FlowStepNode(
                    stepId=31,
                    stepName="调整均衡器参数",
                    stepDescription="用户调整均衡器各频段参数，形成新的均衡器设置。",
                    stepType=FlowStepType.ACTOR_ACTION,
                    actorIds=[3],
                    inputBusinessObjectIds=[7],
                    outputBusinessObjectIds=[7],
                    nextStepIds=[33],
                ),
                FlowStepNode(
                    stepId=32,
                    stepName="配置音效参数",
                    stepDescription="用户配置其他音效参数，并决定是否保存为个人偏好。",
                    stepType=FlowStepType.ACTOR_ACTION,
                    actorIds=[3],
                    inputBusinessObjectIds=[7],
                    outputBusinessObjectIds=[7],
                    nextStepIds=[33],
                ),
                FlowStepNode(
                    stepId=33,
                    stepName="应用音效配置",
                    stepDescription="系统将新的音效配置应用到当前播放会话。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[3, 7],
                    outputBusinessObjectIds=[3],
                    nextStepIds=[34],
                ),
                FlowStepNode(
                    stepId=34,
                    stepName="保存音效偏好",
                    stepDescription="系统保存用户配置的预设音效、均衡器参数和个人音效偏好。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[7],
                    outputBusinessObjectIds=[7],
                    nextStepIds=[],
                ),
            ],
        ),
        FlowNode(
            flowId=5,
            flowName="睡眠定时关闭流程",
            flowDescription="用户设置定时关闭时间和播放结束行为，系统执行倒计时并在到期后停止播放或关闭程序。",
            featureIds=[13, 14, 15],
            flowSteps=[
                FlowStepNode(
                    stepId=35,
                    stepName="设置定时关闭时间",
                    stepDescription="用户输入定时关闭时长或指定关闭时间。",
                    stepType=FlowStepType.ACTOR_ACTION,
                    actorIds=[5],
                    inputBusinessObjectIds=[],
                    outputBusinessObjectIds=[8],
                    nextStepIds=[36],
                ),
                FlowStepNode(
                    stepId=36,
                    stepName="设置播放结束行为",
                    stepDescription="用户选择倒计时结束后的处理方式，如停止播放或关闭程序。",
                    stepType=FlowStepType.ACTOR_ACTION,
                    actorIds=[5],
                    inputBusinessObjectIds=[8],
                    outputBusinessObjectIds=[8],
                    nextStepIds=[37],
                ),
                FlowStepNode(
                    stepId=37,
                    stepName="启动倒计时",
                    stepDescription="系统保存定时关闭设置并启动倒计时。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[8],
                    outputBusinessObjectIds=[8],
                    nextStepIds=[38],
                ),
                FlowStepNode(
                    stepId=38,
                    stepName="查看或取消倒计时",
                    stepDescription="用户查看剩余倒计时，或取消已经设置的定时关闭。",
                    stepType=FlowStepType.ACTOR_ACTION,
                    actorIds=[5],
                    inputBusinessObjectIds=[8],
                    outputBusinessObjectIds=[8],
                    nextStepIds=[39],
                ),
                FlowStepNode(
                    stepId=39,
                    stepName="判断定时状态",
                    stepDescription="系统判断定时任务是已取消、继续倒计时还是已经到期。",
                    stepType=FlowStepType.JUDGMENT,
                    actorIds=[],
                    inputBusinessObjectIds=[8],
                    outputBusinessObjectIds=[],
                    nextStepIds=[40, 41, 42],
                ),
                FlowStepNode(
                    stepId=40,
                    stepName="取消定时任务",
                    stepDescription="系统取消当前睡眠定时任务，并清除倒计时状态。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[8],
                    outputBusinessObjectIds=[8],
                    nextStepIds=[],
                ),
                FlowStepNode(
                    stepId=41,
                    stepName="继续倒计时",
                    stepDescription="系统继续维护倒计时并更新剩余时间。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[8],
                    outputBusinessObjectIds=[8],
                    nextStepIds=[38],
                ),
                FlowStepNode(
                    stepId=42,
                    stepName="执行结束行为",
                    stepDescription="系统在倒计时结束后按照用户配置停止播放或关闭程序。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[3, 8],
                    outputBusinessObjectIds=[3, 8],
                    nextStepIds=[],
                ),
            ],
        ),
        FlowNode(
            flowId=6,
            flowName="全局快捷键控制流程",
            flowDescription="用户配置全局快捷键，系统校验并保存快捷键绑定，用户通过快捷键快速执行播放控制操作。",
            featureIds=[16, 17, 18],
            flowSteps=[
                FlowStepNode(
                    stepId=43,
                    stepName="进入快捷键设置",
                    stepDescription="用户打开快捷键设置入口，准备配置播放控制快捷键。",
                    stepType=FlowStepType.ACTOR_ACTION,
                    actorIds=[6],
                    inputBusinessObjectIds=[],
                    outputBusinessObjectIds=[],
                    nextStepIds=[44],
                ),
                FlowStepNode(
                    stepId=44,
                    stepName="配置快捷键组合",
                    stepDescription="用户为播放、暂停、上一首和下一首等命令设置快捷键组合。",
                    stepType=FlowStepType.ACTOR_ACTION,
                    actorIds=[6],
                    inputBusinessObjectIds=[],
                    outputBusinessObjectIds=[9],
                    nextStepIds=[45],
                ),
                FlowStepNode(
                    stepId=45,
                    stepName="校验快捷键冲突",
                    stepDescription="系统校验快捷键组合是否为空、重复或与已有快捷键冲突。",
                    stepType=FlowStepType.JUDGMENT,
                    actorIds=[],
                    inputBusinessObjectIds=[9],
                    outputBusinessObjectIds=[],
                    nextStepIds=[46, 47],
                ),
                FlowStepNode(
                    stepId=46,
                    stepName="提示重新设置",
                    stepDescription="系统提示快捷键不可用，要求用户重新设置快捷键组合。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[9],
                    outputBusinessObjectIds=[],
                    nextStepIds=[44],
                ),
                FlowStepNode(
                    stepId=47,
                    stepName="保存快捷键配置",
                    stepDescription="系统保存有效的快捷键配置并启用全局快捷键监听。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[9],
                    outputBusinessObjectIds=[9],
                    nextStepIds=[48],
                ),
                FlowStepNode(
                    stepId=48,
                    stepName="触发快捷键",
                    stepDescription="用户在任意场景下按下已配置的全局快捷键。",
                    stepType=FlowStepType.ACTOR_ACTION,
                    actorIds=[6, 1],
                    inputBusinessObjectIds=[9],
                    outputBusinessObjectIds=[],
                    nextStepIds=[49],
                ),
                FlowStepNode(
                    stepId=49,
                    stepName="识别快捷键命令",
                    stepDescription="系统根据快捷键配置识别用户触发的播放控制命令。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[9],
                    outputBusinessObjectIds=[],
                    nextStepIds=[50],
                ),
                FlowStepNode(
                    stepId=50,
                    stepName="执行播放控制",
                    stepDescription="系统执行对应的播放、暂停、上一首、下一首或快速调节播放状态操作。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[3, 9],
                    outputBusinessObjectIds=[3],
                    nextStepIds=[],
                ),
            ],
        ),
        FlowNode(
            flowId=7,
            flowName="界面偏好设置流程",
            flowDescription="用户调整播放器界面显示样式、轻量化布局和视觉风格，系统保存并应用界面偏好。",
            featureIds=[19, 20, 21],
            flowSteps=[
                FlowStepNode(
                    stepId=51,
                    stepName="进入界面设置",
                    stepDescription="用户进入播放器界面设置入口。",
                    stepType=FlowStepType.ACTOR_ACTION,
                    actorIds=[7],
                    inputBusinessObjectIds=[],
                    outputBusinessObjectIds=[],
                    nextStepIds=[52],
                ),
                FlowStepNode(
                    stepId=52,
                    stepName="调整界面显示样式",
                    stepDescription="用户调整界面显示样式、视觉风格或是否显示额外视觉元素。",
                    stepType=FlowStepType.ACTOR_ACTION,
                    actorIds=[7],
                    inputBusinessObjectIds=[10],
                    outputBusinessObjectIds=[10],
                    nextStepIds=[53],
                ),
                FlowStepNode(
                    stepId=53,
                    stepName="选择布局模式",
                    stepDescription="用户选择标准布局或轻量化布局，以减少操作干扰。",
                    stepType=FlowStepType.ACTOR_ACTION,
                    actorIds=[7],
                    inputBusinessObjectIds=[10],
                    outputBusinessObjectIds=[10],
                    nextStepIds=[54],
                ),
                FlowStepNode(
                    stepId=54,
                    stepName="应用界面偏好",
                    stepDescription="系统根据用户选择立即调整界面布局、视觉风格和显示元素。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[10],
                    outputBusinessObjectIds=[10],
                    nextStepIds=[55],
                ),
                FlowStepNode(
                    stepId=55,
                    stepName="保存界面设置",
                    stepDescription="系统保存用户界面偏好，供后续启动播放器时自动加载。",
                    stepType=FlowStepType.SYSTEM_ACTION,
                    actorIds=[],
                    inputBusinessObjectIds=[10],
                    outputBusinessObjectIds=[10],
                    nextStepIds=[],
                ),
            ],
        ),
    ]

    async def main():
        flows_perceptron_result = await flows_perceptron.perceive(
            FlowsPerceptronInput(user_requirements, test_features, test_flows)
        )
    asyncio.run(main())

    result = """
{
    "perception_description": "需要补充“播放器启动与偏好恢复流程”。原因是当前已有流程覆盖了导入播放、歌单管理、歌词、音效、睡眠定时、全局快捷键和界面偏好的配置与使用，但缺少一个从“启动应用”到“恢复用户习惯状态”的整体运行流程：例如读取已保存的音乐库、音效设置、界面布局、快捷键绑定、歌词同步偏移以及上次播放状态（如是否继续上次播放、默认打开哪个歌单/页面）等。对一个强调极简、清爽、替代主流播放器的本地播放器来说，这种“启动即就绪”的能力是核心体验的一部分，仅靠单独的设置流程无法体现其在应用启动时如何被应用。补充方式是新增一个“播放器启动与会话恢复流程”，不引入新 feature，而是关联已有音效、界面偏好、快捷键、歌词匹配、音乐导入等相关 feature：步骤可包括（1）启动应用并加载基础配置；（2）读取已保存音乐库索引（如不存在则提示用户扫描本地音乐）；（3）加载用户界面偏好和布局（标准/轻量、视觉风格）；（4）加载音效配置并应用到默认输出；（5）注册全局快捷键；（6）恢复歌词关联与同步偏移；（7）根据用户设置决定是否自动恢复上次播放会话（歌曲、播放位置或仅停留在暂停状态）。通过该启动流程，将零散的设置/控制能力在应用生命周期入口处整合起来，确保系统行为与“极简纯净”“开箱即用”的目标体验一致。"
}
"""
