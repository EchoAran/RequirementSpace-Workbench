from dataclasses import dataclass
import json
from typing import Dict, List

from backend.core.perceptrons.prompts import acceptance_criteria_perceive_prompt
from backend.core.perceptrons.base_perceptron import BasePerceptron, PerceptronInput
from backend.schemas import ActorNode, FeatureNode, ScenarioNode


# 为成功标准感知器定义专属的输入类型
@dataclass
class AcceptanceCriteriaPerceptronInput(PerceptronInput):
    user_requirements: str
    actor: ActorNode
    feature: FeatureNode
    scenarios: List[ScenarioNode]


class AcceptanceCriteriaPerceptron(
    BasePerceptron[AcceptanceCriteriaPerceptronInput]
):
    async def perceive(
        self,
        input_data: AcceptanceCriteriaPerceptronInput,
    ) -> Dict:
        user_requirements_ = input_data.user_requirements

        actor_ = ActorNode.schema(
            only=("actorName", "actorDescription"),
        ).dumps(
            input_data.actor,
            ensure_ascii=False,
            indent=2,
        )

        feature_ = FeatureNode.schema(
            only=("featureName", "featureDescription"),
        ).dumps(
            input_data.feature,
            ensure_ascii=False,
            indent=2,
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

        response = await self._llm_handler.call_llm(
            prompt=acceptance_criteria_perceive_prompt.replace(
                "{{user_requirements}}", user_requirements_).replace(
                "{{actor}}", actor_).replace(
                "{{feature}}", feature_).replace(
                "{{scenarios}}", scenarios_
            ),
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
    from backend.schemas import AcceptanceCriterionNode

    acceptance_criteria_perceptron = AcceptanceCriteriaPerceptron()

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

    async def main():
        await acceptance_criteria_perceptron.perceive(
            AcceptanceCriteriaPerceptronInput(
                user_requirements,
                test_actor,
                test_feature,
                test_scenarios,
            )
        )

    asyncio.run(main())

    acceptance_criteria_perceptron_result = """
{
  "perception_description": "需要补充多个场景的成功标准。当前各场景的成功标准大多只覆盖“开始操作/识别文件”的主路径，没有覆盖导入结果的可见反馈、重复文件与不支持格式的处理、扫描/导入过程中的异常与边界条件、媒体库的状态变化细节以及用户对纯本地/不联网特性的感知。具体建议如下：\n1）补充场景1“扫描本地音乐目录”的成功标准：\n- 需要验证扫描完成后的结果反馈（扫描到多少首、多少失败）、扫描进度或状态（进行中/完成/被取消）、以及空目录或无可识别音乐文件时的反馈。否则无法确认用户是否知道扫描已完成、是否成功；也无法保证对边界条件（空目录）有合理处理。\n- 补充对不支持的文件格式和损坏文件的处理（略过并记录或提示），以及权限不足/路径不存在时的异常反馈。\n- 可新增若干 Given-When-Then，例如：扫描目录为空/无音乐文件时显示“未找到音乐”；遇到不支持格式文件时不导入并可在结果中显示“X个文件未导入”；访问目录失败时给出错误提示。\n2）补充场景2“导入指定本地音乐文件”的成功标准：\n- 当前只说明“仅导入勾选文件”，缺少导入结束后的用户可见结果（这些歌曲要出现在播放列表或媒体库视图中），也缺少对重复导入的处理约束（是否去重、不产生多条重复记录）。\n- 建议增加成功标准，验证：勾选文件导入后能在媒体库/当前列表中看到，重复导入同一文件不会产生重复条目（或有明确策略说明），导入过程失败时给出原因（例如文件损坏、无权限）。\n3）补充场景3“支持多种无损与常见格式导入”的成功标准：\n- 当前只说明识别 .flac/.wav/.mp3 为可支持格式，但没有验证其他扩展名的排除策略，也未说明当文件扩展名与实际内容不匹配或文件损坏时如何处理。\n- 建议新增成功标准，明确：非支持格式文件不会被纳入导入范围且不会导致扫描失败，并在结果汇总中体现在“X个不支持文件被忽略”；遇到损坏或无法解析的支持格式文件时，系统跳过并给出友好提示或错误记录。\n4）补充场景4“读取并展示本地音乐信息”的成功标准：\n- 当前只说明“尝试读取标签”，缺少标签缺失或不完整时的显示策略（例如使用文件名作为标题）、编码异常（乱码）时的处理，以及用户界面上展示的具体行为（如在列表中显示哪些字段）。\n- 建议增加成功标准，覆盖：当文件缺少部分标签时使用合理的默认值（如未知专辑/歌手）、仍可正常导入并播放；读取失败或字符编码异常时不会阻断导入，并在 UI 中以可接受的形式显示或标记。\n5）补充场景5“建立纯本地音乐媒体库”的成功标准：\n- 目前只说“保存在本地媒体库中”，但未体现“不依赖网络、无账号登录”的约束如何在行为上体现，也未明确媒体库持久化与后续访问（重启应用后仍可读取）。\n- 建议新增成功标准，说明：写入媒体库时不触发任何网络请求、不需登录；关闭并重新打开播放器后，之前导入的媒体库可被正确加载；媒体库文件存储在本地指定位置且不会因为断网导致功能不可用。\n6）补充场景6“更新本地音乐库”的成功标准：\n- 当前只到“系统应检查新增、删除或移动的音乐文件”，缺少检查后的具体行为：如何更新媒体库记录、删除已不存在的条目、为新增文件创建记录，以及更新后用户界面列表的变化；也没说明增量扫描的效率约束（只扫描已配置目录）和用户反馈。\n- 建议新增成功标准，验证：重新/增量扫描完成后，媒体库中新增文件被加入、已删除文件从库中移除、被移动文件的路径信息被更新；更新结果在界面上同步（歌曲列表数量变化），并给出更新数量反馈；增量扫描不重复创建同一文件的多条记录。\n通过上述补充，可以更完整地覆盖主成功路径、关键异常路径、边界条件、数据持久化与状态变化，以及“纯本地、不联网”的关键约束。"
}
"""
