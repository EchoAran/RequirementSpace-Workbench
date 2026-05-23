from dataclasses import dataclass
import json
from typing import Dict, List

from backend.core.generators.prompts import scopes_generate_prompt
from backend.core.generators.base_generator import BaseGenerator, GenerateInput
from backend.schemas import FeatureNode

# 为范围生成器定义专属的输入类型
@dataclass
class ScopesGeneratorInput(GenerateInput):
    user_requirements: str
    features: List[FeatureNode]
    user_feedback: str | None = None

class ScopesGenerator(BaseGenerator[ScopesGeneratorInput]):
    async def generate(self, input_data: ScopesGeneratorInput) -> Dict:
        user_requirements_ = input_data.user_requirements
        feedback = input_data.user_feedback or ""

        features_payload = FeatureNode.schema(
            many=True,
            only=("featureId", "featureName", "featureDescription")
        ).dump(node for node in input_data.features if len(node.childrenIds) == 0)      # 筛选出没有孩子的结点，即叶子结点

        features_ = json.dumps(
            {"features": features_payload},
            ensure_ascii=False,
            indent=2
        )

        response = await self._llm_handler.call_llm(
            prompt=scopes_generate_prompt.replace(
                "{{user_requirements}}", f"{user_requirements_}").replace(
                "{{features}}", f"{features_}"
            ),
            query=feedback,
            print_log=False,
        )
        return json.loads(response)

if __name__ == "__main__":
    import asyncio
    from backend.schemas import FeatureNode
    scopes_generator = ScopesGenerator()

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

    async def main():
        await scopes_generator.generate(
            ScopesGeneratorInput(user_requirements, test_features)
         )
    asyncio.run(main())

    scopes_generator_result = """
{
  "scopes": [
    {
      "feature_id": 3,
      "scope": "CURRENT",
      "reasons": "本地扫描导入是“只读取电脑本地音乐文件”的前置能力，没有该能力播放器无法使用，是最核心基础。"
    },
    {
      "feature_id": 4,
      "scope": "CURRENT",
      "reasons": "播放/暂停/切歌/进度调整是任何播放器的基础交互，是全局快捷键等能力的依托，必须首期完成。"
    },
    {
      "feature_id": 5,
      "scope": "CURRENT",
      "reasons": "需求明确要求支持 Flac/WAV/MP3 无损及常见格式播放，该能力直接决定产品是否满足“替代臃肿主流播放器”的核心诉求。"
    },
    {
      "feature_id": 7,
      "scope": "CURRENT",
      "reasons": "歌单自定义是需求显式提出的核心能力，“新建与删除歌单”是实现自定义歌单的基础，首期必须具备。"
    },
    {
      "feature_id": 8,
      "scope": "CURRENT",
      "reasons": "歌单自定义依赖对歌曲的添加/移除操作，否则歌单无法被实际使用和管理，属于歌单管理的核心组成。"
    },
    {
      "feature_id": 9,
      "scope": "POSTPONED",
      "reasons": "歌单排序与更细粒度的自定义提升管理体验，但在首期只要支持创建/删除歌单与添加/移除歌曲即可形成基本价值，可后续优化。"
    },
    {
      "feature_id": 11,
      "scope": "CURRENT",
      "reasons": "需求强调“自带歌词本地匹配”，本地自动匹配是关键卖点之一，直接影响与传统播放器差异化，应纳入首期。"
    },
    {
      "feature_id": 12,
      "scope": "CURRENT",
      "reasons": "歌词显示是歌词功能的直接体现，且简单同步调整用于保证基础使用可用度，与本地匹配一起构成完整歌词体验，应本期实现。"
    },
    {
      "feature_id": 13,
      "scope": "POSTPONED",
      "reasons": "歌词关联管理是专业用户的精细维护能力，非首要刚需，核心价值在“自动匹配+显示”，可在基础稳定后迭代。"
    },
    {
      "feature_id": 15,
      "scope": "CURRENT",
      "reasons": "需求明确点出“音效均衡器”，均衡器调节是该诉求的核心功能，属于主卖点之一，应在首期实现。"
    },
    {
      "feature_id": 16,
      "scope": "POSTPONED",
      "reasons": "更丰富的音效参数配置与预设偏向进阶用户和音色微调，超出“极简纯净”的首期最低可用范围，可后置。"
    },
    {
      "feature_id": 17,
      "scope": "POSTPONED",
      "reasons": "预设音效切换属于均衡器的增强体验，帮助快速切换风格，但非满足基本需求所必需，可在核心播放和简单均衡器稳定后迭代。"
    },
    {
      "feature_id": 19,
      "scope": "CURRENT",
      "reasons": "“睡眠定时关闭”是用户明确需求，设置定时关闭是实现该场景的核心步骤，应在首期支持。"
    },
    {
      "feature_id": 20,
      "scope": "POSTPONED",
      "reasons": "取消定时与查看倒计时提升可控性和可见性，但在极简首期中，先支持基础定时关闭即可形成完整场景，该功能可延后。"
    },
    {
      "feature_id": 21,
      "scope": "POSTPONED",
      "reasons": "细化定时结束后的行为（停止播放/关闭程序）属于高级配置，首期只提供一种简单行为即可满足睡眠关机基本需求，此项可后续增强。"
    },
    {
      "feature_id": 23,
      "scope": "CURRENT",
      "reasons": "“全局快捷键切歌”是需求中明确提到的功能，首期至少要支持设置切歌相关全局快捷键，是差异化体验点之一。"
    },
    {
      "feature_id": 24,
      "scope": "CURRENT",
      "reasons": "全局快捷键执行播放/暂停/上一首/下一首直接映射需求中的“全局快捷键切歌”，属于核心使用场景，应在首期落地。"
    },
    {
      "feature_id": 25,
      "scope": "POSTPONED",
      "reasons": "更多维度的播放状态快速调整属于效率与高级体验优化，在已有常规控件和基本快捷键后，价值边际降低，可后置。"
    },
    {
      "feature_id": 27,
      "scope": "CURRENT",
      "reasons": "用户强调“界面清爽轻量化”，基础的界面样式调整能力有助于减少干扰、控制信息密度，是与产品定位强相关的能力，应首期支持基础版本。"
    },
    {
      "feature_id": 28,
      "scope": "CURRENT",
      "reasons": "轻量化布局切换直接体现“极简纯净、轻量化”的核心定位，帮助用户避免复杂视图和多余元素，是本产品与传统播放器的重要区别之一。"
    },
    {
      "feature_id": 29,
      "scope": "POSTPONED",
      "reasons": "更丰富的视觉风格与外观偏好管理属于个性化与美化需求，会增加设置复杂度，与“极简”首版目标有一定冲突，可留待用户规模扩大后再做。"
    }
  ]
}
"""