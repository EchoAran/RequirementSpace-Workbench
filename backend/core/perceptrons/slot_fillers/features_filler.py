from dataclasses import dataclass
import json
from typing import Dict, List

from backend.core.perceptrons.slot_fillers.prompts.features_fill_agent import features_fill_prompt
from backend.core.perceptrons.slot_fillers.base_filler import BaseFiller, FillerInput
from backend.schemas import PerceptionSlot, FeatureNode


# 为功能补充器定义专属的输入类型
@dataclass
class FeaturesFillerInput(FillerInput):
    user_requirements: str
    features: List[FeatureNode]
    perception_description: PerceptionSlot
    user_feedback: str | None = None

class FeaturesFiller(BaseFiller[FeaturesFillerInput]):
    async def fill(self, input_data: FeaturesFillerInput) -> Dict:
        user_requirements_ = input_data.user_requirements

        features_payload = FeatureNode.schema(
            many=True,
            only=("featureId", "featureName", "featureDescription", "childrenIds")
        ).dump(input_data.features)

        features_ = json.dumps(
            {"features": features_payload},
            ensure_ascii=False,
            indent=2
        )

        perception_description_payload = PerceptionSlot.schema(
            only=("perceptionKind", "perceptionDescription")
        ).dump(input_data.perception_description)
        perception_description_ = json.dumps(
            perception_description_payload,
            ensure_ascii=False,
            indent=2,
        )

        response = await self._llm_handler.call_llm(
            prompt=features_fill_prompt.replace(
                "{{user_requirements}}", f"{user_requirements_}").replace(
                "{{features}}", f"{features_}").replace(
                "{{perception_description}}", f"{perception_description_}"
            ),
            query=input_data.user_feedback,
            print_log=False,
        )
        return json.loads(response)

if __name__ == "__main__":
    import asyncio
    from backend.schemas import FeatureNode, PerceptionSlot, PerceptionKindType

    features_filler = FeaturesFiller()

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
            featureDescription="支持从电脑本地读取、扫描 and 导入音乐文件，作为播放器的媒体来源。",
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
        )
    ]
    test_perception_slot = PerceptionSlot(
        perceptionSlotId = 1,
        perceptionKind = PerceptionKindType.FEATURE_BRANCH,
        perceptionDescription = "需要补充“系统全局功能与个性化设置”功能分支。原因是用户总需求中明确提到：轻量化界面、睡眠定时、全局快捷键等整体行为与使用偏好相关的能力，目前功能树只覆盖到本地音乐播放、歌单管理、歌词匹配等核心播放功能，但缺失这些面向“播放器整体使用体验”的系统级能力。补充方式：在根节点“极简纯净本地音乐播放器”（feature_id: 1）下新增一个子功能分支，例如“系统全局功能与设置”，其下再细化新增叶子功能，如：（1）“睡眠定时控制”——支持设置在指定时间或当前曲目/播放队列结束后自动停止播放并可选择退出程序；（2）“全局快捷键管理”——支持定义/启用系统级快捷键，用于在窗口不激活时控制播放/暂停、上一首、下一首、音量调整等；（3）“轻量化界面与资源占用控制”——定义如简洁主题、最小化到托盘、减少额外组件加载等策略，以保证软件轻量运行。这样可以使功能树覆盖需求描述中“睡眠定时”“全局快捷键”“轻量化界面”等非播放本身但关键的使用体验需求。"
    )
    async def main():
         await features_filler.fill(
            FeaturesFillerInput(user_requirements, test_features, test_perception_slot)
        )
    asyncio.run(main())

    features_filler_result = """
{
  "features": [
    {
      "feature_id": 14,
      "feature_name": "系统全局功能与个性化设置",
      "feature_description": "支持配置播放器整体运行方式和使用偏好，包括睡眠定时、全局快捷键和界面轻量化相关设置，以提升本地离线听歌体验。",
      "children_ids": [15, 16, 17],
      "parent_id": 1
    },
    {
      "feature_id": 15,
      "feature_name": "睡眠定时控制",
      "feature_description": "支持用户设置在指定时间、当前歌曲结束或当前播放队列结束后自动停止播放，并可选择同时关闭应用，适用于睡前听歌等场景。",
      "children_ids": [],
      "parent_id": 14
    },
    {
      "feature_id": 16,
      "feature_name": "全局快捷键管理",
      "feature_description": "支持用户在播放器窗口未激活或最小化到托盘时，仍可通过系统级快捷键控制播放/暂停、上一首、下一首、音量增减和静音等操作，并可根据个人习惯自定义或启用/关闭快捷键。",
      "children_ids": [],
      "parent_id": 14
    },
    {
      "feature_id": 17,
      "feature_name": "轻量化界面与资源占用控制",
      "feature_description": "支持简洁主题样式、最小化到系统托盘、关闭多余视觉效果或附加模块，并通过限制后台常驻组件和无用扫描频率等方式控制资源占用，保持界面清爽和运行轻量。",
      "children_ids": [],
      "parent_id": 14
    }
  ]
}
"""
