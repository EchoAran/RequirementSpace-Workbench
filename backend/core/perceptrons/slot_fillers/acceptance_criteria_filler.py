from dataclasses import dataclass
import json
from typing import Dict, List

from backend.core.perceptrons.slot_fillers.prompts.acceptance_criteria_fill_agent import acceptance_criteria_fill_prompt
from backend.core.perceptrons.slot_fillers.base_filler import BaseFiller, FillerInput
from backend.schemas import ActorNode, FeatureNode, PerceptionSlot, ScenarioNode


# 为成功标准补充器定义专属的输入类型
@dataclass
class AcceptanceCriteriaFillerInput(FillerInput):
    user_requirements: str
    actor: ActorNode
    feature: FeatureNode
    scenarios: List[ScenarioNode]
    perception_description: PerceptionSlot
    user_feedback: str | None = None


class AcceptanceCriteriaFiller(BaseFiller[AcceptanceCriteriaFillerInput]):
    async def fill(
        self,
        input_data: AcceptanceCriteriaFillerInput,
    ) -> Dict:
        user_requirements_ = input_data.user_requirements

        actor_ = ActorNode.schema(
            only=("actorName", "actorDescription"),
        ).dumps(
            input_data.actor,
            indent=2,
            ensure_ascii=False,
        )

        feature_ = FeatureNode.schema(
            only=("featureName", "featureDescription"),
        ).dumps(
            input_data.feature,
            indent=2,
            ensure_ascii=False,
        )

        scenarios_ = json.dumps(
            {
                "scenarios": self._build_scenarios_payload(
                    input_data.scenarios
                ),
            },
            ensure_ascii=False,
            indent=2,
        )

        perception_description_payload = PerceptionSlot.schema(
            only=("perceptionDescription",)
        ).dump(input_data.perception_description)

        perception_description_ = json.dumps(
            perception_description_payload,
            ensure_ascii=False,
            indent=2,
        )

        response = await self._llm_handler.call_llm(
            prompt=acceptance_criteria_fill_prompt.replace(
                "{{user_requirements}}", user_requirements_,).replace(
                "{{actor}}", actor_,).replace(
                "{{feature}}", feature_,).replace(
                "{{scenarios}}", scenarios_,).replace(
                "{{perception_description}}", perception_description_,
            ),
            query=input_data.user_feedback,
            print_log=True,
        )

        return json.loads(response)

    @staticmethod
    def _build_scenarios_payload(
        scenarios: List[ScenarioNode],
    ) -> list[dict]:
        return [
            {
                "scenario_id": scenario.scenarioId,
                "scenario_name": scenario.scenarioName,
                "scenario_content": scenario.scenarioContent,
                "acceptance_criteria": [
                    {
                        "criterion_id": criterion.criterionId,
                        "criterion_content": criterion.criterionContent,
                    }
                    for criterion in scenario.acceptanceCriteria
                ],
            }
            for scenario in scenarios
        ]


if __name__ == "__main__":
    import asyncio
    from backend.schemas import (
        AcceptanceCriterionNode,
        PerceptionKindType,
    )

    acceptance_criteria_filler = AcceptanceCriteriaFiller()

    user_requirements = "极简纯净本地音乐播放器，不联网、无会员、无广告，只读取电脑本地音乐文件，支持无损格式 Flac/WAV/MP3 播放，自带歌词本地匹配、音效均衡器、歌单自定义、睡眠定时关闭、全局快捷键切歌，界面清爽轻量化，替代臃肿的主流音乐播放器。"

    test_actor = ActorNode(
        actorId=1,
        actorName="本地音乐听众",
        actorDescription="本地音乐听众是指在需要播放和聆听电脑本地音乐文件的场景下，与音乐播放器发生交互，并可执行导入或扫描本地音乐、播放暂停、切换上一首下一首、调整播放进度、管理播放列表和选择音频格式进行播放等操作的用户角色。",
    )

    test_feature = FeatureNode(
        featureId=1,
        featureName="扫描与导入本地音乐",
        featureDescription="支持从电脑本地读取、扫描和导入音乐文件，作为播放器的媒体来源。",
        actorIds=[1],
        childrenIds=[],  # 无子功能，为叶子节点
    )

    test_scenarios: List[ScenarioNode] = [
        ScenarioNode(
            scenarioId=1,
            scenarioName="扫描本地音乐目录",
            scenarioContent="As a 本地音乐听众, I want to 扫描电脑中的本地音乐目录, So that 我可以一次性将所有本地音乐文件加入播放器作为播放来源",
            featureId=1,
            actorId=1,
            acceptanceCriteria=[
                AcceptanceCriterionNode(
                    criterionId=1,
                    criterionContent="Given 本地音乐听众正在使用极简本地音乐播放器且尚未导入任何音乐文件，When 本地音乐听众选择“扫描本地音乐目录”并指定一个或多个本地目录路径，Then 系统应开始遍历所选目录及其子目录中的文件以查找可识别的音乐文件。",
                )
            ],
        ),
        ScenarioNode(
            scenarioId=2,
            scenarioName="导入指定本地音乐文件",
            scenarioContent="As a 本地音乐听众, I want to 从本地磁盘中手动选择并导入指定音乐文件或文件夹, So that 我可以精确控制哪些音乐加入播放器库",
            featureId=1,
            actorId=1,
            acceptanceCriteria=[
                AcceptanceCriterionNode(
                    criterionId=2,
                    criterionContent="Given 本地音乐听众正在使用极简本地音乐播放器，When 本地音乐听众在应用中选择“导入文件/文件夹”并通过系统文件选择器手动勾选一个或多个音乐文件，Then 系统应仅对被选择的文件执行导入操作而不扫描其他未选中文件。",
                )
            ],
        ),
        ScenarioNode(
            scenarioId=3,
            scenarioName="支持多种无损与常见格式导入",
            scenarioContent="As a 本地音乐听众, I want to 在扫描与导入时支持 Flac/WAV/MP3 等格式, So that 我可以无缝播放自己本地收藏的无损与有损音乐",
            featureId=1,
            actorId=1,
            acceptanceCriteria=[
                AcceptanceCriterionNode(
                    criterionId=3,
                    criterionContent="Given 本地音乐听众正在使用播放器执行扫描或导入操作，When 系统遍历本地文件时遇到扩展名为 .flac、.wav、.mp3 的文件，Then 系统应将这些文件识别为可支持的音乐文件并纳入导入范围。",
                )
            ],
        ),
        ScenarioNode(
            scenarioId=4,
            scenarioName="读取并展示本地音乐信息",
            scenarioContent="As a 本地音乐听众, I want to 在扫描与导入时自动读取歌曲名称、专辑、歌手等标签信息, So that 我可以在播放器中清晰地识别和管理已导入的歌曲",
            featureId=1,
            actorId=1,
            acceptanceCriteria=[
                AcceptanceCriterionNode(
                    criterionId=4,
                    criterionContent="Given 本地音乐听众正在执行扫描或导入本地音乐文件操作，When 系统成功识别某个音乐文件，Then 系统应尝试读取该文件中包含的常见标签信息，如歌曲标题、专辑名称、歌手、艺术家、曲目号和时长。",
                )
            ],
        ),
        ScenarioNode(
            scenarioId=5,
            scenarioName="建立纯本地音乐媒体库",
            scenarioContent="As a 本地音乐听众, I want to 将扫描或导入的音乐文件构建成本地媒体库且不依赖网络, So that 我可以在一个纯本地、无广告、无账号登录的环境中播放音乐",
            featureId=1,
            actorId=1,
            acceptanceCriteria=[
                AcceptanceCriterionNode(
                    criterionId=5,
                    criterionContent="Given 本地音乐听众已经完成本地音乐扫描或导入操作，When 系统写入媒体库数据，Then 系统应把识别到的音乐文件及其基础标签信息保存在本地媒体库中。",
                )
            ],
        ),
        ScenarioNode(
            scenarioId=6,
            scenarioName="更新本地音乐库",
            scenarioContent="As a 本地音乐听众, I want to 重新扫描或增量扫描本地音乐目录, So that 我在新增或删除本地音乐文件后可以快速更新播放器中的歌曲列表",
            featureId=1,
            actorId=1,
            acceptanceCriteria=[
                AcceptanceCriterionNode(
                    criterionId=6,
                    criterionContent="Given 本地音乐听众已经导入过一个或多个本地音乐目录，When 本地音乐听众执行重新扫描或增量扫描操作，Then 系统应检查已配置目录中的新增、删除或移动的音乐文件。",
                )
            ],
        ),
    ]

    test_perception_slot = PerceptionSlot(
        perceptionSlotId=1,
        perceptionKind=PerceptionKindType.ACCEPTANCE_CRITERION,
        perceptionDescription="需要补充成功标准。原因是当前每个场景只覆盖了一个主路径断言，但缺少对导入结果写入、重复文件跳过、无效文件处理、扫描进度反馈、纯本地运行、不联网约束、标签缺失兜底以及本地库更新后移除失效记录等关键行为的验证。补充方式是围绕 scenario_id 1 到 6 分别新增成功标准，覆盖扫描完成后的批量写入、手动导入的重复处理、损坏文件跳过、多格式文件展示、媒体库离线播放约束、重新扫描后的歌曲列表更新与失效文件清理。",
    )

    async def main():
        await acceptance_criteria_filler.fill(
            AcceptanceCriteriaFillerInput(
                user_requirements,
                test_actor,
                test_feature,
                test_scenarios,
                test_perception_slot,
            )
        )

    asyncio.run(main())

    acceptance_criteria_filler_result = """
{
  "scenario_acceptance_criteria": [
    {
      "scenario_id": 1,
      "acceptance_criteria": [
        "Given 本地音乐听众已选择一个或多个本地音乐目录进行扫描，且系统已开始遍历文件，When 系统完成对所选目录及其子目录的扫描，Then 系统应仅将识别为支持格式的音乐文件批量写入本地媒体库并可在歌曲列表中被看到。",
        "Given 本地音乐听众正在扫描本地音乐目录，When 系统在遍历过程中遇到损坏或无法读取的音乐文件，Then 系统应跳过这些文件、记录失败原因并在扫描结果中以可视方式提示失败文件数量。",
        "Given 本地音乐听众正在扫描本地音乐目录，When 扫描过程持续一定时间，Then 系统应通过进度条或百分比等方式实时展示扫描进度并在扫描完成后更新为完成状态。"
      ]
    },
    {
      "scenario_id": 2,
      "acceptance_criteria": [
        "Given 本地音乐听众通过“导入文件/文件夹”选择了一个或多个音乐文件，且这些文件中部分已存在于媒体库，When 系统执行导入操作，Then 系统应跳过媒体库中已存在的文件记录且不产生重复歌曲条目。",
        "Given 本地音乐听众通过“导入文件/文件夹”选择了包含非音乐文件的文件夹，When 系统执行导入操作，Then 系统应仅导入支持格式的音乐文件并忽略非音乐文件且不在媒体库中生成无效记录。"
      ]
    },
    {
      "scenario_id": 3,
      "acceptance_criteria": [
        "Given 本地音乐听众正在执行扫描或导入操作，When 系统遍历到不在支持列表中的音频扩展名文件（如 .aac、.ogg 等），Then 系统应忽略这些文件并在扫描完成后通过摘要信息说明有若干不受支持格式未被导入。",
        "Given 本地音乐听众完成对包含 .flac、.wav、.mp3 混合文件的目录的扫描或导入，When 本地音乐听众打开播放器中对应的歌曲列表，Then 系统应展示所有成功导入的 .flac、.wav、.mp3 文件，并保证它们均可被选择播放。"
      ]
    },
    {
      "scenario_id": 4,
      "acceptance_criteria": [
        "Given 系统在扫描或导入过程中尝试读取音乐文件的标签信息，When 某个音乐文件缺失部分标签字段（例如缺少专辑或歌手），Then 系统应使用文件名或目录名作为兜底显示信息并保证该歌曲仍可在列表中被识别与播放。",
        "Given 系统已成功读取音乐文件的标签信息，When 本地音乐听众在播放器的歌曲列表中查看该歌曲，Then 系统应以结构化方式展示歌曲标题、专辑、歌手和时长等基础信息并与媒体库中的记录保持一致。"
      ]
    },
    {
      "scenario_id": 5,
      "acceptance_criteria": [
        "Given 本地音乐听众已完成本地音乐扫描或导入并建立媒体库，When 本地音乐听众播放媒体库中的歌曲，Then 系统应在完全离线、不发起任何网络连接请求的情况下完成歌曲播放。",
        "Given 本地音乐听众已建立本地媒体库，When 本地音乐听众重新打开播放器应用，Then 系统应从本地存储中加载媒体库数据并在无账号登录、无广告展示的前提下恢复上次的歌曲列表。"
      ]
    },
    {
      "scenario_id": 6,
      "acceptance_criteria": [
        "Given 本地音乐听众已导入过一个或多个本地音乐目录并建立媒体库，When 本地音乐听众在文件系统中新增了音乐文件后执行增量扫描，Then 系统应将新文件添加到媒体库并在歌曲列表中可见且可播放。",
        "Given 本地音乐听众已导入过一个或多个本地音乐目录并建立媒体库，When 本地音乐听众从文件系统中删除或移动了部分已导入的音乐文件后执行重新扫描，Then 系统应将这些不再存在于配置目录中的文件从媒体库中标记为失效或移除，使歌曲列表与实际文件状态保持一致。"
      ]
    }
  ]
}
"""
